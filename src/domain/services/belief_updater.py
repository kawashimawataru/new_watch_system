"""
BeliefUpdater - 観測から Belief を更新

BattleMemory（ログ記録）と連携し、観測情報から BeliefState を
ベイズ的に更新する。

更新トリガー:
  1. 行動順から素早さを推定
  2. 被ダメージから耐久/アイテムを推定
  3. 見えた技から型を推定
  4. 見えた持ち物/特性/テラスを確定

References:
  - VGC-Bench: https://arxiv.org/abs/2506.10326
"""

from __future__ import annotations

from typing import Optional, Dict, List, Set
from dataclasses import dataclass

from src.domain.services.belief_state import (
    BeliefState,
    EVHypothesis,
    get_belief_state,
    COMMON_ITEMS,
)


# ============================================================================
# 型推定ルール
# ============================================================================

# 特定の技を見たときに確率が上がる持ち物/型
MOVE_TO_ITEM_HINTS = {
    # スカーフ示唆
    "voltswitch": {"choicescarf": 1.5, "choicespecs": 0.8},
    "uturn": {"choicescarf": 1.5, "choiceband": 0.8},
    "trick": {"choicescarf": 2.0, "choicespecs": 2.0},
    
    # 眼鏡/鉢巻示唆
    "dracometeor": {"choicespecs": 1.5, "lifeorb": 1.2},
    "overheat": {"choicespecs": 1.5, "lifeorb": 1.2},
    "closecombat": {"choiceband": 1.5, "lifeorb": 1.2},
    
    # 守る持ち→スカーフ/鉢巻/眼鏡ではない
    "protect": {"choicescarf": 0.1, "choicespecs": 0.1, "choiceband": 0.1},
    "detect": {"choicescarf": 0.1, "choicespecs": 0.1, "choiceband": 0.1},
    
    # 身代わり→襷/残飯/オボン示唆
    "substitute": {"focussash": 0.5, "leftovers": 1.5, "sitrusberry": 1.3},
    
    # 努力値示唆
    "trickroom": {},  # トリル要員はHC振り多い
    "tailwind": {},   # 追い風要員はHS振り多い
}

# 特定の技を見たときの努力値傾向
MOVE_TO_EV_HINTS = {
    "trickroom": {"HC252": 1.5, "HA252": 1.5, "CS252": 0.5, "AS252": 0.5},
    "tailwind": {"HS252": 1.3, "CS252": 0.8},
    "protect": {},  # 特に傾向なし
}


# ============================================================================
# BeliefUpdater
# ============================================================================

