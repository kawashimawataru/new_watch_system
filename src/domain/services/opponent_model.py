"""
OpponentModel - 相手行動予測

Phase C: 相手の次の行動を確率的に予測する

機能:
- Protect確率の推定
- 交代確率の推定
- 技選択の確率分布
- Quantal Response による確率化
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any
import math

from src.domain.services.damage_calc_service import (
    DamageCalcService, get_damage_calc_service,
    PokemonStats, MoveData, DamageResult,
    create_pokemon_from_poke_env, create_move_from_poke_env
)
from src.domain.services.battle_memory import (
    BattleMemory, get_battle_memory
)


# =============================================================================
# データクラス
# =============================================================================

@dataclass
class ActionPrediction:
    """1つの行動の予測"""
    action_type: str          # "move", "switch", "protect"
    action_id: str            # 技ID or ポケモン名
    probability: float        # 選択確率 (0.0 ~ 1.0)
    target: Optional[int] = None  # ターゲット
    rationale: str = ""       # 理由


@dataclass
class SlotPrediction:
    """1スロットの行動予測"""
    slot: int                           # 0 or 1
    species: str                        # ポケモン種族
    predictions: List[ActionPrediction] # 確率降順
    
    @property
    def top_prediction(self) -> Optional[ActionPrediction]:
        """最も確率の高い予測"""
        return self.predictions[0] if self.predictions else None
    
    def get_protect_prob(self) -> float:
        """Protect確率を取得"""
        for p in self.predictions:
            if p.action_type == "protect":
                return p.probability
        return 0.0


# =============================================================================
# OpponentModel
# =============================================================================

class OpponentModel:
    """
    相手の行動を予測するモデル
    
    VGCにおける相手の意思決定をモデル化:
    1. Protect: 集中されそう、不利対面、HP低い時に上昇
    2. 交代: ワンパン圏内、不利対面時に上昇
    3. 技選択: ダメ計で高効率な技を優先、Quantal Response で確率化
    """
    
    def __init__(
        self,
        damage_calc: Optional[DamageCalcService] = None,
        memory: Optional[BattleMemory] = None,
        tau: float = 0.5,  # Quantal Response 温度
    ):
        """
        初期化
        
        Args:
            damage_calc: ダメージ計算サービス
            memory: バトル履歴
            tau: Quantal Response の温度パラメータ（小=鋭い、大=散る）
        """
        self.damage_calc = damage_calc or get_damage_calc_service()
        self.memory = memory or get_battle_memory()
        self.tau = tau
    
    def predict_slot(
        self,
        opp_pokemon: Any,  # poke-env Pokemon
        opp_moves: List[Any],  # poke-env Move list
        self_pokemon: List[Any],  # 自分の場のポケモン
        slot: int,
        field_conditions: Optional[Dict[str, Any]] = None,
    ) -> SlotPrediction:
        """
        1スロットの行動を予測
        
        Args:
            opp_pokemon: 相手ポケモン
            opp_moves: 相手の使用可能技
            self_pokemon: 自分の場のポケモン（2体）
            slot: スロット番号 (0 or 1)
            field_conditions: フィールド状態
            
        Returns:
            SlotPrediction: 予測結果
        """
        predictions: List[ActionPrediction] = []
        field_conditions = field_conditions or {}
        
        species = opp_pokemon.species if hasattr(opp_pokemon, 'species') else str(opp_pokemon)
        
        # 自分のポケモンをStats形式に変換
        self_stats = []
        for p in self_pokemon:
            if p and not (hasattr(p, 'fainted') and p.fainted):
                self_stats.append(create_pokemon_from_poke_env(p))
        
        if not self_stats:
            # 自分が全滅している場合は適当に返す
            return SlotPrediction(slot=slot, species=species, predictions=[])
        
        opp_stats = create_pokemon_from_poke_env(opp_pokemon)
        
        # -----------------------------------------------------------------
        # 1. Protect確率
        # -----------------------------------------------------------------
        protect_prob = self._estimate_protect_prob(
            opp_stats, self_stats, field_conditions
        )
        
        if protect_prob > 0.05:
            predictions.append(ActionPrediction(
                action_type="protect",
                action_id="protect",
                probability=protect_prob,
                rationale="集中/不利対面でProtect可能性"
            ))
        
        # -----------------------------------------------------------------
        # 2. 交代確率
        # -----------------------------------------------------------------
        switch_prob = self._estimate_switch_prob(
            opp_stats, self_stats, field_conditions
        )
        
        if switch_prob > 0.05:
            predictions.append(ActionPrediction(
                action_type="switch",
                action_id="switch",
                probability=switch_prob,
                rationale="不利対面/ワンパン回避で交代可能性"
            ))
        
        # -----------------------------------------------------------------
        # 3. 技選択の確率分布
        # -----------------------------------------------------------------
        move_probs = self._estimate_move_probs(
            opp_stats, opp_moves, self_stats, field_conditions
        )
        
        # Protect/交代を除いた残り確率を技に分配
        remaining_prob = 1.0 - protect_prob - switch_prob
        remaining_prob = max(0.0, remaining_prob)
        
        for move_id, base_prob, target, rationale in move_probs:
            adjusted_prob = base_prob * remaining_prob
            if adjusted_prob > 0.01:
                predictions.append(ActionPrediction(
                    action_type="move",
                    action_id=move_id,
                    probability=adjusted_prob,
                    target=target,
                    rationale=rationale
                ))
        
        # 確率降順ソート
        predictions.sort(key=lambda x: x.probability, reverse=True)
        
        # 確率の正規化（合計が1.0になるように）
        total_prob = sum(p.probability for p in predictions)
        if total_prob > 0:
            for p in predictions:
                p.probability /= total_prob
        
        return SlotPrediction(slot=slot, species=species, predictions=predictions)
    
    def predict_both_slots(
        self,
        opp_pokemon: List[Any],  # 相手の場の2体
        opp_available_moves: List[List[Any]],  # 各スロットの技
        self_pokemon: List[Any],  # 自分の場の2体
        field_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[SlotPrediction]:
        """
        両スロットの行動を予測
        
        Returns:
            List[SlotPrediction]: 2つのスロットの予測
        """
        results = []
        
        for slot in range(2):
            if slot < len(opp_pokemon) and opp_pokemon[slot]:
                moves = opp_available_moves[slot] if slot < len(opp_available_moves) else []
                pred = self.predict_slot(
                    opp_pokemon[slot],
                    moves,
                    self_pokemon,
                    slot,
                    field_conditions
                )
                results.append(pred)
        
        return results
    
    # =========================================================================
    # 確率推定
    # =========================================================================
    
    def _estimate_protect_prob(
        self,
        opp: PokemonStats,
        self_pokemon: List[PokemonStats],
        field_conditions: Dict[str, Any],
    ) -> float:
        """Protect使用確率を推定"""
        
        # 連続Protect判定
        consecutive = self.memory.get_consecutive_protects(opp.species, is_opponent=True)
        protect_success_rate = self.memory.get_protect_probability(opp.species)
        
        # 連続Protectは成功率が下がるので使いにくい
        if consecutive >= 1:
            return 0.05 * protect_success_rate
        
        # 集中されそうか判定
        is_focused = self._check_focus_threat(opp, self_pokemon)
        
        # 不利対面か
        is_unfavorable = self._check_unfavorable_matchup(opp, self_pokemon)
        
        # HP比率
        hp_ratio = opp.hp / opp.max_hp if opp.max_hp > 0 else 1.0
        
        return self.memory.estimate_protect_likelihood(
            opp.species,
            is_being_focused=is_focused,
            is_unfavorable_matchup=is_unfavorable,
            hp_ratio=hp_ratio
        )
    
    def _estimate_switch_prob(
        self,
        opp: PokemonStats,
        self_pokemon: List[PokemonStats],
        field_conditions: Dict[str, Any],
    ) -> float:
        """交代確率を推定"""
        
        # ワンパン圏内か
        is_one_shot = False
        for self_poke in self_pokemon:
            # 簡易判定：自分のポケモンが相手を倒せるか
            # TODO: 実際の技を使った判定
            pass
        
        # 不利対面か
        is_unfavorable = self._check_unfavorable_matchup(opp, self_pokemon)
        
        return self.memory.estimate_switch_likelihood(
            opp.species,
            is_one_shot_range=is_one_shot,
            is_unfavorable_matchup=is_unfavorable,
            has_better_switch=True  # 簡略化
        )
    
    def _estimate_move_probs(
        self,
        opp: PokemonStats,
        opp_moves: List[Any],
        self_pokemon: List[PokemonStats],
        field_conditions: Dict[str, Any],
    ) -> List[Tuple[str, float, Optional[int], str]]:
        """
        技選択の確率分布を推定
        
        Returns:
            List[(move_id, probability, target, rationale)]
        """
        if not opp_moves:
            return []
        
        # 各技のスコアを計算
        move_scores: List[Tuple[str, float, Optional[int], str]] = []
        
        for move in opp_moves:
            move_data = create_move_from_poke_env(move)
            
            # 変化技は別途評価
            if move_data.category == "status":
                score = self._score_status_move(move_data, opp, self_pokemon)
                move_scores.append((move_data.id, score, None, "変化技"))
                continue
            
            # 各ターゲットへのダメージを計算
            best_score = 0.0
            best_target = None
            best_rationale = ""
            
            for i, target in enumerate(self_pokemon):
                result = self.damage_calc.calculate(opp, target, move_data, field_conditions)
                
                # スコア = KO確率 * 2 + 期待値 / 100
                score = result.ko_prob * 2.0 + result.expected / 100.0
                
                # タイプ相性ボーナス
                if result.type_effectiveness >= 2.0:
                    score *= 1.3
                
                if score > best_score:
                    best_score = score
                    best_target = i + 1  # 1-indexed
                    if result.ko_prob > 0.9:
                        best_rationale = f"確殺 ({result.expected:.0f}%)"
                    elif result.ko_prob > 0.5:
                        best_rationale = f"高乱数 ({result.expected:.0f}%)"
                    else:
                        best_rationale = f"ダメージ {result.expected:.0f}%"
            
            # 範囲技は両方にダメージ
            if move_data.is_spread:
                total_damage = 0.0
                for target in self_pokemon:
                    result = self.damage_calc.calculate(opp, target, move_data, field_conditions)
                    total_damage += result.expected
                best_score = total_damage / 100.0
                best_target = None  # 範囲技
                best_rationale = f"範囲技 合計{total_damage:.0f}%"
            
            move_scores.append((move_data.id, best_score, best_target, best_rationale))
        
        # Quantal Response で確率化
        if not move_scores:
            return []
        
        scores = [s[1] for s in move_scores]
        probs = self._quantal_response(scores)
        
        result = []
        for i, (move_id, score, target, rationale) in enumerate(move_scores):
            result.append((move_id, probs[i], target, rationale))
        
        return result
    
    def _score_status_move(
        self,
        move: MoveData,
        opp: PokemonStats,
        self_pokemon: List[PokemonStats],
    ) -> float:
        """変化技のスコアを計算"""
        move_id = move.id.lower()
        
        # 高スコア技
        high_value_moves = {
            "tailwind": 1.5,      # おいかぜ
            "trickroom": 1.5,     # トリックルーム
            "thunderwave": 1.2,   # でんじは
            "willowisp": 1.2,     # おにび
            "spore": 1.5,         # キノコのほうし
            "sleeppowder": 1.3,   # ねむりごな
            "swordsdance": 1.0,   # つるぎのまい
            "nastyplot": 1.0,     # わるだくみ
            "substitute": 0.8,    # みがわり
        }
        
        return high_value_moves.get(move_id, 0.5)
    
    # =========================================================================
    # ヘルパー
    # =========================================================================
    
    def _check_focus_threat(
        self,
        opp: PokemonStats,
        self_pokemon: List[PokemonStats],
    ) -> bool:
        """集中攻撃されそうか判定"""
        # 簡易実装: 自分が2体いて、相手のHP が低い場合
        if len(self_pokemon) >= 2:
            hp_ratio = opp.hp / opp.max_hp if opp.max_hp > 0 else 1.0
            if hp_ratio < 0.6:
                return True
        return False
    
    def _check_unfavorable_matchup(
        self,
        opp: PokemonStats,
        self_pokemon: List[PokemonStats],
    ) -> bool:
        """不利対面か判定"""
        # 簡易実装: タイプ相性で判定
        from src.domain.models.type_chart import get_type_effectiveness
        
        for self_poke in self_pokemon:
            for self_type in self_poke.types:
                eff = get_type_effectiveness(self_type, opp.types)
                if eff >= 2.0:
                    return True
        return False
    
    def _quantal_response(self, utilities: List[float]) -> List[float]:
        """
        Quantal Response で効用値を確率に変換
        
        P(a) ∝ exp(Q(a) / τ)
        """
        if not utilities:
            return []
        
        # オーバーフロー防止のため最大値を引く
        max_u = max(utilities)
        exp_values = [math.exp((u - max_u) / self.tau) for u in utilities]
        total = sum(exp_values)
        
        if total == 0:
            return [1.0 / len(utilities)] * len(utilities)
        
        return [e / total for e in exp_values]


# =============================================================================
# シングルトン
# =============================================================================

_model: Optional[OpponentModel] = None


def get_opponent_model() -> OpponentModel:
    """OpponentModel のシングルトンを取得"""
    global _model
    if _model is None:
        _model = OpponentModel()
    return _model
