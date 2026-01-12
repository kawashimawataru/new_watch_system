"""
Plan Tracker - プラン進捗追跡サービス

BattlePlanの進捗を追跡し、プランに沿っているかを評価する。
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from src.domain.models.battle_plan import BattlePlan, PlanStatus, PlanPhase


class PlanTracker:
    """
    バトルプランの進捗を追跡するサービス
    """
    
    def __init__(self):
        self._current_plan: Optional[BattlePlan] = None
        self._milestones: List[str] = []
        self._turn_history: List[Dict[str, Any]] = []
    
    def set_plan(self, plan: BattlePlan) -> None:
        """プランを設定"""
        self._current_plan = plan
        self._milestones = []
        self._turn_history = []
    
    def get_plan(self) -> Optional[BattlePlan]:
        """現在のプランを取得"""
        return self._current_plan
    
    def evaluate(
        self,
        player_pokemon: List[Dict[str, Any]],
        opponent_pokemon: List[Dict[str, Any]],
        turn: int,
    ) -> PlanStatus:
        """
        現在の盤面とプランを比較して進捗を評価
        
        Args:
            player_pokemon: 自分のポケモン (name, hp_fraction, fainted)
            opponent_pokemon: 相手のポケモン
            turn: 現在のターン
        
        Returns:
            PlanStatus
        """
        if not self._current_plan:
            return PlanStatus(
                progress="プラン未設定",
                on_track=True,
            )
        
        plan = self._current_plan
        status = PlanStatus()
        
        # 優先ターゲットの処理状況
        target_status = self._check_target_status(opponent_pokemon, plan.priority_targets)
        
        # フェーズ判定
        current_phase = self._determine_phase(
            player_pokemon, opponent_pokemon, turn
        )
        plan.current_phase = current_phase
        
        # プラン通りかの判定
        on_track, adjustments = self._check_plan_adherence(
            player_pokemon, opponent_pokemon, plan, target_status
        )
        
        status.progress = target_status
        status.on_track = on_track
        status.adjustments = adjustments
        status.achieved_milestones = list(self._milestones)
        status.remaining_goals = self._get_remaining_goals(plan, opponent_pokemon)
        
        return status
    
    def _check_target_status(
        self,
        opponent_pokemon: List[Dict],
        targets: List[str],
    ) -> str:
        """優先ターゲットの状態を確認"""
        parts = []
        
        for target in targets:
            for poke in opponent_pokemon:
                name = poke.get("name", "").lower()
                if target.lower() in name:
                    hp = poke.get("hp_fraction", 1.0)
                    fainted = poke.get("fainted", False)
                    
                    if fainted:
                        parts.append(f"{target}は処理済み ✅")
                        if target not in self._milestones:
                            self._milestones.append(f"{target}処理")
                    elif hp <= 0.3:
                        parts.append(f"{target}はHP30%以下（処理可能）")
                    elif hp <= 0.5:
                        parts.append(f"{target}はHP50%程度")
                    else:
                        parts.append(f"{target}はHP{int(hp*100)}%")
                    break
        
        return " / ".join(parts) if parts else "ターゲット情報なし"
    
    def _determine_phase(
        self,
        player_pokemon: List[Dict],
        opponent_pokemon: List[Dict],
        turn: int,
    ) -> PlanPhase:
        """現在のフェーズを判定"""
        # カウント
        player_alive = sum(1 for p in player_pokemon if not p.get("fainted", False))
        opponent_alive = sum(1 for p in opponent_pokemon if not p.get("fainted", False))
        
        # 序盤: ターン1-3
        if turn <= 3:
            return PlanPhase.OPENING
        
        # 緊急: 自分が数的不利
        if player_alive < opponent_alive:
            return PlanPhase.EMERGENCY
        
        # 終盤: 相手が残り2体以下、または自分が数的有利
        if opponent_alive <= 2 or player_alive > opponent_alive:
            return PlanPhase.CLOSING
        
        # 中盤
        return PlanPhase.MIDGAME
    
    def _check_plan_adherence(
        self,
        player_pokemon: List[Dict],
        opponent_pokemon: List[Dict],
        plan: BattlePlan,
        target_status: str,
    ) -> tuple[bool, Optional[str]]:
        """プランに沿っているかチェック"""
        
        # 温存ポケモンのチェック
        if plan.key_pokemon:
            for poke in player_pokemon:
                if plan.key_pokemon.lower() in poke.get("name", "").lower():
                    if poke.get("fainted", False):
                        return False, f"温存予定の{plan.key_pokemon}が倒された。プラン変更を推奨。"
        
        # 処理済みでないターゲットがまだ健在かチェック
        all_targets_handled = all(
            "処理済み" in target_status or "HP30%以下" in target_status
            for target in plan.priority_targets
            if target in target_status
        )
        
        # 緊急フェーズでプラン変更を推奨
        if plan.current_phase == PlanPhase.EMERGENCY:
            return False, "数的不利のため、逆転プランへの切り替えを推奨"
        
        return True, None
    
    def _get_remaining_goals(
        self,
        plan: BattlePlan,
        opponent_pokemon: List[Dict],
    ) -> List[str]:
        """残りの目標を取得"""
        remaining = []
        
        for target in plan.priority_targets:
            # まだ処理されていないターゲット
            if f"{target}処理" not in self._milestones:
                remaining.append(f"{target}を処理")
        
        if not remaining:
            remaining.append("残りの相手を処理して勝利")
        
        return remaining
    
    def record_turn(self, turn_data: Dict[str, Any]) -> None:
        """ターンの記録を追加"""
        self._turn_history.append(turn_data)


# Singleton
_plan_tracker = None

def get_plan_tracker() -> PlanTracker:
    global _plan_tracker
    if _plan_tracker is None:
        _plan_tracker = PlanTracker()
    return _plan_tracker
