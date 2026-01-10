"""
GamePlanner - ゲームプラン策定

cona氏のプランニング理論に基づく選出画面での戦略立案。

主要機能:
1. 脅威分析 - 相手パーティで最も危険なポケモンを特定
2. 対策プラン - ダメージプラン/受けプランを策定
3. 選出決定 - 先発2体、後発2体を決定
4. 初動方針 - 1ターン目の行動方針

References:
- cona氏（新潟オフ優勝者）のプランニング解説
"""

from __future__ import annotations

import json
import os
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
# データ構造
# ============================================================================

@dataclass
class GamePlan:
    """
    試合のゲームプラン
    
    cona氏のプランニング理論に基づく:
    - 脅威（負け筋）を特定
    - 勝ち筋を設計
    - ダメージ/受けプランを策定
    - 保険（バックアップ）を準備
    """
    # 個別対策（相手ポケモン別）
    matchup_analysis: Dict[str, str]
    
    # 選出
    lead: Tuple[str, str]     # 先発2体
    back: Tuple[str, str]     # 後発2体
    lead_reason: str          # 先発の理由
    back_reason: str          # 後発の理由
    
    # プラン
    damage_plan: str          # 誰で誰を倒すか
    defensive_plan: str       # どう守るか
    win_condition: str        # 勝ち筋
    
    # 初動
    turn1_pokemon1: str       # 先発1体目の1ターン目行動
    turn1_pokemon2: str       # 先発2体目の1ターン目行動
    
    # ============= 案2: cona的プランニング構造 =============
    # 脅威（負け筋）- 最優先で対処すべき相手
    primary_threats: List[str] = field(default_factory=list)
    
    # KOルート - 具体的な倒し方
    ko_routes: Dict[str, str] = field(default_factory=dict)  # {target: "誰のどの技で"}
    
    # 保険（バックアップ）- プランが崩れた時
    backup_lines: List[str] = field(default_factory=list)
    
    # S操作方針
    speed_control: str = ""  # "tailwind", "trickroom", "icywind", "none"
    
    # テラスタル方針
    tera_plan: str = ""  # いつ誰がテラスタルするか
    
    def __str__(self) -> str:
        lines = [
            "=" * 60,
            "📋 ゲームプラン",
            "=" * 60,
            "",
            "【相手への対策】",
        ]
        for opp_name, strategy in self.matchup_analysis.items():
            lines.append(f"  vs {opp_name}: {strategy}")
        
        # 脅威（負け筋）
        if self.primary_threats:
            lines.append("")
            lines.append(f"【⚠️ 脅威（負け筋）】{', '.join(self.primary_threats)}")
        
        lines.extend([
            "",
            f"【選出】",
            f"  先発: {self.lead[0]} + {self.lead[1]}",
            f"    理由: {self.lead_reason}",
            f"  後発: {self.back[0]} + {self.back[1]}",
            f"    理由: {self.back_reason}",
            "",
            f"【ダメージプラン】{self.damage_plan}",
            f"【受けプラン】{self.defensive_plan}",
            f"【勝ち筋】{self.win_condition}",
        ])
        
        # KOルート
        if self.ko_routes:
            lines.append("")
            lines.append("【KOルート】")
            for target, route in self.ko_routes.items():
                lines.append(f"  {target}: {route}")
        
        # 保険
        if self.backup_lines:
            lines.append("")
            lines.append("【保険（バックアップ）】")
            for backup in self.backup_lines:
                lines.append(f"  - {backup}")
        
        lines.extend([
            "",
            f"【1ターン目】",
            f"  {self.lead[0]}: {self.turn1_pokemon1}",
            f"  {self.lead[1]}: {self.turn1_pokemon2}",
            "",
            "=" * 60,
        ])
        return "\n".join(lines)
    
    def get_threat_priority(self, pokemon_name: str) -> int:
        """脅威の優先度を取得（低いほど優先）"""
        name_lower = pokemon_name.lower()
        for i, threat in enumerate(self.primary_threats):
            if threat.lower() == name_lower:
                return i
        return 999  # 脅威リストにない場合
    
    def is_primary_threat(self, pokemon_name: str) -> bool:
        """主要脅威かどうか"""
        name_lower = pokemon_name.lower()
        return any(t.lower() == name_lower for t in self.primary_threats)


# ============================================================================
# LLMプロンプト
# ============================================================================

