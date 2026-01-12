"""
Explanation Generator - LLM解説生成器

CandidateScorerの結果を受け取り、LLMで解説を生成する。
LLMは候補手を決めるのではなく、「なぜこの手が良いか」を解説するだけ。
"""

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.domain.services.candidate_scorer import ScoredCandidate


@dataclass
class BattleExplanation:
    """バトル解説"""
    current_situation: str          # 現在の状況説明
    recommended_strategy: str       # 推奨戦略
    top_candidate_reason: str       # トップ候補の理由
    risk_analysis: str              # リスク分析
    opponent_prediction: str        # 相手の予測
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_situation": self.current_situation,
            "recommended_strategy": self.recommended_strategy,
            "top_candidate_reason": self.top_candidate_reason,
            "risk_analysis": self.risk_analysis,
            "opponent_prediction": self.opponent_prediction,
        }


class ExplanationGenerator:
    """
    観戦AI用解説生成器
    
    CandidateScorerの結果を受け取り、LLMで解説を生成する。
    候補手の決定には関与しない。
    """
    
    SYSTEM_PROMPT = """あなたはVGCダブルバトルの実況解説者です。

与えられた候補手のスコアリング結果に基づいて、視聴者に分かりやすく解説してください。

重要なルール:
1. 候補手の選択はAIが既に行っています。あなたは「なぜこの手が良いか」を解説するだけです。
2. タイプ相性や素早さの計算は既に行われています。その結果を信頼してください。
3. 視聴者が楽しめるように、ドラマチックに解説してください。
4. 日本語で回答してください。

回答は以下のJSON形式で:
{
    "current_situation": "現在の盤面状況を1文で",
    "recommended_strategy": "推奨戦略を1文で",
    "top_candidate_reason": "トップ候補がなぜ良いかを2文で",
    "risk_analysis": "リスクを1文で",
    "opponent_prediction": "相手の動きを1文で予測"
}
"""
    
    def __init__(self, use_openai: bool = True):
        self.use_openai = use_openai
        self._openai_client = None
    
    def _get_openai_client(self):
        """OpenAI clientを遅延初期化"""
        if self._openai_client is None and self.use_openai:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI()
            except ImportError:
                print("OpenAI package not installed. Using fallback.")
                self.use_openai = False
        return self._openai_client
    
    def generate(
        self,
        candidates: List[ScoredCandidate],
        player_active: List[Dict[str, Any]],
        opponent_active: List[Dict[str, Any]],
        turn: int = 1,
    ) -> BattleExplanation:
        """
        候補手に対する解説を生成
        
        Args:
            candidates: スコア付き候補手リスト
            player_active: 自分の場のポケモン
            opponent_active: 相手の場のポケモン
            turn: 現在のターン
        
        Returns:
            BattleExplanation
        """
        # プロンプト構築
        prompt = self._build_prompt(candidates, player_active, opponent_active, turn)
        
        # LLM呼び出し
        if self.use_openai:
            return self._call_openai(prompt)
        else:
            return self._fallback_explanation(candidates)
    
    def _build_prompt(
        self,
        candidates: List[ScoredCandidate],
        player_active: List[Dict],
        opponent_active: List[Dict],
        turn: int,
    ) -> str:
        """LLMプロンプトを構築"""
        sections = []
        
        # 現在の盤面
        sections.append(f"【ターン {turn}】")
        sections.append("自分:")
        for p in player_active:
            hp = int(p.get("hp_fraction", 1.0) * 100)
            sections.append(f"  {p.get('name', 'ポケモン')}: HP {hp}%")
        
        sections.append("相手:")
        for o in opponent_active:
            hp = int(o.get("hp_fraction", 1.0) * 100)
            sections.append(f"  {o.get('name', 'ポケモン')}: HP {hp}%")
        
        # 候補手（スコア付き）
        sections.append("")
        sections.append("【AI候補手（スコア順）】")
        for i, c in enumerate(candidates[:3], 1):
            sections.append(
                f"{i}. {c.move1} + {c.move2} "
                f"(スコア: {c.score:.0f}, リスク: {c.risk_level})"
            )
            if c.reasoning_hint:
                sections.append(f"   ヒント: {c.reasoning_hint}")
        
        sections.append("")
        sections.append("上記の候補手を視聴者に解説してください。")
        
        return "\n".join(sections)
    
    def _call_openai(self, prompt: str) -> BattleExplanation:
        """OpenAI APIを呼び出す"""
        client = self._get_openai_client()
        
        if client is None:
            return self._fallback_explanation([])
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            
            content = response.choices[0].message.content
            return self._parse_response(content)
            
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            return self._fallback_explanation([])
    
    def _parse_response(self, content: str) -> BattleExplanation:
        """LLMのレスポンスをパース"""
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                return BattleExplanation(
                    current_situation=data.get("current_situation", ""),
                    recommended_strategy=data.get("recommended_strategy", ""),
                    top_candidate_reason=data.get("top_candidate_reason", ""),
                    risk_analysis=data.get("risk_analysis", ""),
                    opponent_prediction=data.get("opponent_prediction", ""),
                )
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error: {e}")
        
        return self._fallback_explanation([])
    
    def _fallback_explanation(
        self,
        candidates: List[ScoredCandidate],
    ) -> BattleExplanation:
        """フォールバック解説"""
        if candidates and len(candidates) > 0:
            top = candidates[0]
            return BattleExplanation(
                current_situation="盤面を分析中",
                recommended_strategy=f"{top.move1}と{top.move2}の組み合わせが高評価",
                top_candidate_reason=f"スコア{top.score:.0f}点。{top.expected_outcome}",
                risk_analysis=f"リスクレベル: {top.risk_level}",
                opponent_prediction="相手の動きを予測中",
            )
        
        return BattleExplanation(
            current_situation="盤面を分析中",
            recommended_strategy="状況に応じて判断",
            top_candidate_reason="複数の選択肢を検討中",
            risk_analysis="リスクは中程度",
            opponent_prediction="相手の動きを予測中",
        )


# Singleton
_explanation_generator = None

def get_explanation_generator() -> ExplanationGenerator:
    global _explanation_generator
    if _explanation_generator is None:
        _explanation_generator = ExplanationGenerator()
    return _explanation_generator
