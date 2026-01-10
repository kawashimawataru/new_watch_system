"""
Explainer - KAG説明生成

PokéChamp型アーキテクチャの説明モジュール。
根拠アンカーを生成し、LLMで日本語整形。

References:
- PokeLLMon: https://arxiv.org/abs/2402.01118 (KAG)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from predictor.core.game_solver import SolveResult, SwingPoint

try:
    from poke_env.environment.double_battle import DoubleBattle
except ImportError:
    try:
        from poke_env.battle import DoubleBattle
    except ImportError:
        DoubleBattle = None


# ============================================================================
# データ構造
# ============================================================================

@dataclass
class ExplanationAnchor:
    """根拠アンカー"""
    category: str       # "speed", "ko", "protection", "swing", "advantage"
    fact: str           # 具体的な事実
    impact: float       # 勝率への影響度


@dataclass
class ExplanationResult:
    """説明結果"""
    short: str                              # 短い説明（1-2文）
    anchors: List[ExplanationAnchor]        # 根拠アンカー
    self_action_explain: str                # 自分の行動の説明
    opp_action_explain: str                 # 相手の行動の説明


# ============================================================================
# Explainer
# ============================================================================

class Explainer:
    """
    KAG説明生成器
    
    1. 計算結果から根拠アンカーを生成
    2. LLMで日本語整形（オプション）
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        self.llm = llm_client
    
    def generate_anchors(
        self,
        battle: DoubleBattle,
        solve_result: SolveResult,
    ) -> List[ExplanationAnchor]:
        """
        計算結果から根拠アンカーを生成
        """
        anchors = []
        
        # 1. 勝率に関する根拠
        win_prob = solve_result.win_prob
        if win_prob > 0.7:
            anchors.append(ExplanationAnchor(
                category="advantage",
                fact=f"現在の勝率は{win_prob:.0%}と優勢",
                impact=win_prob - 0.5,
            ))
        elif win_prob < 0.3:
            anchors.append(ExplanationAnchor(
                category="advantage",
                fact=f"現在の勝率は{win_prob:.0%}と劣勢",
                impact=win_prob - 0.5,
            ))
        
        # 2. 最善手の根拠
        if solve_result.self_dist:
            best = solve_result.self_dist[0]
            if best.probability > 0.5:
                tags_str = "/".join(best.tags[:2]) if best.tags else "有効"
                anchors.append(ExplanationAnchor(
                    category="best_action",
                    fact=f"最善手は{best.action.slot0}（{tags_str}）",
                    impact=best.probability,
                ))
        
        # 3. 相手の予測行動
        if solve_result.opp_dist:
            top_opp = solve_result.opp_dist[0]
            if top_opp.probability > 0.3:
                anchors.append(ExplanationAnchor(
                    category="opponent_prediction",
                    fact=f"相手は{top_opp.action.slot0}を選ぶ可能性が{top_opp.probability:.0%}",
                    impact=top_opp.probability,
                ))
        
        # 4. 分岐点
        for swing in solve_result.swing_points[:2]:
            anchors.append(ExplanationAnchor(
                category="swing",
                fact=swing.description,
                impact=swing.impact,
            ))
        
        # 5. HP/残数差
        self_remaining = sum(1 for p in battle.team.values() if p and not p.fainted)
        opp_remaining = sum(1 for p in battle.opponent_team.values() if p and not p.fainted)
        if self_remaining != opp_remaining:
            diff = self_remaining - opp_remaining
            if diff > 0:
                anchors.append(ExplanationAnchor(
                    category="numbers",
                    fact=f"残数で{diff}体リード",
                    impact=diff * 0.1,
                ))
            else:
                anchors.append(ExplanationAnchor(
                    category="numbers",
                    fact=f"残数で{-diff}体ビハインド",
                    impact=diff * 0.1,
                ))
        
        return anchors
    
    def explain(
        self,
        battle: DoubleBattle,
        solve_result: SolveResult,
    ) -> ExplanationResult:
        """
        説明を生成
        """
        anchors = self.generate_anchors(battle, solve_result)
        
        # 短い説明を生成
        short = self._generate_short_explanation(anchors, solve_result)
        
        # 自分/相手の行動説明
        self_explain = self._explain_self_action(solve_result)
        opp_explain = self._explain_opp_action(solve_result)
        
        return ExplanationResult(
            short=short,
            anchors=anchors,
            self_action_explain=self_explain,
            opp_action_explain=opp_explain,
        )
    
    def _generate_short_explanation(
        self,
        anchors: List[ExplanationAnchor],
        solve_result: SolveResult,
    ) -> str:
        """短い説明を生成（LLMなしの場合はテンプレート）"""
        parts = []
        
        # 勝率
        win_prob = solve_result.win_prob
        if win_prob > 0.6:
            parts.append(f"勝率{win_prob:.0%}で優勢。")
        elif win_prob < 0.4:
            parts.append(f"勝率{win_prob:.0%}で劣勢。")
        else:
            parts.append(f"勝率{win_prob:.0%}の五分。")
        
        # 重要な根拠を1つ追加
        important = [a for a in anchors if abs(a.impact) > 0.1]
        if important:
            parts.append(important[0].fact + "。")
        
        return "".join(parts)
    
    def _explain_self_action(self, solve_result: SolveResult) -> str:
        """自分の行動を説明"""
        if not solve_result.self_dist:
            return ""
        
        best = solve_result.self_dist[0]
        prob = best.probability
        
        explanation = f"推奨行動: {best.action}"
        if best.tags:
            explanation += f" ({', '.join(best.tags[:2])})"
        explanation += f" / 選択率: {prob:.0%}"
        
        # 代替手があれば
        if len(solve_result.self_dist) > 1:
            alt = solve_result.self_dist[1]
            if alt.delta and abs(alt.delta) < 0.1:
                explanation += f"\n代替手: {alt.action} (Δ={alt.delta:+.1%})"
        
        return explanation
    
    def _explain_opp_action(self, solve_result: SolveResult) -> str:
        """相手の行動を説明"""
        if not solve_result.opp_dist:
            return ""
        
        lines = ["相手の予測行動:"]
        for i, opp in enumerate(solve_result.opp_dist[:3]):
            lines.append(f"  {i+1}. {opp.action} ({opp.probability:.0%})")
        
        return "\n".join(lines)
    
    async def explain_with_llm(
        self,
        battle: DoubleBattle,
        solve_result: SolveResult,
    ) -> ExplanationResult:
        """LLMを使って説明を生成（非同期）"""
        anchors = self.generate_anchors(battle, solve_result)
        
        short = self._generate_short_explanation(anchors, solve_result)
        
        # LLMで整形（利用可能な場合）
        if self.llm:
            try:
                anchor_texts = [a.fact for a in anchors]
                short = await self.llm.generate_explanation(anchor_texts)
            except Exception:
                pass
        
        return ExplanationResult(
            short=short,
            anchors=anchors,
            self_action_explain=self._explain_self_action(solve_result),
            opp_action_explain=self._explain_opp_action(solve_result),
        )


# ============================================================================
# シングルトン
# ============================================================================

_explainer: Optional[Explainer] = None

def get_explainer() -> Explainer:
    """Explainerのシングルトンを取得"""
    global _explainer
    if _explainer is None:
        _explainer = Explainer()
    return _explainer
