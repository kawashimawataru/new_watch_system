"""
LLMClient - LLM呼び出しクライアント

PokéChamp型アーキテクチャのLLM統合モジュール。
候補生成/相手モデル/価値推定/説明生成を担当。

References:
- PokéChamp: https://arxiv.org/abs/2503.04094
- PokeLLMon: https://arxiv.org/abs/2402.01118 (KAG)
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from poke_env.environment.double_battle import DoubleBattle
except ImportError:
    try:
        from poke_env.battle import DoubleBattle
    except ImportError:
        DoubleBattle = None


# ============================================================================
# 設定
# ============================================================================

@dataclass
class LLMConfig:
    """LLMクライアントの設定"""
    provider: str = "openai"              # "openai", "anthropic", "google"
    model: str = "gpt-4o-mini"            # モデル名
    temperature: float = 0.3              # 生成温度
    max_tokens: int = 1024                # 最大トークン数
    timeout: float = 10.0                 # タイムアウト（秒）
    api_key: Optional[str] = None         # APIキー（Noneなら環境変数）


# ============================================================================
# プロンプトテンプレート
# ============================================================================

CANDIDATE_GENERATION_PROMPT = """あなたはポケモンVGC（ダブルバトル）の専門家です。
以下の局面で、有効な候補手を評価してください。

## 局面情報
{battle_summary}

## 合法な行動一覧
{action_list}

## タスク
各行動を評価し、以下のJSON形式で回答してください。
スコアは0.0〜1.0で、1.0が最も有効な行動です。
上位10個の行動のみを返してください。

```json
[
  {{"action_id": "A1", "score": 0.85, "tags": ["ko", "spread"]}},
  {{"action_id": "A2", "score": 0.70, "tags": ["speed", "setup"]}}
]
```

重要ルール:
- action_id は必ず上記一覧にあるIDを使用
- tags は以下から選択: ko, spread, speed, setup, protect, switch, redirection, tera
- JSONのみを返す（説明不要）
"""

OPPONENT_MODELING_PROMPT = """あなたはポケモンVGC（ダブルバトル）の専門家です。
相手プレイヤーの視点で、どの行動を選びそうかを予測してください。

## 局面情報（相手視点）
{battle_summary}

## 相手の合法な行動一覧
{action_list}

## タスク
相手がどの行動を選ぶか確率分布を予測してください。
pは確率（合計1.0）、rationale_tags は行動理由を示すタグです。

```json
[
  {{"action_id": "B1", "p": 0.40, "rationale_tags": ["aggressive", "ko_threat"]}},
  {{"action_id": "B2", "p": 0.30, "rationale_tags": ["safe", "protect"]}}
]
```

重要ルール:
- action_id は必ず上記一覧にあるIDを使用
- pの合計が1.0になるように
- rationale_tags: aggressive, defensive, safe, risky, ko_threat, setup, pivot
"""

VALUE_ESTIMATION_PROMPT = """あなたはポケモンVGC（ダブルバトル）の専門家です。
以下の局面を評価してください。

## 局面情報
{battle_summary}

## タスク
自分（P1）視点での有利度を-1.0〜+1.0で評価してください。
+1.0は確実勝利、-1.0は確実敗北、0.0は五分です。

```json
{{"value": 0.3, "rationale_tags": ["hp_advantage", "speed_control"]}}
```

rationale_tags: hp_advantage, hp_disadvantage, speed_control, tera_advantage, momentum, numbers_advantage
"""

EXPLANATION_PROMPT = """あなたはポケモンVGC（ダブルバトル）の実況者です。
以下の情報を基に、状況を分かりやすく解説してください。

## 根拠情報
{anchors}

## タスク
上記の根拠を基に、観戦者向けに1-2文で状況を解説してください。
- 専門用語は避けて分かりやすく
- 「〜です」「〜ます」調で
- 50文字以内