GAME_PLANNER_PROMPT = """あなたはVGCダブルバトルの戦略家です。

## VGCルール
- ダブルバトル: 場には常に2体ずつ（2vs2）
- 選出: 6体から**4体だけ**選んで試合に使う
- 先発2体が最初に場に出る、後発2体は控え

## 自分のパーティ（6体）
{my_team}

## 相手のパーティ（6体）
{opp_team}

## タスク
相手の各ポケモンへの対策を考え、最適な4体を選出してください。

以下のJSON形式で回答：

```json
{{
  "matchup_analysis": {{
    "{opp1}": "誰でどう対処するか",
    "{opp2}": "誰でどう対処するか",
    "{opp3}": "誰でどう対処するか",
    "{opp4}": "誰でどう対処するか",
    "{opp5}": "誰でどう対処するか",
    "{opp6}": "誰でどう対処するか"
  }},
  "selection": {{
    "lead": ["先発1体目", "先発2体目"],
    "back": ["後発1体目", "後発2体目"],
    "lead_reason": "この先発を選んだ理由",
    "back_reason": "この後発を選んだ理由"
  }},
  "game_plan": {{
    "damage_plan": "選出4体で誰が誰を倒すか",
    "defensive_plan": "どう守って勝ちにつなげるか",
    "win_condition": "どうすれば勝てるか"
  }},
  "turn1_actions": {{
    "pokemon1": "先発1体目の1ターン目行動",
    "pokemon2": "先発2体目の1ターン目行動"
  }}
}}
```

重要:
1. 選出は4体のみ（lead 2 + back 2）
2. 選ばれなかった2体はプランに含めない
3. 相手6体すべてへの対策を記載
4. **ポケモン名は英語のみ**（例：arcaninehisui, fluttermane）
5. 日本語名や括弧は使わない
"""


# 毎ターン行動選択用プロンプト
TURN_ACTION_PROMPT = """あなたはVGCダブルバトルのAIです。

## 現在の状況
ターン: {turn}
勝率推定: {win_prob}%

### 自分のアクティブ
{my_active}

### 相手のアクティブ
{opp_active}

### 自分の控え
{my_bench}

### 使用可能な技
{available_moves}

### 現在の候補行動（確率付き）
{candidate_actions}

## タスク
上記の候補から最適な行動を選び、理由を説明してください。

JSON形式で回答：
```json
{{
  "recommended_action": "〇〇は△△を使う / ××は□□を使う",
  "reasoning": "この行動を選んだ理由（1文）",
  "risk": "この行動のリスク（1文）"
}}
```
"""


# ============================================================================
# GamePlanner
# ============================================================================

