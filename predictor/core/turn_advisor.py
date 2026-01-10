"""
TurnAdvisor - 毎ターンのLLM候補絞り込み

案1: 対戦中に毎ターンLLMを呼び出し、有望な候補を絞り込む

役割:
- 現在の盤面 + PlanObject を受け取る
- LLMに「この盤面で有望な2-3手」を問い合わせる
- 返ってきた候補を CandidateGenerator / MCTS に渡す

注意:
- LLMは「候補生成」のみ、最終決定はダメ計+予測+MCTSで行う
- LLM呼び出しに失敗した場合は全候補を返す（フォールバック）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from poke_env.environment.double_battle import DoubleBattle
except ImportError:
    try:
        from poke_env.battle import DoubleBattle
    except ImportError:
        DoubleBattle = None

from predictor.core.game_planner import GamePlan


# =============================================================================
# データ構造
# =============================================================================

@dataclass
class TurnRecommendation:
    """1ターンの推奨行動"""
    slot0_moves: List[str]      # スロット0の推奨技ID
    slot1_moves: List[str]      # スロット1の推奨技ID
    should_protect: List[bool]  # [slot0, slot1] で守るべきか
    should_switch: List[bool]   # [slot0, slot1] で交代すべきか
    reasoning: str              # 理由（互換性のため残す、中身はthought_processと同じ）
    thought_process: str        # 思考プロセス (Chain of Thought)
    risk_warning: str           # リスク警告
    plan_alignment: float       # プラン遂行度 (0.0 ~ 1.0)


# =============================================================================
# プロンプト
# =============================================================================

TURN_ADVISOR_PROMPT = """あなたはVGC（ポケモンダブルバトル）の戦略アドバイザーです。
「読み」や「直感」ではなく、**論理的なリスク管理**と**勝利確率の最大化**に基づいて判断してください。

## ゲームプラン（選出時に策定済み）
勝ち筋: {win_condition}
ダメージプラン: {damage_plan}
受けプラン: {defensive_plan}
主要脅威: {primary_threats}

## 現在の盤面
ターン: {turn}

### 自分のアクティブ
{my_active}

### 相手のアクティブ（アイテム・特性も考慮）
{opp_active}

### 自分の控え（交代候補）
{my_bench}

### テラスタル状況
自分のテラス可能: {my_tera_available}
相手のテラス済み: {opp_tera_used}

### 使用可能な技
スロット0 ({pokemon0}): {moves0}
スロット1 ({pokemon1}): {moves1}

### 交代可能ポケモン
{switch_options}

---

## 思考プロセス (Chain of Thought)
以下のステップで論理的に思考してください：
1. **盤面分析**: 相手の脅威度、有利/不利対面の判定。
2. **リスク評価**: 「守る」や「テラスタル」が必要な致命的な攻撃（集中攻撃、弱点突かれ）があるか？
3. **勝ち筋確認**: ゲームプランに沿った行動か？（例: サイクル戦で削る、トリックルームを展開する等）
4. **候補選定**: 有力な行動ペアを列挙し、それぞれのリスク/リターンを評価。
5. **絞り込み**: 最も合理的で勝率が高いと思われる「トップ5」の候補を選定。

## 出力フォーマット
JSON形式で回答してください。`thought_process` に上記の思考ステップを記述し、その結論として各スロットの推奨行動を出力します。

```json
{{
  "thought_process": "1. 盤面分析: ... \n2. リスク評価: ... \n3. 勝ち筋確認: ... \n4. 候補選定: ... \n5. 結論: ...",
  "risk_assessment": {{
    "slot0_dies_if_not_protect": false,
    "slot0_dies_if_not_tera": false,
    "slot1_dies_if_not_protect": false,
    "slot1_dies_if_not_tera": false
  }},
  "slot0": {{
    "recommended_moves": ["技ID1", "技ID2", "技ID3", "技ID4", "技ID5"],
    "should_protect": false,
    "protect_reason": "守る理由",
    "should_switch": false,
    "switch_to": null,
    "switch_reason": "交代理由",
    "should_tera": false,
    "tera_reason": "テラス理由",
    "move_reasoning": "推奨技の選定理由"
  }},
  "slot1": {{
    "recommended_moves": ["技ID1", "技ID2", "技ID3", "技ID4", "技ID5"],
    "should_protect": false,
    "protect_reason": null,
    "should_switch": false,
    "switch_to": null,
    "switch_reason": null,
    "should_tera": false,
    "tera_reason": null,
    "move_reasoning": "推奨技の選定理由"
  }},
  "plan_alignment": 0.9
}}
```

