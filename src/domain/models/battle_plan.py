"""
Battle Plan - バトルプランモデル

バトル開始時に立てた戦略を保持するValue Object。
LLMに「プランに沿った行動」を促すために使用。
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class PlanPhase(Enum):
    """プランのフェーズ"""
    OPENING = "opening"      # 序盤: 選出・初動
    MIDGAME = "midgame"      # 中盤: 削り・崩し
    CLOSING = "closing"      # 終盤: 詰め
    EMERGENCY = "emergency"  # 緊急: 逆転を狙う


@dataclass
class BattlePlan:
    """
    バトルプラン
    
    バトル開始時（選出後）に策定し、ターンごとに進捗を追跡する。
    """
    
    # 勝利条件
    win_condition: str = ""
    # 例: "バドレックスを処理して数的有利を取る"
    
    # 優先ターゲット
    priority_targets: List[str] = field(default_factory=list)
    # 例: ["バドレックス", "イエッサン"]
    
    # 温存すべきポケモン
    key_pokemon: Optional[str] = None
    # 例: "テラパゴスは詰め用に温存"
    
    # テラスタル計画
    terastal_plan: str = ""
    # 例: "テラパゴスのステラテラスは相手テラスを見てから切る"
    
    # リスク要因
    risk_factors: List[str] = field(default_factory=list)
    # 例: ["トリックルーム展開", "ゴリランダー着地"]
    
    # 現在のフェーズ
    current_phase: PlanPhase = PlanPhase.OPENING
    
    # 選出
    selected_pokemon: List[str] = field(default_factory=list)
    # 例: ["テラパゴス", "ガオガエン", "モロバレル", "オーガポン"]
    
    # 初動の方針
    opening_strategy: str = ""
    # 例: "ガオガエン+テラパゴス先発。猫+テラクラで削り。"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "win_condition": self.win_condition,
            "priority_targets": self.priority_targets,
            "key_pokemon": self.key_pokemon,
            "terastal_plan": self.terastal_plan,
            "risk_factors": self.risk_factors,
            "current_phase": self.current_phase.value,
            "selected_pokemon": self.selected_pokemon,
            "opening_strategy": self.opening_strategy,
        }
    
    def to_prompt_text(self) -> str:
        """LLMプロンプト用のテキスト"""
        lines = [
            "【バトルプラン】",
            f"勝利条件: {self.win_condition}",
            f"優先ターゲット: {', '.join(self.priority_targets)}",
        ]
        
        if self.key_pokemon:
            lines.append(f"温存ポケモン: {self.key_pokemon}")
        
        if self.terastal_plan:
            lines.append(f"テラスタル計画: {self.terastal_plan}")
        
        if self.risk_factors:
            lines.append(f"リスク要因: {', '.join(self.risk_factors)}")
        
        lines.append(f"現在フェーズ: {self._phase_to_japanese()}")
        
        return "\n".join(lines)
    
    def _phase_to_japanese(self) -> str:
        mapping = {
            PlanPhase.OPENING: "序盤（展開）",
            PlanPhase.MIDGAME: "中盤（崩し）",
            PlanPhase.CLOSING: "終盤（詰め）",
            PlanPhase.EMERGENCY: "緊急（逆転狙い）",
        }
        return mapping.get(self.current_phase, "不明")


@dataclass
class PlanStatus:
    """
    プランの進捗状況
    """
    
    # 進捗の説明
    progress: str = ""
    # 例: "バドレックスをHP30%まで削り完了"
    
    # プラン通りか
    on_track: bool = True
    
    # 調整が必要な場合の提案
    adjustments: Optional[str] = None
    # 例: "トリルに切り替わったため、プラン変更を推奨"
    
    # 達成済みのマイルストーン
    achieved_milestones: List[str] = field(default_factory=list)
    # 例: ["バドレックス処理", "数的有利確保"]
    
    # 残りの目標
    remaining_goals: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "progress": self.progress,
            "on_track": self.on_track,
            "adjustments": self.adjustments,
            "achieved_milestones": self.achieved_milestones,
            "remaining_goals": self.remaining_goals,
        }
    
    def to_prompt_text(self) -> str:
        """LLMプロンプト用のテキスト"""
        lines = ["【プラン進捗】"]
        lines.append(f"状況: {self.progress}")
        
        status = "✅ プラン通り" if self.on_track else "⚠️ 調整必要"
        lines.append(f"ステータス: {status}")
        
        if self.adjustments:
            lines.append(f"調整案: {self.adjustments}")
        
        if self.achieved_milestones:
            lines.append(f"達成済み: {', '.join(self.achieved_milestones)}")
        
        if self.remaining_goals:
            lines.append(f"残り目標: {', '.join(self.remaining_goals)}")
        
        return "\n".join(lines)


def create_initial_plan(
    my_team: List[str],
    opponent_team: List[str],
    selected: List[str],
) -> BattlePlan:
    """
    初期プランを作成（簡易ヒューリスティック）
    
    実際のバトルでは、LLMや選出アルゴリズムで生成することを想定。
    """
    plan = BattlePlan()
    plan.selected_pokemon = selected
    
    # 優先ターゲットの決定（仮: 相手の選出の最初のポケモン）
    if opponent_team:
        plan.priority_targets = opponent_team[:2]
    
    # 勝利条件の設定（仮）
    plan.win_condition = f"{plan.priority_targets[0] if plan.priority_targets else '相手エース'}を処理して数的有利を取る"
    
    # テラスタル計画（仮）
    plan.terastal_plan = "相手のテラスタルを見てから切る"
    
    # 初動（仮）
    if len(selected) >= 2:
        plan.opening_strategy = f"{selected[0]}と{selected[1]}で先発。様子を見つつ削る。"
    
    return plan
