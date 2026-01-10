"""
ConsistentTurnAdvisor - 自己整合版 TurnAdvisor

LLMは同じ入力でも毎回異なる出力を返すことがある（温度による）。
自己整合（Self-Consistency）は、複数回の出力から多数決を取ることでブレを抑制する。

概念:
  従来:
    LLM(prompt) → 1回の出力をそのまま使用

  自己整合:
    LLM(prompt) → 出力1: ["icywind", "makeitrain"]
    LLM(prompt) → 出力2: ["icywind", "protect"]  
    LLM(prompt) → 出力3: ["icywind", "heatwave"]
    
    投票結果: slot0 = "icywind" (3票), slot1 = "makeitrain" (1票), ...
    
    → slot0 は高信頼度、slot1 は低信頼度（探索に任せる）

References:
  - PokéLLMon: https://arxiv.org/abs/2402.01118
  - Self-Consistency: Wang et al., 2022
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set


# ============================================================================
# 出力データ構造
# ============================================================================

@dataclass
class ConsistentRecommendation:
    """自己整合による推奨結果"""
    
    # スロットごとの技と得票数
    slot0_votes: Dict[str, int] = field(default_factory=dict)
    slot1_votes: Dict[str, int] = field(default_factory=dict)
    
    # 信頼度（最多票 / 総票数）
    slot0_confidence: float = 0.0
    slot1_confidence: float = 0.0
    
    # 最終推奨（信頼度に応じて1〜3個）
    slot0_moves: List[str] = field(default_factory=list)
    slot1_moves: List[str] = field(default_factory=list)
    
    # 各LLM出力のplan_alignment平均
    avg_plan_alignment: float = 0.0
    
    # LLMの reasoning（最も信頼度の高いもの）
    best_reasoning: str = ""
    
    def get_recommended_moves(self) -> Dict[int, Set[str]]:
        """GameSolver用のフォーマットで推奨技を取得"""
        return {
            0: set(m.lower() for m in self.slot0_moves),
            1: set(m.lower() for m in self.slot1_moves),
        }
    
    def to_summary(self) -> str:
        """デバッグ用サマリー"""
        lines = ["=== ConsistentRecommendation ==="]
        
        lines.append(f"\nSlot 0 (信頼度: {self.slot0_confidence:.0%}):")
        for move, votes in sorted(self.slot0_votes.items(), key=lambda x: -x[1]):
            selected = "✓" if move in self.slot0_moves else " "
            lines.append(f"  [{selected}] {move}: {votes}票")
        
        lines.append(f"\nSlot 1 (信頼度: {self.slot1_confidence:.0%}):")
        for move, votes in sorted(self.slot1_votes.items(), key=lambda x: -x[1]):
            selected = "✓" if move in self.slot1_moves else " "
            lines.append(f"  [{selected}] {move}: {votes}票")
        
        lines.append(f"\nPlan Alignment: {self.avg_plan_alignment:.0%}")
        
        return "\n".join(lines)


# ============================================================================
# ConsistentTurnAdvisor
# ============================================================================

class ConsistentTurnAdvisor:
    """
    自己整合版 TurnAdvisor
    
    N回LLMを呼び出し、投票結果から推奨を決定する。
    """
    
    def __init__(
        self, 
        llm_client: Any,
        n_samples: int = 3,
        high_confidence_threshold: float = 0.66
    ):
        """
        Args:
            llm_client: OpenAI client
            n_samples: LLM呼び出し回数
            high_confidence_threshold: この割合以上の票で「高信頼度」
        """
        self.llm_client = llm_client
        self.n_samples = n_samples
        self.high_confidence_threshold = high_confidence_threshold
        
        # 基本TurnAdvisorをインポート
        try:
            from predictor.core.turn_advisor import TurnAdvisor
            self.base_advisor = TurnAdvisor(llm_client=llm_client)
        except ImportError:
            self.base_advisor = None
    
    def advise(self, battle: Any, game_plan: Any = None) -> ConsistentRecommendation:
        """
        N回LLMを呼び出し、投票結果を返す
        
        Args:
            battle: DoubleBattle オブジェクト
            game_plan: GamePlan オブジェクト（オプション）
        
        Returns:
            ConsistentRecommendation
        """
        if self.base_advisor is None:
            return self._fallback_recommendation()
        
        recommendations = []
        plan_alignments = []
        
        for i in range(self.n_samples):
            try:
                rec = self.base_advisor.advise(battle, game_plan)
                if rec:
                    recommendations.append(rec)
                    if hasattr(rec, 'plan_alignment'):
                        plan_alignments.append(rec.plan_alignment)
            except Exception as e:
                print(f"  ⚠️ TurnAdvisor call {i+1} failed: {e}")
                continue
        
        if not recommendations:
            return self._fallback_recommendation()
        
        # 投票集計
        slot0_votes = defaultdict(int)
        slot1_votes = defaultdict(int)
        
        for rec in recommendations:
            if hasattr(rec, 'slot0_moves'):
                for move in rec.slot0_moves:
                    slot0_votes[move.lower()] += 1
            if hasattr(rec, 'slot1_moves'):
                for move in rec.slot1_moves:
                    slot1_votes[move.lower()] += 1
        
        # 信頼度計算
        total_votes = len(recommendations)
        slot0_confidence = max(slot0_votes.values()) / total_votes if slot0_votes else 0
        slot1_confidence = max(slot1_votes.values()) / total_votes if slot1_votes else 0
        
        # 信頼度に応じて推奨を決定
        slot0_moves = self._select_moves(slot0_votes, slot0_confidence, total_votes)
        slot1_moves = self._select_moves(slot1_votes, slot1_confidence, total_votes)
        
        # plan_alignment 平均
        avg_plan_alignment = sum(plan_alignments) / len(plan_alignments) if plan_alignments else 0.5
        
        # 最良の reasoning を取得
        best_reasoning = ""
        if recommendations and hasattr(recommendations[0], 'reasoning'):
            best_reasoning = recommendations[0].reasoning
        
        result = ConsistentRecommendation(
            slot0_votes=dict(slot0_votes),
            slot1_votes=dict(slot1_votes),
            slot0_confidence=slot0_confidence,
            slot1_confidence=slot1_confidence,
            slot0_moves=slot0_moves,
            slot1_moves=slot1_moves,
            avg_plan_alignment=avg_plan_alignment,
            best_reasoning=best_reasoning,
        )
        
        print(result.to_summary())
        
        return result
    
    def _select_moves(
        self, 
        votes: Dict[str, int], 
        confidence: float,
        total_votes: int
    ) -> List[str]:
        """
        信頼度に応じて推奨技を選択
        
        高信頼度（>= 2/3）: 最多票のみ
        低信頼度: 上位2-3個
        """
        if not votes:
            return []
        
        sorted_moves = sorted(votes.items(), key=lambda x: -x[1])
        
        if confidence >= self.high_confidence_threshold:
            # 高信頼度: 最多票のみ
            max_votes = sorted_moves[0][1]
            return [m for m, v in sorted_moves if v == max_votes]
        else:
            # 低信頼度: 上位2-3個
            return [m for m, _ in sorted_moves[:3]]
    
    def _fallback_recommendation(self) -> ConsistentRecommendation:
        """LLM呼び出しが失敗した場合のフォールバック"""
        return ConsistentRecommendation(
            slot0_moves=["protect"],  # 安全策
            slot1_moves=["protect"],
            slot0_confidence=0.0,
            slot1_confidence=0.0,
            avg_plan_alignment=0.0,
        )
    
    def get_adjusted_solver_config(
        self, 
        recommendation: ConsistentRecommendation
    ) -> Dict[str, Any]:
        """
        plan_alignment に応じて探索の設定を調整
        
        plan_alignment が高い → LLM候補を信頼、探索は軽め
        plan_alignment が低い → LLM候補を参考程度、探索をしっかり
        
        Returns:
            SolverConfig に渡すパラメータ辞書
        """
        alignment = recommendation.avg_plan_alignment
        
        if alignment >= 0.8:
            # LLM候補を強く信頼
            return {
                "top_k_self": 5,
                "depth": 2,
                "n_samples": 8,
            }
        elif alignment >= 0.5:
            # 普通
            return {
                "top_k_self": 15,
                "depth": 3,
                "n_samples": 12,
            }
        else:
            # LLMに懐疑的、探索を重視
            return {
                "top_k_self": 25,
                "depth": 3,
                "n_samples": 16,
            }


# ============================================================================
# シングルトン
# ============================================================================

_consistent_advisor: Optional[ConsistentTurnAdvisor] = None

def get_consistent_turn_advisor(llm_client: Any = None) -> ConsistentTurnAdvisor:
    """ConsistentTurnAdvisor のシングルトンを取得"""
    global _consistent_advisor
    if _consistent_advisor is None and llm_client is not None:
        _consistent_advisor = ConsistentTurnAdvisor(llm_client=llm_client)
    return _consistent_advisor
