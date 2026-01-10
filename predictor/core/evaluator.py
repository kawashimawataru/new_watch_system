"""
Evaluator - 葉ノード評価

PokéChamp型アーキテクチャの価値推定モジュール。
ヒューリスティック評価 + LLM補助。

References:
- PokéChamp: https://arxiv.org/abs/2503.04094 (value estimation)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

try:
    from poke_env.environment.double_battle import DoubleBattle
    from poke_env.environment.pokemon import Pokemon
except ImportError:
    try:
        from poke_env.battle import DoubleBattle, Pokemon
    except ImportError:
        DoubleBattle = None
        Pokemon = None


# ============================================================================
# 設定
# ============================================================================

@dataclass
class EvaluatorConfig:
    """評価器の設定"""
    sim_weight: float = 0.8         # α: シミュレーション価値の重み
    llm_weight: float = 0.2         # 1-α: LLM価値の重み
    
    # ヒューリスティック重み
    hp_weight: float = 0.30
    remaining_weight: float = 0.20
    speed_weight: float = 0.20
    tera_weight: float = 0.10
    momentum_weight: float = 0.15
    status_weight: float = 0.05


# ============================================================================
# Evaluator
# ============================================================================

class Evaluator:
    """
    葉ノード評価器
    
    V(s) = α * V_sim + (1-α) * V_llm
    
    - V_sim: ヒューリスティック評価
    - V_llm: LLM価値推定（オプション）
    """
    
    def __init__(
        self,
        config: Optional[EvaluatorConfig] = None,
        llm_client: Optional[Any] = None,
    ):
        self.config = config or EvaluatorConfig()
        self.llm = llm_client
    
    def evaluate(
        self,
        battle: DoubleBattle,
        side: Literal["self", "opp"] = "self"
    ) -> float:
        """
        状態を評価
        
        Returns:
            [-1, +1] の範囲の価値（+1 が side 有利）
        """
        v_sim = self._heuristic_value(battle, side)
        
        if self.llm:
            v_llm = self._llm_value(battle, side)
            return self.config.sim_weight * v_sim + self.config.llm_weight * v_llm
        
        return v_sim
    
    def evaluate_with_breakdown(
        self,
        battle: DoubleBattle,
        side: Literal["self", "opp"] = "self"
    ) -> Tuple[float, Dict[str, float]]:
        """
        評価と内訳を返す
        
        Returns:
            (value, breakdown_dict)
        """
        breakdown = {}
        
        # HP差
        hp_score = self._hp_advantage(battle, side)
        breakdown["hp"] = hp_score
        
        # 残数差
        remaining_score = self._remaining_advantage(battle, side)
        breakdown["remaining"] = remaining_score
        
        # 速度支配
        speed_score = self._speed_advantage(battle, side)
        breakdown["speed"] = speed_score
        
        # テラスタル
        tera_score = self._tera_advantage(battle, side)
        breakdown["tera"] = tera_score
        
        # モメンタム（場の有利）
        momentum_score = self._momentum(battle, side)
        breakdown["momentum"] = momentum_score
        
        # 状態異常
        status_score = self._status_advantage(battle, side)
        breakdown["status"] = status_score
        
        # 加重平均
        value = (
            self.config.hp_weight * hp_score +
            self.config.remaining_weight * remaining_score +
            self.config.speed_weight * speed_score +
            self.config.tera_weight * tera_score +
            self.config.momentum_weight * momentum_score +
            self.config.status_weight * status_score
        )
        
        # クリップ
        value = max(-1.0, min(1.0, value))
        breakdown["total"] = value
        
        return value, breakdown
    
    def _heuristic_value(
        self,
        battle: DoubleBattle,
        side: str
    ) -> float:
        """ヒューリスティック評価"""
        value, _ = self.evaluate_with_breakdown(battle, side)
        return value
    
    def _hp_advantage(self, battle: DoubleBattle, side: str) -> float:
        """HP合計の差"""
        self_hp = 0.0
        self_count = 0
        opp_hp = 0.0
        opp_count = 0
        
        # 自分のチーム
        for p in battle.team.values():
            if p and not p.fainted:
                self_hp += p.current_hp_fraction
                self_count += 1
        
        # 相手のチーム
        for p in battle.opponent_team.values():
            if p and not p.fainted:
                opp_hp += p.current_hp_fraction
                opp_count += 1
        
        # 正規化
        if self_count > 0:
            self_hp /= self_count
        if opp_count > 0:
            opp_hp /= opp_count
        
        # side が self なら self_hp - opp_hp
        if side == "self":
            return self_hp - opp_hp
        else:
            return opp_hp - self_hp
    
    def _remaining_advantage(self, battle: DoubleBattle, side: str) -> float:
        """残数の差"""
        self_remaining = sum(1 for p in battle.team.values() if p and not p.fainted)
        opp_remaining = sum(1 for p in battle.opponent_team.values() if p and not p.fainted)
        
        # 6体中の残数を正規化
        diff = (self_remaining - opp_remaining) / 6.0
        
        if side == "self":
            return diff * 2  # -2 to +2 にスケール
        else:
            return -diff * 2
    
    def _speed_advantage(self, battle: DoubleBattle, side: str) -> float:
        """速度支配の評価"""
        score = 0.0
        
        # 追い風
        if hasattr(battle, 'side_conditions'):
            if 'TAILWIND' in str(battle.side_conditions).upper():
                score += 0.5
        
        # 相手の追い風
        if hasattr(battle, 'opponent_side_conditions'):
            if 'TAILWIND' in str(battle.opponent_side_conditions).upper():
                score -= 0.5
        
        # トリックルーム
        if hasattr(battle, 'fields'):
            if 'TRICK_ROOM' in str(battle.fields).upper():
                # トリルは遅い側が有利
                # 簡易判定: 自分が遅いなら+、速いなら-
                # TODO: より正確な判定
                pass
        
        if side == "opp":
            score = -score
        
        return score
    
    def _tera_advantage(self, battle: DoubleBattle, side: str) -> float:
        """テラスタル残りの評価"""
        self_tera_available = not getattr(battle, '_tera_used', False)
        opp_tera_available = True  # 相手のテラ使用状況は推測
        
        score = 0.0
        if self_tera_available:
            score += 0.3
        if not opp_tera_available:
            score += 0.2
        
        if side == "opp":
            score = -score
        
        return score
    
    def _momentum(self, battle: DoubleBattle, side: str) -> float:
        """モメンタム（場の有利）"""
        score = 0.0
        
        # 壁
        if hasattr(battle, 'side_conditions'):
            conditions = str(battle.side_conditions).upper()
            if 'REFLECT' in conditions:
                score += 0.2
            if 'LIGHT_SCREEN' in conditions:
                score += 0.2
            if 'AURORA_VEIL' in conditions:
                score += 0.3
        
        # 相手の壁
        if hasattr(battle, 'opponent_side_conditions'):
            conditions = str(battle.opponent_side_conditions).upper()
            if 'REFLECT' in conditions:
                score -= 0.2
            if 'LIGHT_SCREEN' in conditions:
                score -= 0.2
            if 'AURORA_VEIL' in conditions:
                score -= 0.3
        
        if side == "opp":
            score = -score
        
        return score
    
    def _status_advantage(self, battle: DoubleBattle, side: str) -> float:
        """状態異常の評価"""
        self_bad = 0
        opp_bad = 0
        
        for p in battle.active_pokemon:
            if p and p.status:
                self_bad += 1
        
        for p in battle.opponent_active_pokemon:
            if p and p.status:
                opp_bad += 1
        
        score = (opp_bad - self_bad) * 0.3
        
        if side == "opp":
            score = -score
        
        return score
    
    def _llm_value(self, battle: DoubleBattle, side: str) -> float:
        """LLM価値推定（プレースホルダー）"""
        # TODO: LLMクライアントで価値を推定
        return 0.0


# ============================================================================
# シングルトン
# ============================================================================

_evaluator: Optional[Evaluator] = None

def get_evaluator() -> Evaluator:
    """Evaluatorのシングルトンを取得"""
    global _evaluator
    if _evaluator is None:
        _evaluator = Evaluator()
    return _evaluator
