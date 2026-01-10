"""
OpponentModelAdvisor - LLMで相手モデルを補正

PokéChamp 型の設計に基づき、LLMを使って:
1. 相手視点の安定行動を推定
2. OpponentModel の τ（温度）に反映
3. Protect/交代の確率を補正
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, List, Any
import json

try:
    from poke_env.environment.double_battle import DoubleBattle
except ImportError:
    DoubleBattle = None


@dataclass
class OpponentPrior:
    """相手行動の事前確率補正"""
    
    # 行動確率の補正
    protect_probability: float = 0.15       # 守る確率
    switch_probability: float = 0.10        # 交代確率
    aggressive_probability: float = 0.50    # 攻撃的行動確率
    defensive_probability: float = 0.25     # 守備的行動確率
    
    # 推定されたスタイル
    style: str = "balanced"  # aggressive / defensive / balanced / unpredictable
    
    # 特定行動の確率（LLMが推定）
    specific_moves: Dict[str, float] = None  # {"protect": 0.3, "earthquake": 0.4}
    
    # 温度調整
    tau_modifier: float = 1.0  # τを何倍にするか（高いほどランダム）
    
    # 推論理由
    reasoning: str = ""
    
    def __post_init__(self):
        if self.specific_moves is None:
            self.specific_moves = {}


OPPONENT_MODEL_PROMPT = """あなたはVGC（ポケモンダブルバトル）の相手行動予測アドバイザーです。
相手視点から「安定行動」を推測してください。

## 現在の盤面

### 相手のアクティブ（相手視点では"自分"）
{opp_active}

### 自分のアクティブ（相手視点では"相手"）
{my_active}

### 相手の控え
{opp_bench}

### テラスタル状況
相手のテラス可能: {opp_tera_available}
自分のテラス済み: {my_tera_used}

### 相手の残りポケモン数: {opp_remaining}
### 自分の残りポケモン数: {my_remaining}

---

## 分析してほしいこと

1. **相手視点のリスク**: 相手にとって何が怖いか
2. **安定行動**: 相手が「読まれても損しない」行動は何か
3. **守る確率**: 相手が守る可能性（0〜1）
4. **交代確率**: 相手が交代する可能性（0〜1）
5. **攻撃的行動確率**: 攻撃技を選ぶ可能性（0〜1）
6. **相手のスタイル**: aggressive / defensive / balanced

---

## 出力形式（JSON）

```json
{
  "opponent_risk": "説明",
  "stable_action": "説明",
  "protect_probability": 0.0〜1.0,
  "switch_probability": 0.0〜1.0,
  "aggressive_probability": 0.0〜1.0,
  "style": "balanced",
  "tau_modifier": 1.0,
  "reasoning": "推論理由"
}
```

