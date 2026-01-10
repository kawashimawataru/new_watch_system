"""
BeliefState - 隠れ情報の確率管理

VGCは隠れ情報（持ち物、努力値、技構成、テラスタイプ）が勝敗に直結する。
このモジュールは「見えた情報」ではなく「確率で仮定」するBeliefを管理する。

概念:
  Belief = 観測 → 事後確率の更新（ベイズ推論的）

  例1: 行動順で素早さを推定
    - 相手のミライドンがこちらのトルネロス（S121）より先に動いた
    - → 「最速orスカーフ」の確率が上昇

  例2: 被ダメージで耐久を推定
    - ダメージ量からDamageCalcServiceで逆算
    - → 「H252振り」「半減実なし」の確率が上昇

  例3: 技が見えたことで型を推定
    - 相手のカイオーガが「れいとうビーム」を見せた
    - → 「スカーフ型」「CSメガネ型」の確率が上昇

References:
  - VGC-Bench: https://arxiv.org/abs/2506.10326
  - PokéChamp: https://arxiv.org/abs/2503.04094
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any


# ============================================================================
# 努力値仮説
# ============================================================================

@dataclass
class EVHypothesis:
    """
    努力値仮説（1つの振り方パターン）
    
    例: "CS252" = 特攻252, 素早さ252, H4
    """
    spread_name: str  # "CS252", "HS252", "HB252" など
    hp: int = 0
    atk: int = 0
    def_: int = 0
    spa: int = 0
    spd: int = 0
    spe: int = 0
    nature_boost: str = ""  # "spa", "spe", "atk" など
    probability: float = 0.25  # 事後確率
    
    def get_stat(self, stat_name: str, base_stat: int, level: int = 50) -> int:
        """
        実数値を計算
        
        Args:
            stat_name: "hp", "atk", "def", "spa", "spd", "spe"
            base_stat: 種族値
            level: レベル（VGCは50）
        
        Returns:
            実数値
        """
        ev_map = {
            "hp": self.hp,
            "atk": self.atk,
            "def": self.def_,
            "spa": self.spa,
            "spd": self.spd,
            "spe": self.spe,
        }
        ev = ev_map.get(stat_name, 0)
        
        if stat_name == "hp":
            # HP計算式
            return int((base_stat * 2 + 31 + ev // 4) * level // 100 + level + 10)
        else:
            # その他のステータス計算式
            stat = int((base_stat * 2 + 31 + ev // 4) * level // 100 + 5)
            
            # 性格補正
            if self.nature_boost == stat_name:
                stat = int(stat * 1.1)
            
            return stat


# ============================================================================
# 代表的な努力値テンプレ
# ============================================================================

COMMON_EV_SPREADS = {
    # 高速アタッカー
    "CS252": EVHypothesis("CS252", hp=4, spa=252, spe=252, nature_boost="spa"),
    "AS252": EVHypothesis("AS252", hp=4, atk=252, spe=252, nature_boost="atk"),
    "CS252_timid": EVHypothesis("CS252_timid", hp=4, spa=252, spe=252, nature_boost="spe"),
    "AS252_jolly": EVHypothesis("AS252_jolly", hp=4, atk=252, spe=252, nature_boost="spe"),
    
    # 耐久型
    "HS252": EVHypothesis("HS252", hp=252, spa=4, spe=252, nature_boost="spe"),
    "HB252": EVHypothesis("HB252", hp=252, def_=252, spa=4, nature_boost="def"),
    "HD252": EVHypothesis("HD252", hp=252, spd=252, spa=4, nature_boost="spd"),
    
    # バランス型
    "H252_S252": EVHypothesis("H252_S252", hp=252, spe=252, spa=4, nature_boost="spe"),
    "H252_C252": EVHypothesis("H252_C252", hp=252, spa=252, spe=4, nature_boost="spa"),
    
    # トリル用（S逆V想定はレベル50では大差ないので省略）
    "HC252": EVHypothesis("HC252", hp=252, spa=252, def_=4, nature_boost="spa"),
    "HA252": EVHypothesis("HA252", hp=252, atk=252, def_=4, nature_boost="atk"),
}


# ============================================================================
# 代表的な持ち物
# ============================================================================

COMMON_ITEMS = {
    # 火力アイテム
    "lifeorb": 0.15,
    "choicespecs": 0.10,
    "choiceband": 0.08,
    "choicescarf": 0.12,
    "expertbelt": 0.05,
    
    # 耐久アイテム
    "assaultvest": 0.10,
    "leftovers": 0.05,
    "sitrusberry": 0.05,
    
    # 半減実
    "occaberry": 0.05,  # 炎半減
    "wacanberry": 0.05,  # 電気半減
    "rindoberry": 0.04,  # 草半減
    "cobaberry": 0.04,   # 飛行半減
    
    # その他
    "focussash": 0.08,
    "safetygoggles": 0.04,
    "clearamulet": 0.03,
}


# ============================================================================
# BeliefState
# ============================================================================

@dataclass
class BeliefState:
    """
    隠れ情報に対する事後確率
    BattleMemoryの上位層として動作
    """
    
    # ============= 持ち物の確率分布 =============
    # {"miraidon": {"choicescarf": 0.4, "lifeorb": 0.3, ...}}
    item_beliefs: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # ============= 努力値仮説 =============
    # {"miraidon": [EVHypothesis(...), ...]}
    ev_hypotheses: Dict[str, List[EVHypothesis]] = field(default_factory=dict)
    
    # ============= テラスタイプ確率 =============
    # {"miraidon": {"fairy": 0.3, "steel": 0.25, ...}}
    tera_beliefs: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # ============= 残り技スロット確率 =============
    # {"miraidon": {0: {"thunderbolt": 1.0}, 1: {"protect": 0.6, ...}, ...}}
    move_slot_beliefs: Dict[str, Dict[int, Dict[str, float]]] = field(default_factory=dict)
    
    # ============= 確定情報（見えた） =============
    confirmed_items: Dict[str, str] = field(default_factory=dict)
    confirmed_abilities: Dict[str, str] = field(default_factory=dict)
    confirmed_tera: Dict[str, str] = field(default_factory=dict)
    seen_moves: Dict[str, Set[str]] = field(default_factory=dict)
    
    def initialize_pokemon(self, pokemon: str, base_stats: Optional[Dict[str, int]] = None):
        """
        ポケモンの Belief を初期化（デフォルト prior）
        """
        pokemon_key = pokemon.lower().replace(" ", "").replace("-", "")
        
        # 持ち物
        self.item_beliefs[pokemon_key] = dict(COMMON_ITEMS)
        
        # 努力値仮説（代表的な4パターンから開始）
        self.ev_hypotheses[pokemon_key] = [
            EVHypothesis("CS252", hp=4, spa=252, spe=252, nature_boost="spa", probability=0.35),
            EVHypothesis("AS252", hp=4, atk=252, spe=252, nature_boost="atk", probability=0.25),
            EVHypothesis("HS252", hp=252, spa=4, spe=252, nature_boost="spe", probability=0.20),
            EVHypothesis("HB252", hp=252, def_=252, spa=4, nature_boost="def", probability=0.20),
        ]
        
        # テラスタイプ（よくある5タイプから開始）
        self.tera_beliefs[pokemon_key] = {
            "fairy": 0.20,
            "steel": 0.15,
            "water": 0.15,
            "grass": 0.15,
            "ground": 0.10,
            "fire": 0.10,
            "flying": 0.05,
            "ghost": 0.05,
            "electric": 0.05,
        }
        
        # 技スロット
        self.move_slot_beliefs[pokemon_key] = {}
        self.seen_moves[pokemon_key] = set()
    
    def get_item_prob(self, pokemon: str, item: str) -> float:
        """持ち物の確率を取得"""
        pokemon_key = pokemon.lower().replace(" ", "").replace("-", "")
        
        # 確定情報があればそれを返す
        if pokemon_key in self.confirmed_items:
            return 1.0 if self.confirmed_items[pokemon_key] == item else 0.0
        
        beliefs = self.item_beliefs.get(pokemon_key, {})
        return beliefs.get(item, 0.0)
    
    def get_most_likely_item(self, pokemon: str) -> Tuple[str, float]:
        """最も確率の高い持ち物を取得"""
        pokemon_key = pokemon.lower().replace(" ", "").replace("-", "")
        
        if pokemon_key in self.confirmed_items:
            return (self.confirmed_items[pokemon_key], 1.0)
        
        beliefs = self.item_beliefs.get(pokemon_key, {})
        if not beliefs:
            return ("unknown", 0.0)
        
        best = max(beliefs.items(), key=lambda x: x[1])
        return best
    
    def get_speed_range(self, pokemon: str, base_speed: int) -> Tuple[int, int]:
        """
        素早さの確率付きレンジを取得
        
        Returns:
            (min_speed, max_speed) の中で確率50%以上をカバーするレンジ
        """
        pokemon_key = pokemon.lower().replace(" ", "").replace("-", "")
        hypotheses = self.ev_hypotheses.get(pokemon_key, [])
        
        if not hypotheses:
            # デフォルト: 無振り～最速
            min_s = int((base_speed * 2 + 31) * 50 // 100 + 5)
            max_s = int((base_speed * 2 + 31 + 63) * 50 // 100 + 5 * 1.1)
            return (min_s, int(max_s))
        
        speeds = []
        for h in hypotheses:
            s = h.get_stat("spe", base_speed, 50)
            speeds.append((s, h.probability))
        
        speeds.sort(key=lambda x: x[0])
        return (speeds[0][0], speeds[-1][0])
    
    def sample(self) -> Dict[str, Dict[str, Any]]:
        """
        Belief から仮説をサンプル（Determinization MCTS 用）
        
        Returns:
            {"miraidon": {"item": "choicescarf", "ev_spread": "CS252", ...}, ...}
        """
        result = {}
        
        for pokemon_key in self.item_beliefs.keys():
            pokemon_sample = {}
            
            # 持ち物をサンプル
            if pokemon_key in self.confirmed_items:
                pokemon_sample["item"] = self.confirmed_items[pokemon_key]
            else:
                items = list(self.item_beliefs[pokemon_key].items())
                if items:
                    names, probs = zip(*items)
                    total = sum(probs)
                    if total > 0:
                        normalized = [p / total for p in probs]
                        pokemon_sample["item"] = random.choices(names, normalized)[0]
            
            # 努力値をサンプル
            hypotheses = self.ev_hypotheses.get(pokemon_key, [])
            if hypotheses:
                probs = [h.probability for h in hypotheses]
                total = sum(probs)
                if total > 0:
                    normalized = [p / total for p in probs]
                    sampled_hypo = random.choices(hypotheses, normalized)[0]
                    pokemon_sample["ev_spread"] = sampled_hypo.spread_name
            
            # テラスタイプをサンプル
            if pokemon_key in self.confirmed_tera:
                pokemon_sample["tera_type"] = self.confirmed_tera[pokemon_key]
            else:
                tera_beliefs = self.tera_beliefs.get(pokemon_key, {})
                if tera_beliefs:
                    types, probs = zip(*tera_beliefs.items())
                    total = sum(probs)
                    if total > 0:
                        normalized = [p / total for p in probs]
                        pokemon_sample["tera_type"] = random.choices(types, normalized)[0]
            
            result[pokemon_key] = pokemon_sample
        
        return result
    
    def to_summary(self) -> str:
        """デバッグ用サマリー"""
        lines = ["=== BeliefState Summary ==="]
        
        for pokemon_key in self.item_beliefs.keys():
            lines.append(f"\n【{pokemon_key}】")
            
            # 持ち物
            if pokemon_key in self.confirmed_items:
                lines.append(f"  持ち物: {self.confirmed_items[pokemon_key]} (確定)")
            else:
                item, prob = self.get_most_likely_item(pokemon_key)
                lines.append(f"  持ち物: {item} ({prob:.0%})")
            
            # 努力値
            hypotheses = self.ev_hypotheses.get(pokemon_key, [])
            if hypotheses:
                top = max(hypotheses, key=lambda h: h.probability)
                lines.append(f"  努力値: {top.spread_name} ({top.probability:.0%})")
            
            # テラス
            if pokemon_key in self.confirmed_tera:
                lines.append(f"  テラス: {self.confirmed_tera[pokemon_key]} (確定)")
            else:
                tera = self.tera_beliefs.get(pokemon_key, {})
                if tera:
                    best_tera = max(tera.items(), key=lambda x: x[1])
                    lines.append(f"  テラス: {best_tera[0]} ({best_tera[1]:.0%})")
            
            # 見えた技
            seen = self.seen_moves.get(pokemon_key, set())
            if seen:
                lines.append(f"  見えた技: {', '.join(seen)}")
        
        return "\n".join(lines)


# ============================================================================
# シングルトン
# ============================================================================

_belief_state: Optional[BeliefState] = None

def get_belief_state() -> BeliefState:
    """BeliefState のシングルトンを取得"""
    global _belief_state
    if _belief_state is None:
        _belief_state = BeliefState()
    return _belief_state

def reset_belief_state():
    """新しいバトル開始時にリセット"""
    global _belief_state
    _belief_state = BeliefState()
