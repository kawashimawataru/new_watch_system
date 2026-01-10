"""Lightweight heuristic evaluation for quick recommendations."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List, Sequence

from predictor.core.models import (
    ActionCandidate,
    ActionScore,
    BattleState,
    EvaluationResult,
    PlayerEvaluation,
    PokemonRecommendation,
)


class HeuristicEvaluator:
    """
    Implements the plan described as Algorithm A in the spec.
    
    Phase D 統合: 脅威度評価とプラン遂行度スコアを追加
    """

    def __init__(
        self,
        weights: Dict[str, float] | None = None,
        game_plan = None  # Phase D: GamePlan 参照
    ):
        self.weights = weights or {
            "hp": 3.0,
            "status": 0.75,
            "reserves": 0.5,
            "speed": 0.25,
            "field": 0.4,
            # Phase D: 新規追加
            "threat": 1.0,        # 脅威度評価
            "plan_progress": 0.8,  # プラン遂行度
        }
        self.tag_bonus = {
            "protect": 0.5,
            "spread": 0.35,
            "priority": 0.2,
            "speed_control": 0.35,
            "boost": 0.3,
            "pivot": 0.25,
        }
        
        # Phase D: GamePlan 参照
        self.game_plan = game_plan

    def evaluate(self, battle_state: BattleState) -> EvaluationResult:
        """Return win rates and action suggestions for both players."""

        board_score = self._state_value(battle_state)
        win_rate_a = self._sigmoid(board_score)
        win_rate_b = 1.0 - win_rate_a

        rec_a = self._score_actions("A", battle_state)
        rec_b = self._score_actions("B", battle_state)

        return EvaluationResult(
            player_a=PlayerEvaluation(win_rate=win_rate_a, active=rec_a),
            player_b=PlayerEvaluation(win_rate=win_rate_b, active=rec_b),
        )

    def _state_value(self, state: BattleState) -> float:
        """
        盤面価値を計算
        
        Phase D 統合:
        - 脅威度評価: 相手の主要脅威が残っているほど不利
        - プラン遂行度: 自分のKOターゲットを処理できているほど有利
        """
        hp_a = sum(p.hp_fraction for p in state.player_a.active)
        hp_b = sum(p.hp_fraction for p in state.player_b.active)
        reserves_a = len(state.player_a.reserves)
        reserves_b = len(state.player_b.reserves)
        status_a = sum(1 for p in state.player_a.active if p.status)
        status_b = sum(1 for p in state.player_b.active if p.status)
        speed_a = sum(p.boosts.get("spe", 0) for p in state.player_a.active)
        speed_b = sum(p.boosts.get("spe", 0) for p in state.player_b.active)

        field_bonus = 0.0
        if state.room == "trick":
            field_bonus += 0.3
        if state.weather in {"rain", "sun"}:
            field_bonus += 0.1

        value = 0.0
        value += self.weights["hp"] * (hp_a - hp_b)
        value += self.weights["status"] * (status_b - status_a)
        value += self.weights["reserves"] * (reserves_a - reserves_b)
        value += self.weights["speed"] * (speed_a - speed_b)
        value += self.weights["field"] * field_bonus
        value += state.player_a.score_bias - state.player_b.score_bias
        
        # ============= Phase D: 脅威度評価 =============
        # 相手の主要脅威が残っているほど不利
        if self.game_plan and hasattr(self.game_plan, 'primary_threats'):
            threat_penalty = 0.0
            for threat_name in self.game_plan.primary_threats:
                # 相手のアクティブ・控えに脅威がいるかチェック
                threat_alive = False
                for p in state.player_b.active:
                    if p.name.lower() == threat_name.lower() and p.hp_fraction > 0:
                        # 脅威がアクティブで高HPなら大きなペナルティ
                        threat_penalty += p.hp_fraction * 0.5
                        threat_alive = True
                        break
                
                if not threat_alive:
                    for p in state.player_b.reserves:
                        if hasattr(p, 'name') and p.name.lower() == threat_name.lower():
                            threat_penalty += 0.3  # 控えに脅威
                            break
            
            value -= self.weights.get("threat", 1.0) * threat_penalty
        
        # ============= Phase D: プラン遂行度スコア =============
        # KOターゲットを処理できているほど有利
        if self.game_plan and hasattr(self.game_plan, 'ko_routes'):
            plan_progress = 0.0
            for target_name in self.game_plan.ko_routes.keys():
                # ターゲットが倒れているかチェック
                target_defeated = True
                for p in state.player_b.active:
                    if p.name.lower() == target_name.lower() and p.hp_fraction > 0:
                        target_defeated = False
                        break
                
                if target_defeated:
                    for p in state.player_b.reserves:
                        if hasattr(p, 'name') and p.name.lower() == target_name.lower():
                            target_defeated = False
                            break
                
                if target_defeated:
                    plan_progress += 0.5  # ターゲット処理完了
            
            value += self.weights.get("plan_progress", 0.8) * plan_progress
        
        return value

    def _score_actions(self, player_label: str, state: BattleState) -> List[PokemonRecommendation]:
        actions = state.legal_actions.get(player_label)
        if not actions:
            return self._fallback_recommendations(
                state.player_a if player_label == "A" else state.player_b
            )

        per_actor: Dict[str, List[ActionScore]] = defaultdict(list)
        for action in actions:
            score = self._score_action_candidate(action)
            per_actor[action.actor].append(
                ActionScore(move=action.move, target=action.target, score=score)
            )

        recommendations = []
        for actor, move_scores in per_actor.items():
            normalized = self._normalize_scores(move_scores)
            recommendations.append(
                PokemonRecommendation(name=actor, suggested_moves=normalized)
            )
        return recommendations

    def _score_action_candidate(self, action: ActionCandidate) -> float:
        """
        アクション候補のスコアを計算
        
        Phase 4.3: Consistent Action Generation
        - パニック交代のペナルティ（HP高いのに交代）
        - 連続Protectのペナルティ
        - 無効技の回避
        """
        score = 0.1  # base prior to avoid zeros
        for tag in action.tags:
            score += self.tag_bonus.get(tag, 0.0)
        if action.metadata.get("is_stab"):
            score += 0.2
        if action.metadata.get("is_super_effective"):
            score += 0.35
        if action.metadata.get("coverage_multiplier"):
            score += 0.1 * action.metadata["coverage_multiplier"]
        if damage := action.metadata.get("estimatedDamage"):
            score += 0.4 * damage.get("koChance", 0.0)
            score += 0.1 * (damage.get("maxPercent", 0.0) / 100.0)
            score += 0.05 * damage.get("hitChance", 0.0)
        if action.target and "slot2" in action.target:
            score += 0.05  # encourage spread coverage on the second slot
        
        # === Consistent Action Generation (Phase 4.3) ===
        
        # 交代ペナルティ（HP が高いのに交代はパニック交代とみなす）
        if action.metadata.get("is_switch"):
            actor_hp = action.metadata.get("actor_hp_fraction", 1.0)
            if actor_hp > 0.7:
                # HPが70%以上で交代は大幅減点（パニック交代）
                score -= 0.4
            elif actor_hp > 0.4:
                # 中程度のHPでは軽めのペナルティ
                score -= 0.15
            else:
                # HPが低い場合の交代は妥当
                score -= 0.05
        
        # 連続Protect使用のペナルティ
        if action.move and action.move.lower() == "protect":
            consecutive_protects = action.metadata.get("consecutive_protects", 0)
            if consecutive_protects > 0:
                # 連続使用すると成功率が下がる（1/3 → 1/9 → ...）
                score -= 0.3 * consecutive_protects
        
        # 無効技の回避（タイプ相性・特性）
        if action.metadata.get("is_immune"):
            score -= 1.0  # 無効技は大幅減点
        
        # いまひとつの技はやや減点
        if action.metadata.get("is_not_very_effective"):
            score -= 0.15
        
        return max(score, 0.01)

    @staticmethod
    def _normalize_scores(scores: Sequence[ActionScore]) -> List[ActionScore]:
        total = sum(max(s.score, 0.0) for s in scores)
        if total <= 0:
            uniform = 1.0 / len(scores) if scores else 0.0
            return [ActionScore(move=s.move, target=s.target, score=uniform) for s in scores]
        return [
            ActionScore(move=s.move, target=s.target, score=max(s.score, 0.0) / total)
            for s in scores
        ]

    @staticmethod
    def _fallback_recommendations(player_state) -> List[PokemonRecommendation]:
        recommendations = []
        for pokemon in player_state.active:
            recommendations.append(
                PokemonRecommendation(
                    name=pokemon.name,
                    suggested_moves=[ActionScore(move="Struggle", target=None, score=1.0)],
                )
            )
        return recommendations

    @staticmethod
    def _sigmoid(value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))
    
    def get_action_weights(self, state: BattleState, actions: List[ActionCandidate]) -> List[float]:
        """
        Guided Playouts用にアクションの重みを計算
        
        MCTSシミュレーション中に使用される。
        完全にランダムではなく、より有望な手を優先的に選択するための重み付け。
        
        Args:
            state: 現在のバトル状態
            actions: アクション候補リスト
        
        Returns:
            各アクションの選択確率（合計1.0）
        """
        if not actions:
            return []
        
        scores = []
        for action in actions:
            score = self._score_action_candidate(action)
            
            # === Phase 3 追加評価 ===
            # 残りHP低下時の先制技ボーナス
            actor_name = action.actor
            actor_hp = 1.0
            for p in state.player_a.active:
                if p.name == actor_name:
                    actor_hp = p.hp_fraction
                    break
            
            # HP低い時に先制技を優遇
            if "priority" in action.tags and actor_hp < 0.4:
                score += 0.3
            
            # Protectは連続使用で失敗しやすいが、初回は高評価
            if action.move and action.move.lower() == "protect":
                score += 0.15
            
            # 味方殴りの技は低評価（味方対象の場合）
            if action.target and "ally" in str(action.target).lower():
                score -= 0.3
            
            scores.append(max(score, 0.01))  # 最低値を保証
        
        # Softmax風の正規化（より高いスコアを優先しつつ、探索も維持）
        # 温度パラメータを適用（低いほど最良手に集中）
        temperature = 0.5
        exp_scores = [math.exp(s / temperature) for s in scores]
        total = sum(exp_scores)
        
        if total <= 0:
            uniform = 1.0 / len(actions)
            return [uniform] * len(actions)
        
        return [s / total for s in exp_scores]