class BeliefUpdater:
    """
    観測から Belief を更新
    """
    
    def __init__(self, belief: Optional[BeliefState] = None):
        self.belief = belief or get_belief_state()
    
    def update_from_speed(
        self, 
        pokemon: str, 
        went_first: bool, 
        our_speed: int,
        our_pokemon: str
    ):
        """
        行動順から素早さを推定
        
        Args:
            pokemon: 相手ポケモン名
            went_first: 相手が先に動いたか
            our_speed: こちらのポケモンの素早さ実数値
            our_pokemon: こちらのポケモン名
        
        更新ロジック:
            相手が先に動いた → 相手の素早さ > こちらの素早さ
            → スカーフ/最速の仮説が上昇
        """
        pokemon_key = pokemon.lower().replace(" ", "").replace("-", "")
        
        if pokemon_key not in self.belief.ev_hypotheses:
            return
        
        # 努力値仮説を更新
        for hypo in self.belief.ev_hypotheses[pokemon_key]:
            # TODO: base_stat を取得する必要がある（ポケモンDBから）
            # 今はダミーとして素早さ100を仮定
            est_speed = hypo.get_stat("spe", 100, 50)
            
            if went_first:
                # 相手が先に動いた → 素早さが高い仮説の確率を上げる
                if "S252" in hypo.spread_name or "spe" in hypo.nature_boost:
                    hypo.probability *= 1.5
                else:
                    hypo.probability *= 0.7
            else:
                # こちらが先に動いた → 素早さが低い仮説の確率を上げる
                if "S252" in hypo.spread_name or "spe" in hypo.nature_boost:
                    hypo.probability *= 0.7
                else:
                    hypo.probability *= 1.3
        
        # 持ち物も更新（スカーフ）
        if went_first and pokemon_key in self.belief.item_beliefs:
            # 先に動いた → スカーフの可能性が上がる
            if "choicescarf" in self.belief.item_beliefs[pokemon_key]:
                self.belief.item_beliefs[pokemon_key]["choicescarf"] *= 1.5
        
        self._normalize_hypotheses(pokemon_key)
        self._normalize_items(pokemon_key)
    
    def update_from_damage(
        self, 
        pokemon: str, 
        move_used: str,
        damage_percent: float,
        our_pokemon: str,
        our_attack_stat: int,
        move_power: int
    ):
        """
        被ダメージから耐久/アイテムを推定
        
        Args:
            pokemon: ダメージを受けた相手ポケモン名
            move_used: 使用した技
            damage_percent: 与えたダメージ（HP%）
            our_pokemon: こちらのポケモン名
            our_attack_stat: こちらの攻撃/特攻実数値
            move_power: 技威力
        
        更新ロジック:
            ダメージが予想より低い → 耐久振り/半減実の確率が上がる
            ダメージが予想より高い → 無振り/弱点アイテムの確率が上がる
        """
        pokemon_key = pokemon.lower().replace(" ", "").replace("-", "")
        
        if pokemon_key not in self.belief.ev_hypotheses:
            return
        
        # TODO: DamageCalcService で各仮説のダメージレンジを計算し、
        # 観測値が入る仮説の確率を上げる
        
        # 簡易実装: ダメージ量で傾向を更新
        if damage_percent < 40:
            # ダメージが低い → 耐久振り
            for hypo in self.belief.ev_hypotheses[pokemon_key]:
                if "H" in hypo.spread_name or "B" in hypo.spread_name or "D" in hypo.spread_name:
                    hypo.probability *= 1.3
                else:
                    hypo.probability *= 0.8
            
            # 半減実の確率を上げる
            if pokemon_key in self.belief.item_beliefs:
                for item in ["occaberry", "wacanberry", "rindoberry", "cobaberry"]:
                    if item in self.belief.item_beliefs[pokemon_key]:
                        self.belief.item_beliefs[pokemon_key][item] *= 1.5
        
        elif damage_percent > 60:
            # ダメージが高い → 無振り
            for hypo in self.belief.ev_hypotheses[pokemon_key]:
                if "C" in hypo.spread_name or "A" in hypo.spread_name:
                    if "H" not in hypo.spread_name:
                        hypo.probability *= 1.3
                else:
                    hypo.probability *= 0.8
        
        self._normalize_hypotheses(pokemon_key)
        self._normalize_items(pokemon_key)
    
    def update_from_seen_move(self, pokemon: str, move: str):
        """
        見えた技から型を推定
        
        Args:
            pokemon: 相手ポケモン名
            move: 見えた技名
        """
        pokemon_key = pokemon.lower().replace(" ", "").replace("-", "")
        move_key = move.lower().replace(" ", "").replace("-", "")
        
        # 見えた技を記録
        if pokemon_key not in self.belief.seen_moves:
            self.belief.seen_moves[pokemon_key] = set()
        self.belief.seen_moves[pokemon_key].add(move_key)
        
        # 持ち物確率を更新
        if move_key in MOVE_TO_ITEM_HINTS and pokemon_key in self.belief.item_beliefs:
            for item, multiplier in MOVE_TO_ITEM_HINTS[move_key].items():
                if item in self.belief.item_beliefs[pokemon_key]:
                    self.belief.item_beliefs[pokemon_key][item] *= multiplier
            
            self._normalize_items(pokemon_key)
        
        # 努力値確率を更新
        if move_key in MOVE_TO_EV_HINTS and pokemon_key in self.belief.ev_hypotheses:
            for hypo in self.belief.ev_hypotheses[pokemon_key]:
                for spread_name, multiplier in MOVE_TO_EV_HINTS[move_key].items():
                    if spread_name in hypo.spread_name:
                        hypo.probability *= multiplier
            
            self._normalize_hypotheses(pokemon_key)
    
    def update_from_seen_item(self, pokemon: str, item: str):
        """持ち物が確定した時"""
        pokemon_key = pokemon.lower().replace(" ", "").replace("-", "")
        self.belief.confirmed_items[pokemon_key] = item.lower()
        
        # 確率分布はもう不要だがクリア
        if pokemon_key in self.belief.item_beliefs:
            self.belief.item_beliefs[pokemon_key] = {item.lower(): 1.0}
    
    def update_from_seen_ability(self, pokemon: str, ability: str):
        """特性が確定した時"""
        pokemon_key = pokemon.lower().replace(" ", "").replace("-", "")
        self.belief.confirmed_abilities[pokemon_key] = ability.lower()
    
    def update_from_tera(self, pokemon: str, tera_type: str):
        """テラスタイプが確定した時"""
        pokemon_key = pokemon.lower().replace(" ", "").replace("-", "")
        self.belief.confirmed_tera[pokemon_key] = tera_type.lower()
        
        # 確率分布をクリア
        if pokemon_key in self.belief.tera_beliefs:
            self.belief.tera_beliefs[pokemon_key] = {tera_type.lower(): 1.0}
    
    def _normalize_hypotheses(self, pokemon_key: str):
        """努力値仮説の確率を正規化"""
        hypotheses = self.belief.ev_hypotheses.get(pokemon_key, [])
        if not hypotheses:
            return
        
        total = sum(h.probability for h in hypotheses)
        if total > 0:
            for h in hypotheses:
                h.probability /= total
    
    def _normalize_items(self, pokemon_key: str):
        """持ち物確率を正規化"""
        items = self.belief.item_beliefs.get(pokemon_key, {})
        if not items:
            return
        
        total = sum(items.values())
        if total > 0:
            for item in items:
                items[item] /= total


# ============================================================================
# シングルトン
# ============================================================================

_belief_updater: Optional[BeliefUpdater] = None

def get_belief_updater() -> BeliefUpdater:
    """BeliefUpdater のシングルトンを取得"""
    global _belief_updater
    if _belief_updater is None:
        _belief_updater = BeliefUpdater()
    return _belief_updater

def reset_belief_updater():
    """新しいバトル開始時にリセット"""
    global _belief_updater
    _belief_updater = BeliefUpdater()