重要:
- 確率の合計が1.0を超えても構いません（独立事象として扱います）
- tau_modifier は相手の行動が読みにくい場合に1.5〜2.0、読みやすい場合に0.5〜0.8
"""


class OpponentModelAdvisor:
    """
    LLMで相手モデルを補正するアドバイザー
    
    使用例:
    ```python
    advisor = OpponentModelAdvisor(llm_client)
    prior = advisor.get_opponent_prior(battle)
    
    # prior.protect_probability を使って相手行動を予測
    # prior.tau_modifier を使って OpponentModel の τ を調整
    ```
    """
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
        self._cache: Dict[str, OpponentPrior] = {}
    
    def get_opponent_prior(
        self,
        battle: DoubleBattle,
        plan: Any = None,
    ) -> OpponentPrior:
        """
        相手行動の事前確率をLLMで推定
        
        Args:
            battle: 現在のバトル状態
            plan: ゲームプラン（あれば）
        
        Returns:
            OpponentPrior: 相手行動の事前確率
        """
        if not self.llm:
            return self._default_prior(battle)
        
        # キャッシュキー
        cache_key = self._make_cache_key(battle)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            prior = self._ask_llm(battle)
            self._cache[cache_key] = prior
            return prior
        except Exception as e:
            print(f"  ⚠️ OpponentModelAdvisor エラー: {e}")
            return self._default_prior(battle)
    
    def _make_cache_key(self, battle: DoubleBattle) -> str:
        """キャッシュキーを生成"""
        if not battle:
            return "unknown"
        
        # アクティブポケモンと残数でキー化
        my_active = tuple(p.species if p and not p.fainted else None 
                          for p in battle.active_pokemon[:2])
        opp_active = tuple(p.species if p and not p.fainted else None 
                           for p in battle.opponent_active_pokemon[:2])
        
        return f"{battle.turn}_{my_active}_{opp_active}"
    
    def _default_prior(self, battle: DoubleBattle) -> OpponentPrior:
        """LLMがない場合のデフォルト"""
        # 相手の残りポケモン数に基づく簡易推定
        if battle:
            opp_remaining = sum(1 for p in battle.opponent_team.values() if p and not p.fainted)
            my_remaining = sum(1 for p in battle.team.values() if p and not p.fainted)
            
            if opp_remaining < my_remaining:
                # 相手不利 → より守備的になりやすい
                return OpponentPrior(
                    protect_probability=0.25,
                    switch_probability=0.15,
                    aggressive_probability=0.40,
                    defensive_probability=0.35,
                    style="defensive",
                    tau_modifier=1.2,
                    reasoning="相手不利なので守備的になりやすい"
                )
            elif opp_remaining > my_remaining:
                # 相手有利 → より攻撃的
                return OpponentPrior(
                    protect_probability=0.10,
                    switch_probability=0.08,
                    aggressive_probability=0.65,
                    defensive_probability=0.15,
                    style="aggressive",
                    tau_modifier=0.8,
                    reasoning="相手有利なので攻撃的になりやすい"
                )
        
        return OpponentPrior()
    
    def _ask_llm(self, battle: DoubleBattle) -> OpponentPrior:
        """LLMに問い合わせ"""
        # 盤面情報を収集
        my_active_info = self._format_pokemon_list(battle.active_pokemon, side="self", battle=battle)
        opp_active_info = self._format_pokemon_list(battle.opponent_active_pokemon, side="opp", battle=battle)
        opp_bench_info = self._format_bench(battle, side="opp")
        
        opp_tera_available = not any(p.terastallized for p in battle.opponent_active_pokemon if p)
        my_tera_used = any(p.terastallized for p in battle.active_pokemon if p)
        
        opp_remaining = sum(1 for p in battle.opponent_team.values() if p and not p.fainted)
        my_remaining = sum(1 for p in battle.team.values() if p and not p.fainted)
        
        prompt = OPPONENT_MODEL_PROMPT.format(
            opp_active=opp_active_info,
            my_active=my_active_info,
            opp_bench=opp_bench_info,
            opp_tera_available=opp_tera_available,
            my_tera_used=my_tera_used,
            opp_remaining=opp_remaining,
            my_remaining=my_remaining,
        )
        
        response = self.llm.chat(prompt)
        return self._parse_response(response)
    
    def _format_pokemon_list(self, pokemon_list, side: str, battle) -> str:
        """ポケモンリストをフォーマット"""
        lines = []
        for i, p in enumerate(pokemon_list[:2]):
            if p and not p.fainted:
                hp_pct = p.current_hp_fraction * 100 if p.current_hp_fraction else 100
                status = f" ({p.status.name})" if p.status else ""
                lines.append(f"  スロット{i}: {p.species} HP{hp_pct:.0f}%{status}")
        return "\n".join(lines) if lines else "  なし"
    
    def _format_bench(self, battle, side: str) -> str:
        """控えをフォーマット"""
        team = battle.opponent_team if side == "opp" else battle.team
        active = battle.opponent_active_pokemon if side == "opp" else battle.active_pokemon
        active_species = {p.species for p in active[:2] if p}
        
        lines = []
        for p in team.values():
            if p and not p.fainted and p.species not in active_species:
                hp_pct = p.current_hp_fraction * 100 if p.current_hp_fraction else 100
                lines.append(f"  {p.species} HP{hp_pct:.0f}%")
        
        return "\n".join(lines) if lines else "  なし"
    
    def _parse_response(self, response: str) -> OpponentPrior:
        """LLMレスポンスをパース"""
        try:
            # JSONブロックを抽出
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            
            data = json.loads(json_str)
            
            return OpponentPrior(
                protect_probability=float(data.get("protect_probability", 0.15)),
                switch_probability=float(data.get("switch_probability", 0.10)),
                aggressive_probability=float(data.get("aggressive_probability", 0.50)),
                defensive_probability=1.0 - float(data.get("aggressive_probability", 0.50)),
                style=data.get("style", "balanced"),
                tau_modifier=float(data.get("tau_modifier", 1.0)),
                reasoning=data.get("reasoning", ""),
            )
        except Exception as e:
            print(f"  ⚠️ OpponentModel パースエラー: {e}")
            return OpponentPrior()


# シングルトン
_opponent_advisor: Optional[OpponentModelAdvisor] = None


def get_opponent_model_advisor(llm_client=None) -> OpponentModelAdvisor:
    """OpponentModelAdvisor のシングルトンを取得"""
    global _opponent_advisor
    if _opponent_advisor is None:
        _opponent_advisor = OpponentModelAdvisor(llm_client)
    return _opponent_advisor
