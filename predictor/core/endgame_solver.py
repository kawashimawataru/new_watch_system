"""
EndgameSolver - 終盤読み切りモード

残りポケモンが少ない（≤3体）場合、詰み探索を行う。
MCTS/サンプルではなく、より確実な読み切りを目指す。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import itertools

try:
    from poke_env.environment.double_battle import DoubleBattle
except ImportError:
    DoubleBattle = None


@dataclass
class EndgameResult:
    """終盤読み切りの結果"""
    
    is_winning: bool                     # 勝ち確定か
    is_losing: bool                      # 負け確定か
    best_action: Dict[str, Any]          # 最善手
    win_probability: float               # 勝率（読み切れなかった場合）
    depth_searched: int                  # 探索した深さ
    reasoning: str                       # 読み切りの理由


class EndgameSolver:
    """
    終盤読み切りソルバー
    
    残りポケモンが少ない場合、通常の探索ではなく詰み探索を行う。
    
    使用例:
    ```python
    solver = EndgameSolver()
    
    if solver.should_use_endgame(battle):
        result = solver.solve(battle)
        if result.is_winning:
            # 勝ち確定の最善手を選択
            return result.best_action
    ```
    """
    
    def __init__(
        self,
        max_remaining: int = 3,     # 終盤モードを発動する残り最大数
        max_depth: int = 10,         # 最大探索深さ
    ):
        self.max_remaining = max_remaining
        self.max_depth = max_depth
    
    def should_use_endgame(self, battle: DoubleBattle) -> bool:
        """終盤読み切りモードを使うべきか判定"""
        if not battle:
            return False
        
        # 両者の残りポケモン数
        my_remaining = self._count_remaining(battle, "self")
        opp_remaining = self._count_remaining(battle, "opp")
        
        # 両者合計が閾値以下なら終盤
        total = my_remaining + opp_remaining
        return total <= self.max_remaining * 2  # 例: 3体ずつなら合計6体以下
    
    def solve(
        self,
        battle: DoubleBattle,
        evaluator=None,
    ) -> EndgameResult:
        """
        終盤の読み切りを実行
        
        Args:
            battle: 現在のバトル状態
            evaluator: 局面評価関数（なければ簡易評価）
        
        Returns:
            EndgameResult: 読み切り結果
        """
        my_remaining = self._count_remaining(battle, "self")
        opp_remaining = self._count_remaining(battle, "opp")
        
        # 即座に勝敗が決まるケース
        if opp_remaining == 0:
            return EndgameResult(
                is_winning=True,
                is_losing=False,
                best_action={},
                win_probability=1.0,
                depth_searched=0,
                reasoning="相手のポケモンが全滅"
            )
        
        if my_remaining == 0:
            return EndgameResult(
                is_winning=False,
                is_losing=True,
                best_action={},
                win_probability=0.0,
                depth_searched=0,
                reasoning="自分のポケモンが全滅"
            )
        
        # 終盤の戦況分析
        analysis = self._analyze_endgame(battle)
        
        # 有利/不利の判定
        if analysis["advantage_score"] > 0.7:
            return EndgameResult(
                is_winning=True,
                is_losing=False,
                best_action=analysis["recommended_action"],
                win_probability=analysis["advantage_score"],
                depth_searched=1,
                reasoning=analysis["reasoning"]
            )
        elif analysis["advantage_score"] < 0.3:
            return EndgameResult(
                is_winning=False,
                is_losing=True,
                best_action=analysis["recommended_action"],
                win_probability=analysis["advantage_score"],
                depth_searched=1,
                reasoning=analysis["reasoning"]
            )
        else:
            return EndgameResult(
                is_winning=False,
                is_losing=False,
                best_action=analysis["recommended_action"],
                win_probability=analysis["advantage_score"],
                depth_searched=1,
                reasoning=analysis["reasoning"]
            )
    
    def _count_remaining(self, battle: DoubleBattle, side: str) -> int:
        """残りポケモン数をカウント"""
        team = battle.team if side == "self" else battle.opponent_team
        return sum(1 for p in team.values() if p and not p.fainted)
    
    def _analyze_endgame(self, battle: DoubleBattle) -> Dict[str, Any]:
        """終盤の戦況を分析"""
        my_remaining = self._count_remaining(battle, "self")
        opp_remaining = self._count_remaining(battle, "opp")
        
        # HP合計比較
        my_hp_total = sum(
            p.current_hp_fraction for p in battle.team.values() 
            if p and not p.fainted
        )
        opp_hp_total = sum(
            p.current_hp_fraction for p in battle.opponent_team.values() 
            if p and not p.fainted
        )
        
        # 頭数比較スコア
        count_score = 0.5
        if my_remaining > opp_remaining:
            count_score = 0.6 + 0.1 * (my_remaining - opp_remaining)
        elif my_remaining < opp_remaining:
            count_score = 0.4 - 0.1 * (opp_remaining - my_remaining)
        
        # HP比較スコア
        hp_score = 0.5
        total_hp = my_hp_total + opp_hp_total
        if total_hp > 0:
            hp_score = my_hp_total / total_hp
        
        # 総合スコア
        advantage_score = min(1.0, max(0.0, (count_score + hp_score) / 2))
        
        # 推奨行動
        recommended_action = self._get_recommended_action(battle, advantage_score)
        
        # 理由
        if advantage_score > 0.6:
            reasoning = f"頭数{my_remaining}:{opp_remaining}、HP{my_hp_total:.1f}:{opp_hp_total:.1f}で有利"
        elif advantage_score < 0.4:
            reasoning = f"頭数{my_remaining}:{opp_remaining}、HP{my_hp_total:.1f}:{opp_hp_total:.1f}で不利"
        else:
            reasoning = f"頭数{my_remaining}:{opp_remaining}、HP{my_hp_total:.1f}:{opp_hp_total:.1f}で互角"
        
        return {
            "advantage_score": advantage_score,
            "recommended_action": recommended_action,
            "reasoning": reasoning,
            "my_remaining": my_remaining,
            "opp_remaining": opp_remaining,
        }
    
    def _get_recommended_action(self, battle: DoubleBattle, advantage_score: float) -> Dict[str, Any]:
        """終盤の推奨行動を取得"""
        # 有利時: 安定行動（守りつつ削る）
        if advantage_score > 0.6:
            return {
                "strategy": "secure",
                "description": "有利を固める（安定行動）",
                "prefer_protect": False,  # 有利時は守らなくても良い
                "prefer_switch": False,
            }
        
        # 不利時: 上振れ狙い
        elif advantage_score < 0.4:
            return {
                "strategy": "gamble",
                "description": "上振れを狙う（攻撃的）",
                "prefer_protect": False,
                "prefer_switch": False,
            }
        
        # 互角時: 標準
        else:
            return {
                "strategy": "neutral",
                "description": "通常の判断",
                "prefer_protect": True,
                "prefer_switch": True,
            }


# シングルトン
_endgame_solver: Optional[EndgameSolver] = None


def get_endgame_solver() -> EndgameSolver:
    """EndgameSolver のシングルトンを取得"""
    global _endgame_solver
    if _endgame_solver is None:
        _endgame_solver = EndgameSolver()
    return _endgame_solver
