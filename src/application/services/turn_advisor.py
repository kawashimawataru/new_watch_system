"""
Turn Advisor - LLM行動アドバイザー

ContextBuilderとPlanTrackerを統合し、LLMに問い合わせて行動を提案する。
"""

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from src.domain.services.context_builder import (
    get_context_builder, ContextBuilder, LLMContext
)
from src.domain.services.plan_tracker import (
    get_plan_tracker, PlanTracker, PlanStatus
)
from src.domain.models.battle_plan import BattlePlan


@dataclass
class ActionRecommendation:
    """LLMからの行動推奨"""
    slot_a_action: str          # Slot Aの行動
    slot_a_target: str          # Slot Aのターゲット
    slot_b_action: str          # Slot Bの行動
    slot_b_target: str          # Slot Bのターゲット
    reasoning: str              # 理由
    confidence: float           # 信頼度 (0.0-1.0)
    alternatives: List[Dict] = field(default_factory=list)  # 代替案
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "slot_a": {"action": self.slot_a_action, "target": self.slot_a_target},
            "slot_b": {"action": self.slot_b_action, "target": self.slot_b_target},
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "alternatives": self.alternatives,
        }


class TurnAdvisor:
    """
    LLMを使ったターンアドバイザー
    
    ContextBuilderの計算結果とPlanTrackerの進捗を統合し、
    LLMに問い合わせて最適な行動を提案する。
    """
    
    SYSTEM_PROMPT = """あなたはVGCダブルバトルの戦術アドバイザーです。

与えられた情報に基づいて、最適な行動を選択してください。

重要なルール:
1. タイプ相性の計算結果に従ってください（LLMで再計算しないでください）
2. 素早さ順序の計算結果に従ってください
3. バトルプランに沿った行動を優先してください
4. 技の効果（優先度、範囲など）を正しく理解してください

回答は必ず以下のJSON形式で返してください:
{
    "slot_a_action": "技名または交代先",
    "slot_a_target": "ターゲット名（全体技なら\"全体\"）",
    "slot_b_action": "技名または交代先",
    "slot_b_target": "ターゲット名",
    "reasoning": "この行動を選んだ理由（1-2文で簡潔に）",
    "confidence": 0.8
}
"""
    
    def __init__(self, use_openai: bool = True):
        self.context_builder = get_context_builder()
        self.plan_tracker = get_plan_tracker()
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
    
    def advise(
        self,
        player_active: List[Dict[str, Any]],
        opponent_active: List[Dict[str, Any]],
        player_bench: List[Dict[str, Any]] = None,
        opponent_bench: List[Dict[str, Any]] = None,
        field_state: Dict[str, Any] = None,
        turn: int = 1,
    ) -> ActionRecommendation:
        """
        現在の盤面から行動を推奨
        
        Args:
            player_active: 自分の場のポケモン
            opponent_active: 相手の場のポケモン
            player_bench: 自分の控え
            opponent_bench: 相手の控え
            field_state: フィールド状態
            turn: 現在のターン
        
        Returns:
            ActionRecommendation
        """
        player_bench = player_bench or []
        opponent_bench = opponent_bench or []
        field_state = field_state or {}
        
        # コンテキスト構築
        context = self.context_builder.build(
            player_active, opponent_active,
            player_bench, opponent_bench, field_state
        )
        
        # プラン進捗評価
        all_player = player_active + player_bench
        all_opponent = opponent_active + opponent_bench
        plan_status = self.plan_tracker.evaluate(all_player, all_opponent, turn)
        
        # プラン取得
        plan = self.plan_tracker.get_plan()
        
        # プロンプト構築
        prompt = self._build_prompt(context, plan, plan_status, player_active)
        
        # LLM呼び出し
        if self.use_openai:
            return self._call_openai(prompt)
        else:
            return self._fallback_recommendation(player_active)
    
    def _build_prompt(
        self,
        context: LLMContext,
        plan: Optional[BattlePlan],
        plan_status: PlanStatus,
        player_active: List[Dict],
    ) -> str:
        """LLMプロンプトを構築"""
        sections = []
        
        # プラン情報
        if plan:
            sections.append(plan.to_prompt_text())
            sections.append("")
            sections.append(plan_status.to_prompt_text())
            sections.append("")
        
        # コンテキスト情報
        sections.append(context.to_prompt_text())
        sections.append("")
        
        # 選択可能な行動
        sections.append("【選択可能な行動】")
        for i, poke in enumerate(player_active):
            slot = "A" if i == 0 else "B"
            name = poke.get("name", "Unknown")
            moves = [m.get("name", "技") for m in poke.get("moves", [])]
            sections.append(f"Slot {slot} ({name}): {', '.join(moves)}, 交代")
        
        sections.append("")
        sections.append("上記の情報に基づいて、最適な行動をJSON形式で回答してください。")
        
        return "\n".join(sections)
    
    def _call_openai(self, prompt: str) -> ActionRecommendation:
        """OpenAI APIを呼び出す"""
        client = self._get_openai_client()
        
        if client is None:
            return self._fallback_recommendation([])
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            
            content = response.choices[0].message.content
            
            # JSON抽出
            parsed = self._parse_response(content)
            return parsed
            
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            return self._fallback_recommendation([])
    
    def _parse_response(self, content: str) -> ActionRecommendation:
        """LLMのレスポンスをパース"""
        try:
            # JSON部分を抽出
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                return ActionRecommendation(
                    slot_a_action=data.get("slot_a_action", "まもる"),
                    slot_a_target=data.get("slot_a_target", ""),
                    slot_b_action=data.get("slot_b_action", "まもる"),
                    slot_b_target=data.get("slot_b_target", ""),
                    reasoning=data.get("reasoning", ""),
                    confidence=data.get("confidence", 0.5),
                )
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error: {e}")
        
        return self._fallback_recommendation([])
    
    def _fallback_recommendation(
        self,
        player_active: List[Dict],
    ) -> ActionRecommendation:
        """フォールバック: 守る"""
        return ActionRecommendation(
            slot_a_action="まもる",
            slot_a_target="",
            slot_b_action="まもる",
            slot_b_target="",
            reasoning="LLM応答がないため、安全策として守るを選択",
            confidence=0.3,
        )


# Singleton
_turn_advisor = None

def get_turn_advisor() -> TurnAdvisor:
    global _turn_advisor
    if _turn_advisor is None:
        _turn_advisor = TurnAdvisor()
    return _turn_advisor