回答（日本語のみ）:
"""


# ============================================================================
# LLMClient
# ============================================================================

class LLMClient:
    """
    LLM呼び出しクライアント
    
    - generate_candidates: 候補生成
    - model_opponent: 相手モデリング
    - evaluate_state: 価値推定
    - generate_explanation: 説明生成（KAG）
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._client = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """クライアントを初期化"""
        if self._initialized:
            return
        
        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
        
        if self.config.provider == "openai" and api_key:
            try:
                import openai
                self._client = openai.OpenAI(api_key=api_key)
                self._initialized = True
            except ImportError:
                print("⚠️ openai package not installed")
        elif self.config.provider == "anthropic":
            try:
                import anthropic
                self._client = anthropic.Anthropic(
                    api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
                )
                self._initialized = True
            except ImportError:
                print("⚠️ anthropic package not installed")
    
    def _call_llm(self, prompt: str) -> Optional[str]:
        """LLMを呼び出し"""
        self._ensure_initialized()
        
        if not self._client:
            return None
        
        try:
            print(f"  🤖 LLM呼び出し中... (model: {self.config.model})")
            
            if self.config.provider == "openai":
                response = self._client.chat.completions.create(
                    model=self.config.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                result = response.choices[0].message.content
                # 完全なLLM応答を表示
                print(f"  ✅ LLM応答受信（{len(result)}文字）:")
                print("  " + "-" * 50)
                for line in result.split("\n"):
                    print(f"  {line}")
                print("  " + "-" * 50)
                return result
            
            elif self.config.provider == "anthropic":
                response = self._client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                result = response.content[0].text
                print(f"  ✅ LLM応答: {result[:100]}..." if len(result) > 100 else f"  ✅ LLM応答: {result}")
                return result
            
        except Exception as e:
            print(f"  ⚠️ LLM call failed: {e}")
            return None
    
    def _extract_json(self, text: str) -> Any:
        """テキストからJSONを抽出"""
        if not text:
            return None
        
        # コードブロック内のJSONを探す
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if json_match:
            text = json_match.group(1)
        
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return None
    
    # ========================================================================
    # 候補生成
    # ========================================================================
    
    async def generate_candidates(
        self,
        battle_summary: str,
        action_list: str,
    ) -> List[Dict]:
        """
        候補生成用LLM呼び出し
        
        Returns:
            [{action_id, score, tags}]
        """
        prompt = CANDIDATE_GENERATION_PROMPT.format(
            battle_summary=battle_summary,
            action_list=action_list,
        )
        
        response = self._call_llm(prompt)
        result = self._extract_json(response)
        
        if isinstance(result, list):
            return result
        return []
    
    def generate_candidates_sync(
        self,
        battle_summary: str,
        action_list: str,
    ) -> List[Dict]:
        """同期版"""
        prompt = CANDIDATE_GENERATION_PROMPT.format(
            battle_summary=battle_summary,
            action_list=action_list,
        )
        
        response = self._call_llm(prompt)
        result = self._extract_json(response)
        
        if isinstance(result, list):
            return result
        return []
    
    # ========================================================================
    # 相手モデリング
    # ========================================================================
    
    async def model_opponent(
        self,
        battle_summary: str,
        action_list: str,
    ) -> List[Dict]:
        """
        相手モデリング用LLM呼び出し
        
        Returns:
            [{action_id, p, rationale_tags}]
        """
        prompt = OPPONENT_MODELING_PROMPT.format(
            battle_summary=battle_summary,
            action_list=action_list,
        )
        
        response = self._call_llm(prompt)
        result = self._extract_json(response)
        
        if isinstance(result, list):
            return result
        return []
    
    def model_opponent_sync(
        self,
        battle_summary: str,
        action_list: str,
    ) -> List[Dict]:
        """同期版"""
        prompt = OPPONENT_MODELING_PROMPT.format(
            battle_summary=battle_summary,
            action_list=action_list,
        )
        
        response = self._call_llm(prompt)
        result = self._extract_json(response)
        
        if isinstance(result, list):
            return result
        return []
    
    # ========================================================================
    # 価値推定
    # ========================================================================
    
    async def evaluate_state(
        self,
        battle_summary: str,
    ) -> Tuple[float, List[str]]:
        """
        価値推定用LLM呼び出し
        
        Returns:
            (value, rationale_tags)
        """
        prompt = VALUE_ESTIMATION_PROMPT.format(
            battle_summary=battle_summary,
        )
        
        response = self._call_llm(prompt)
        result = self._extract_json(response)
        
        if isinstance(result, dict):
            value = result.get("value", 0.0)
            tags = result.get("rationale_tags", [])
            return float(value), tags
        
        return 0.0, []
    
    def evaluate_state_sync(
        self,
        battle_summary: str,
    ) -> Tuple[float, List[str]]:
        """同期版"""
        prompt = VALUE_ESTIMATION_PROMPT.format(
            battle_summary=battle_summary,
        )
        
        response = self._call_llm(prompt)
        result = self._extract_json(response)
        
        if isinstance(result, dict):
            value = result.get("value", 0.0)
            tags = result.get("rationale_tags", [])
            return float(value), tags
        
        return 0.0, []
    
    # ========================================================================
    # 説明生成（KAG）
    # ========================================================================
    
    async def generate_explanation(
        self,
        anchors: List[str],
    ) -> str:
        """
        説明生成用LLM呼び出し（KAG）
        
        Returns:
            日本語の短い説明文
        """
        anchors_text = "\n".join(f"- {a}" for a in anchors)
        
        prompt = EXPLANATION_PROMPT.format(
            anchors=anchors_text,
        )
        
        response = self._call_llm(prompt)
        
        if response:
            # 余分な引用符や改行を除去
            return response.strip().strip('"').strip()
        
        return ""
    
    def generate_explanation_sync(
        self,
        anchors: List[str],
    ) -> str:
        """同期版"""
        anchors_text = "\n".join(f"- {a}" for a in anchors)
        
        prompt = EXPLANATION_PROMPT.format(
            anchors=anchors_text,
        )
        
        response = self._call_llm(prompt)
        
        if response:
            return response.strip().strip('"').strip()
        
        return ""


# ============================================================================
# バトル要約生成
# ============================================================================

def summarize_battle(battle: DoubleBattle, side: str = "self") -> str:
    """バトル状態を要約テキストに変換"""
    lines = []
    lines.append(f"ターン: {battle.turn}")
    
    # 自分のアクティブ
    self_active = []
    for p in battle.active_pokemon[:2]:
        if p and not p.fainted:
            hp_pct = int(p.current_hp_fraction * 100)
            status = f"/{p.status.name}" if p.status else ""
            self_active.append(f"{p.species}(HP{hp_pct}%{status})")
    lines.append(f"自分: {', '.join(self_active) or 'なし'}")
    
    # 相手のアクティブ
    opp_active = []
    for p in battle.opponent_active_pokemon[:2]:
        if p and not p.fainted:
            hp_pct = int(p.current_hp_fraction * 100)
            status = f"/{p.status.name}" if p.status else ""
            opp_active.append(f"{p.species}(HP{hp_pct}%{status})")
    lines.append(f"相手: {', '.join(opp_active) or 'なし'}")
    
    # 残数
    self_remaining = sum(1 for p in battle.team.values() if p and not p.fainted)
    opp_remaining = sum(1 for p in battle.opponent_team.values() if p and not p.fainted)
    lines.append(f"残数: 自分{self_remaining} vs 相手{opp_remaining}")
    
    return "\n".join(lines)


def format_action_list(actions: List[Any], prefix: str = "A") -> str:
    """行動リストを文字列に変換"""
    lines = []
    for i, action in enumerate(actions):
        action_id = f"{prefix}{i+1}"
        lines.append(f"- {action_id}: {action}")
    return "\n".join(lines)


# ============================================================================
# シングルトン
# ============================================================================

_llm_client: Optional[LLMClient] = None

def get_llm_client() -> LLMClient:
    """LLMClientのシングルトンを取得"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