重要：
- **`thought_process` は詳細に記述してください。** なぜその技を選んだのか、なぜそのリスクを取るのかを言語化してください。
- `recommended_moves` は各スロットにつき **最大5つ** まで選んでください。優先度の高い順に並べてください。
- 技IDは英語小文字（例: protect, icywind, closecombat）で正確に記述してください。
- **守る**判断: 即死リスクがある場合は迷わず守ってください。
- **テラス**判断: 攻撃的テラス（火力2倍）も積極的に検討してください。
- **交代**判断: 不利対面や展開作り（威嚇サイクル等）のために積極的に交代を検討してください。
"""


# =============================================================================
# TurnAdvisor
# =============================================================================

class TurnAdvisor:
    """
    毎ターンの行動アドバイザー
    
    LLMを使って有望な候補を絞り込み、
    MCTSやダメ計の精度を上げる。
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        """
        初期化
        
        Args:
            llm_client: LLMクライアント
        """
        self.llm = llm_client
    
    def advise(
        self,
        battle: DoubleBattle,
        plan: Optional[GamePlan],
    ) -> TurnRecommendation:
        """
        このターンの推奨行動を取得
        
        Args:
            battle: 現在のバトル状態
            plan: ゲームプラン（選出時に生成）
            
        Returns:
            TurnRecommendation: 推奨行動
        """
        # LLMが使えない場合はフォールバック
        if not self.llm:
            return self._fallback_recommendation(battle)
        
        try:
            return self._advise_with_llm(battle, plan)
        except Exception as e:
            print(f"  ⚠️ TurnAdvisor LLMエラー: {e}")
            return self._fallback_recommendation(battle)
    
    def _advise_with_llm(
        self,
        battle: DoubleBattle,
        plan: Optional[GamePlan],
    ) -> TurnRecommendation:
        """LLMで推奨行動を取得"""
        
        # 盤面情報を整形
        my_active = self._format_active_pokemon(battle.active_pokemon)
        opp_active = self._format_active_pokemon(battle.opponent_active_pokemon)
        my_bench = self._format_bench_pokemon(battle)
        
        # 使用可能技
        pokemon0 = battle.active_pokemon[0].species if battle.active_pokemon[0] else "???"
        pokemon1 = battle.active_pokemon[1].species if len(battle.active_pokemon) > 1 and battle.active_pokemon[1] else "???"
        
        moves0 = self._format_available_moves(battle, 0)
        moves1 = self._format_available_moves(battle, 1)
        
        # プラン情報
        win_condition = plan.win_condition if plan else "不明"
        damage_plan = plan.damage_plan if plan else "不明"
        defensive_plan = plan.defensive_plan if plan else "不明"
        primary_threats = ", ".join(plan.primary_threats) if plan and plan.primary_threats else "なし"
        
        # テラスタル情報
        my_tera_available = self._check_tera_available(battle)
        opp_tera_used = self._check_opp_tera_used(battle)
        
        # 交代オプション
        switch_options = self._format_switch_options(battle)
        
        # プロンプト生成
        prompt = TURN_ADVISOR_PROMPT.format(
            turn=battle.turn,
            my_active=my_active,
            opp_active=opp_active,
            my_bench=my_bench,
            pokemon0=pokemon0,
            pokemon1=pokemon1,
            moves0=moves0,
            moves1=moves1,
            win_condition=win_condition,
            damage_plan=damage_plan,
            defensive_plan=defensive_plan,
            primary_threats=primary_threats,
            my_tera_available=my_tera_available,
            opp_tera_used=opp_tera_used,
            switch_options=switch_options,
        )
        
        print(f"  🤖 TurnAdvisor: ターン{battle.turn}の推奨行動を問い合わせ中...")
        
        # LLM呼び出し
        response = self.llm._call_llm(prompt)
        if not response:
            return self._fallback_recommendation(battle)
        
        # JSON解析
        result = self.llm._extract_json(response)
        if not result:
            return self._fallback_recommendation(battle)
        
        # 結果を構造化
        slot0 = result.get("slot0", {})
        slot1 = result.get("slot1", {})
        
        # thought_processを取得（プロンプトで要求済み）
        thought_process = result.get("thought_process", result.get("reasoning", ""))
        
        return TurnRecommendation(
            slot0_moves=slot0.get("recommended_moves", []),
            slot1_moves=slot1.get("recommended_moves", []),
            should_protect=[
                slot0.get("should_protect", False),
                slot1.get("should_protect", False),
            ],
            should_switch=[
                slot0.get("should_switch", False),
                slot1.get("should_switch", False),
            ],
            reasoning=thought_process,  # 互換性のため thought_process を入れる
            thought_process=thought_process,
            risk_warning=result.get("risk_warning", ""),
            plan_alignment=result.get("plan_alignment", 0.5),
        )
    
    def _fallback_recommendation(self, battle: DoubleBattle) -> TurnRecommendation:
        """フォールバック：全技を推奨"""
        slot0_moves = []
        slot1_moves = []
        
        if battle.available_moves and len(battle.available_moves) > 0:
            slot0_moves = [m.id for m in battle.available_moves[0]]
        if battle.available_moves and len(battle.available_moves) > 1:
            slot1_moves = [m.id for m in battle.available_moves[1]]
        
        reasoning_text = "フォールバック：全候補を評価"
        
        return TurnRecommendation(
            slot0_moves=slot0_moves,
            slot1_moves=slot1_moves,
            should_protect=[False, False],
            should_switch=[False, False],
            reasoning=reasoning_text,
            thought_process=reasoning_text,
            risk_warning="",
            plan_alignment=0.5,
        )
    
    def _format_active_pokemon(self, pokemon_list) -> str:
        """アクティブポケモンを文字列化（アイテム・特性・テラス情報付き）"""
        lines = []
        # pokemon_list がリストでない場合の対策
        if not isinstance(pokemon_list, (list, tuple)):
            pokemon_list = [pokemon_list] if pokemon_list else []
        
        for i, p in enumerate(pokemon_list):
            if p and not getattr(p, 'fainted', False):
                # HP計算を安全に行う
                max_hp = getattr(p, 'max_hp', None)
                current_hp = getattr(p, 'current_hp', None)
                if max_hp and max_hp > 0 and current_hp is not None:
                    hp_pct = int(current_hp / max_hp * 100)
                else:
                    hp_pct = int(getattr(p, 'current_hp_fraction', 1.0) * 100)
                
                # ステータス
                status = ""
                if hasattr(p, 'status') and p.status:
                    status = f" ({p.status.name})"
                
                # アイテム
                item = getattr(p, 'item', None)
                item_str = f" 持ち物:{item}" if item else ""
                
                # 特性
                ability = getattr(p, 'ability', None)
                ability_str = f" 特性:{ability}" if ability else ""
                
                # テラスタル
                tera = ""
                if getattr(p, 'terastallized', False):
                    tera = f" [テラス]"
                
                species = getattr(p, 'species', 'Unknown')
                lines.append(f"  スロット{i}: {species} HP{hp_pct}%{status}{item_str}{ability_str}{tera}")
            elif p and getattr(p, 'fainted', False):
                species = getattr(p, 'species', 'Unknown')
                lines.append(f"  スロット{i}: {species} (瀕死)")
            else:
                lines.append(f"  スロット{i}: なし")
        return "\n".join(lines)
    
    def _format_bench_pokemon(self, battle: DoubleBattle) -> str:
        """控えポケモンを文字列化（交代候補として詳細に）"""
        lines = []
        switches = getattr(battle, 'available_switches', []) or []
        
        # available_switches が2次元リストの場合があるので正規化
        if switches and isinstance(switches[0], (list, tuple)):
            # フラット化
            flat_switches = []
            for slot_switches in switches:
                if slot_switches:
                    for p in slot_switches:
                        if p and p not in flat_switches:
                            flat_switches.append(p)
            switches = flat_switches
        
        for p in switches:
            if p:
                # HP計算を安全に行う
                max_hp = getattr(p, 'max_hp', None)
                current_hp = getattr(p, 'current_hp', None)
                if max_hp and max_hp > 0 and current_hp is not None:
                    hp_pct = int(current_hp / max_hp * 100)
                else:
                    hp_pct = int(getattr(p, 'current_hp_fraction', 1.0) * 100)
                
                # アイテム
                item = getattr(p, 'item', None)
                item_str = f" ({item})" if item else ""
                
                species = getattr(p, 'species', 'Unknown')
                lines.append(f"  {species} HP{hp_pct}%{item_str}")
        return "\n".join(lines) if lines else "  なし"
    
    def _format_available_moves(self, battle: DoubleBattle, slot: int) -> str:
        """使用可能技を文字列化（タイプも表示）"""
        if not battle.available_moves or slot >= len(battle.available_moves):
            return "なし"
        
        moves = battle.available_moves[slot]
        move_strs = []
        for m in moves:
            power = f" 威力{m.base_power}" if m.base_power else ""
            move_type = f"({m.type.name})" if hasattr(m, 'type') and m.type else ""
            move_strs.append(f"{m.id}{move_type}{power}")
        
        return ", ".join(move_strs) if move_strs else "なし"
    
    def _check_tera_available(self, battle: DoubleBattle) -> str:
        """テラスタル可能かどうかを確認"""
        can_tera = []
        for i, p in enumerate(battle.active_pokemon):
            if p and not getattr(p, 'fainted', False):
                # can_terastallize があれば確認
                if hasattr(battle, 'can_terastallize') and battle.can_terastallize:
                    can_tera.append(f"{p.species}({getattr(p, 'tera_type', '?')})")
                elif not getattr(p, 'terastallized', False):
                    tera_type = getattr(p, 'tera_type', None)
                    if tera_type:
                        can_tera.append(f"{p.species}({tera_type})")
        return ", ".join(can_tera) if can_tera else "使用不可"
    
    def _check_opp_tera_used(self, battle: DoubleBattle) -> str:
        """相手がテラスタル済みかどうかを確認"""
        tera_used = []
        for p in battle.opponent_active_pokemon:
            if p and getattr(p, 'terastallized', False):
                tera_used.append(f"{p.species}")
        
        # 相手チーム全体も確認
        if hasattr(battle, 'opponent_team'):
            for p in battle.opponent_team.values():
                if p and getattr(p, 'terastallized', False):
                    if p.species not in tera_used:
                        tera_used.append(f"{p.species}")
        
        return ", ".join(tera_used) if tera_used else "未使用"
    
    def _format_switch_options(self, battle: DoubleBattle) -> str:
        """交代オプションを詳細に文字列化（なぜ交代するべきかも含む）"""
        lines = []
        switches = getattr(battle, 'available_switches', []) or []
        
        # 2次元リストを正規化
        if switches and isinstance(switches[0], (list, tuple)):
            flat_switches = []
            for slot_switches in switches:
                if slot_switches:
                    for p in slot_switches:
                        if p and p not in flat_switches:
                            flat_switches.append(p)
            switches = flat_switches
        
        for p in switches:
            if p:
                species = getattr(p, 'species', 'Unknown')
                
                # HP
                max_hp = getattr(p, 'max_hp', None)
                current_hp = getattr(p, 'current_hp', None)
                if max_hp and max_hp > 0 and current_hp is not None:
                    hp_pct = int(current_hp / max_hp * 100)
                else:
                    hp_pct = int(getattr(p, 'current_hp_fraction', 1.0) * 100)
                
                # 持ち物
                item = getattr(p, 'item', None)
                item_str = f" [{item}]" if item else ""
                
                # タイプ
                types = []
                if hasattr(p, 'types'):
                    types = [str(t.name) if hasattr(t, 'name') else str(t) for t in p.types if t]
                type_str = f" ({'/'.join(types)})" if types else ""
                
                lines.append(f"  {species}{type_str} HP{hp_pct}%{item_str}")
        
        return "\n".join(lines) if lines else "  交代不可"
    
    def filter_candidates(
        self,
        recommendation: TurnRecommendation,
        all_moves: List[List[Any]],  # [slot0_moves, slot1_moves]
    ) -> List[List[Any]]:
        """
        推奨に基づいて候補をフィルタリング
        
        Args:
            recommendation: LLMの推奨
            all_moves: 全使用可能技 [slot0, slot1]
            
        Returns:
            フィルタリングされた技リスト [slot0, slot1]
        """
        result = [[], []]
        
        for slot in range(2):
            recommended = recommendation.slot0_moves if slot == 0 else recommendation.slot1_moves
            moves = all_moves[slot] if slot < len(all_moves) else []
            
            if not recommended:
                # 推奨がなければ全技を返す
                result[slot] = list(moves)
            else:
                # 推奨された技のみ抽出
                recommended_lower = [m.lower() for m in recommended]
                for move in moves:
                    move_id = move.id if hasattr(move, 'id') else str(move)
                    if move_id.lower() in recommended_lower:
                        result[slot].append(move)
                
                # 推奨技が見つからなかった場合は全技を返す
                if not result[slot]:
                    result[slot] = list(moves)
        
        return result


# =============================================================================
# シングルトン
# =============================================================================

_advisor: Optional[TurnAdvisor] = None


def get_turn_advisor(llm_client: Optional[Any] = None) -> TurnAdvisor:
    """TurnAdvisorのシングルトンを取得"""
    global _advisor
    if _advisor is None:
        _advisor = TurnAdvisor(llm_client)
    return _advisor