class GamePlanner:
    """
    ゲームプラン策定器
    
    cona氏のプランニング理論を実装:
    1. 脅威を特定
    2. 対策プランを立案
    3. 選出を決定
    4. 初動を設計
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        self.llm = llm_client
    
    def plan(
        self,
        my_team: List[str],
        opp_team: List[str],
        battle: Optional[DoubleBattle] = None,
    ) -> GamePlan:
        """
        ゲームプランを策定
        
        Args:
            my_team: 自分のパーティ（ポケモン名リスト）
            opp_team: 相手のパーティ（ポケモン名リスト）
            battle: DoubleBattleオブジェクト（オプション）
            
        Returns:
            GamePlan
        """
        # LLMで生成
        if self.llm:
            plan = self._plan_with_llm(my_team, opp_team)
            if plan:
                return plan
        
        # フォールバック: 簡易ロジック
        return self._plan_simple(my_team, opp_team)
    
    def _plan_with_llm(
        self,
        my_team: List[str],
        opp_team: List[str],
    ) -> Optional[GamePlan]:
        """LLMでプランを生成"""
        my_team_str = ", ".join(my_team)
        opp_team_str = ", ".join(opp_team)
        
        # 相手ポケモン名をプロンプトに挿入
        opp_names = opp_team + ["???"] * (6 - len(opp_team))  # 6体に補完
        
        prompt = GAME_PLANNER_PROMPT.format(
            my_team=my_team_str,
            opp_team=opp_team_str,
            opp1=opp_names[0],
            opp2=opp_names[1],
            opp3=opp_names[2],
            opp4=opp_names[3],
            opp5=opp_names[4],
            opp6=opp_names[5],
        )
        
        print("  🤖 LLMでゲームプランを生成中...")
        
        try:
            # LLMを呼び出し
            response = self.llm._call_llm(prompt)
            
            if not response:
                print("  ⚠️ LLM応答なし")
                return None
            
            # JSONを抽出
            result = self.llm._extract_json(response)
            
            if not result:
                print("  ⚠️ JSON解析失敗")
                return None
            
            # 新形式でGamePlanを構築
            matchup = result.get("matchup_analysis", {})
            selection = result.get("selection", {})
            game_plan = result.get("game_plan", {})
            turn1 = result.get("turn1_actions", {})
            
            lead = selection.get("lead", my_team[:2])
            back = selection.get("back", my_team[2:4] if len(my_team) >= 4 else my_team[:2])
            
            return GamePlan(
                matchup_analysis=matchup,
                lead=tuple(lead[:2]) if len(lead) >= 2 else (lead[0] if lead else my_team[0], lead[1] if len(lead) > 1 else my_team[1]),
                back=tuple(back[:2]) if len(back) >= 2 else (back[0] if back else my_team[2], back[1] if len(back) > 1 else my_team[3]),
                lead_reason=selection.get("lead_reason", ""),
                back_reason=selection.get("back_reason", ""),
                damage_plan=game_plan.get("damage_plan", ""),
                defensive_plan=game_plan.get("defensive_plan", ""),
                win_condition=game_plan.get("win_condition", ""),
                turn1_pokemon1=turn1.get("pokemon1", ""),
                turn1_pokemon2=turn1.get("pokemon2", ""),
            )
            
        except Exception as e:
            print(f"  ⚠️ LLMプランニング失敗: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _plan_simple(
        self,
        my_team: List[str],
        opp_team: List[str],
    ) -> GamePlan:
        """簡易プラン（LLMなし）"""
        # 先頭4体を選出
        lead = (my_team[0] if my_team else "???", my_team[1] if len(my_team) > 1 else "???")
        back = (my_team[2] if len(my_team) > 2 else "???", my_team[3] if len(my_team) > 3 else "???")
        
        # 簡易個別対策
        matchup = {name: f"{lead[0]}で対処" for name in opp_team}
        
        return GamePlan(
            matchup_analysis=matchup,
            lead=lead,
            back=back,
            lead_reason="先頭2体を先発",
            back_reason="3-4番目を後発",
            damage_plan="火力ポケモンで削る",
            defensive_plan="サポートで補助",
            win_condition="相手を全滅させる",
            turn1_pokemon1="攻撃",
            turn1_pokemon2="サポート",
        )
    
    def get_team_order(self, plan: GamePlan, my_team: List[str]) -> str:
        """
        GamePlanからポケモンの選出順を取得
        
        Returns:
            "/team 1234" 形式の文字列
        """
        import re
        
        def normalize(name: str) -> str:
            """ポケモン名を正規化"""
            result = name.lower()
            # 日本語括弧、通常括弧、ハイフン、スペース、アンダースコアを削除
            result = re.sub(r'[（）()【】\[\]「」『』\-\s_]', '', result)
            # よくある日本語表記を英語に変換
            replacements = {
                'ヒスイ': 'hisui',
                'ひすい': 'hisui',
                'ガラル': 'galar',
                'アローラ': 'alola',
                'パルデア': 'paldea',
            }
            for jp, en in replacements.items():
                result = result.replace(jp, en)
            return result
        
        # チーム内のインデックスを取得
        order = []
        
        print(f"\n  📋 選出マッピング:")
        print(f"    自分のチーム: {my_team}")
        print(f"    LLM選出 先発: {plan.lead}")
        print(f"    LLM選出 後発: {plan.back}")
        
        # 先発
        for name in plan.lead:
            matched = False
            norm_name = normalize(name)
            for i, pokemon in enumerate(my_team):
                if normalize(pokemon) == norm_name and (i + 1) not in order:
                    order.append(i + 1)
                    print(f"    先発 {name} → インデックス {i + 1}")
                    matched = True
                    break
            if not matched:
                print(f"    ⚠️ 先発 {name} がチームに見つからない（正規化後: {norm_name}）")
        
        # 後発
        for name in plan.back:
            matched = False
            norm_name = normalize(name)
            for i, pokemon in enumerate(my_team):
                if normalize(pokemon) == norm_name and (i + 1) not in order:
                    order.append(i + 1)
                    print(f"    後発 {name} → インデックス {i + 1}")
                    matched = True
                    break
            if not matched:
                print(f"    ⚠️ 後発 {name} がチームに見つからない（正規化後: {norm_name}）")
        
        # 4体に満たない場合は補完
        if len(order) < 4:
            print(f"    ⚠️ 選出が{len(order)}体のみ、補完中...")
            for i in range(1, 7):
                if i not in order and len(order) < 4:
                    order.append(i)
                    print(f"    補完: インデックス {i}")
        
        order_str = "".join(str(i) for i in order[:4])
        print(f"    最終選出順: {order_str}")
        return f"/team {order_str}"


# ============================================================================
# シングルトン
# ============================================================================

_planner: Optional[GamePlanner] = None


def get_game_planner(llm_client: Optional[Any] = None) -> GamePlanner:
    """GamePlannerのシングルトンを取得"""
    global _planner
    if _planner is None:
        _planner = GamePlanner(llm_client)
    return _planner
