"""
Context Builder - LLM用コンテキスト生成器

TypeCalculator, SpeedCalculator, MoveEffectDBを統合し、
LLMが理解しやすい構造化コンテキストを生成する。
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from src.domain.services.type_calculator import (
    get_type_calculator, TypeCalculator, TypeMatchupMatrix
)
from src.domain.services.speed_calculator import (
    get_speed_calculator, SpeedCalculator, SpeedOrder
)
from src.domain.services.move_effect_db import (
    get_move_effect_db, MoveEffectDB, MoveInfo
)


@dataclass
class TurnContext:
    """単一ターンのコンテキスト"""
    speed_order: SpeedOrder
    type_matchups: TypeMatchupMatrix
    relevant_move_effects: List[MoveInfo]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "speed_order": self.speed_order.to_dict(),
            "type_matchups": self.type_matchups.to_dict(),
            "relevant_move_effects": [m.to_dict() for m in self.relevant_move_effects],
        }
    
    def to_summary_text(self) -> str:
        """LLM用のサマリーテキスト"""
        sections = []
        
        # 素早さ順
        sections.append(self.speed_order.to_summary_text())
        sections.append("")
        
        # タイプ相性
        sections.append(self.type_matchups.to_summary_text())
        sections.append("")
        
        # 技効果
        if self.relevant_move_effects:
            sections.append("【重要な技効果】")
            for m in self.relevant_move_effects:
                sections.append(f"  • {m.japanese_name}: {m.effect}")
        
        return "\n".join(sections)


@dataclass
class NextTurnPreview:
    """次ターンのプレビュー（概要のみ）"""
    potential_switches: List[str]
    threats_if_switch: List[str]
    opportunities: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "potential_switches": self.potential_switches,
            "threats_if_switch": self.threats_if_switch,
            "opportunities": self.opportunities,
        }
    
    def to_summary_text(self) -> str:
        lines = ["【次ターンの展望】"]
        
        if self.potential_switches:
            lines.append("  交代候補: " + ", ".join(self.potential_switches))
        
        if self.threats_if_switch:
            lines.append("  注意点:")
            for t in self.threats_if_switch:
                lines.append(f"    • {t}")
        
        if self.opportunities:
            lines.append("  チャンス:")
            for o in self.opportunities:
                lines.append(f"    • {o}")
        
        return "\n".join(lines)


@dataclass
class LLMContext:
    """LLMに渡す完全なコンテキスト"""
    current_turn: TurnContext
    next_turn: NextTurnPreview
    bench_summary: Dict[str, List[str]]  # {"player": [...], "opponent": [...]}
    field_summary: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_turn": self.current_turn.to_dict(),
            "next_turn": self.next_turn.to_dict(),
            "bench_summary": self.bench_summary,
            "field_summary": self.field_summary,
        }
    
    def to_prompt_text(self) -> str:
        """LLMプロンプト用の完全なテキスト"""
        sections = []
        
        # フィールド状態
        sections.append(f"【フィールド状態】\n{self.field_summary}")
        sections.append("")
        
        # 今ターン
        sections.append("=" * 40)
        sections.append("【今ターンの計算結果】")
        sections.append(self.current_turn.to_summary_text())
        sections.append("")
        
        # 次ターン
        sections.append("=" * 40)
        sections.append(self.next_turn.to_summary_text())
        sections.append("")
        
        # 控え
        sections.append("【控えポケモン】")
        sections.append(f"  自分: {', '.join(self.bench_summary.get('player', []))}")
        sections.append(f"  相手: {', '.join(self.bench_summary.get('opponent', []))}")
        
        return "\n".join(sections)


class ContextBuilder:
    """
    LLM用のコンテキストを構築するサービス
    
    BattleStateから全ての必要情報を計算し、
    LLMが理解しやすい形式に変換する。
    """
    
    def __init__(self):
        self.type_calc = get_type_calculator()
        self.speed_calc = get_speed_calculator()
        self.move_db = get_move_effect_db()
    
    def build(
        self,
        player_active: List[Dict[str, Any]],
        opponent_active: List[Dict[str, Any]],
        player_bench: List[Dict[str, Any]] = None,
        opponent_bench: List[Dict[str, Any]] = None,
        field_state: Dict[str, Any] = None,
    ) -> LLMContext:
        """
        バトル状態からLLMコンテキストを構築
        
        Args:
            player_active: 自分の場のポケモン (name, types, moves, speed, etc.)
            opponent_active: 相手の場のポケモン
            player_bench: 自分の控え
            opponent_bench: 相手の控え
            field_state: フィールド状態 (weather, terrain, trick_room, etc.)
        """
        player_bench = player_bench or []
        opponent_bench = opponent_bench or []
        field_state = field_state or {}
        
        # 今ターンのコンテキスト
        current_turn = self._build_current_turn(
            player_active, opponent_active, field_state
        )
        
        # 次ターンのプレビュー
        next_turn = self._build_next_turn_preview(
            player_active, opponent_active, player_bench, opponent_bench
        )
        
        # 控えサマリー
        bench_summary = {
            "player": [p.get("name", "Unknown") for p in player_bench],
            "opponent": [p.get("name", "Unknown") for p in opponent_bench],
        }
        
        # フィールドサマリー
        field_summary = self._build_field_summary(field_state)
        
        return LLMContext(
            current_turn=current_turn,
            next_turn=next_turn,
            bench_summary=bench_summary,
            field_summary=field_summary,
        )
    
    def _build_current_turn(
        self,
        player: List[Dict],
        opponent: List[Dict],
        field_state: Dict,
    ) -> TurnContext:
        """今ターンのコンテキストを構築"""
        
        # 素早さ順序
        speed_order = SpeedCalculator.calculate_from_state(
            player, opponent, field_state
        )
        
        # タイプ相性
        type_matchups = TypeCalculator.build_matrix_from_state(player, opponent)
        
        # 技効果
        all_moves = []
        for p in player + opponent:
            all_moves.extend([m.get("name", "") for m in p.get("moves", [])])
        relevant_effects = self.move_db.get_relevant_effects(all_moves)
        
        return TurnContext(
            speed_order=speed_order,
            type_matchups=type_matchups,
            relevant_move_effects=relevant_effects,
        )
    
    def _build_next_turn_preview(
        self,
        player_active: List[Dict],
        opponent_active: List[Dict],
        player_bench: List[Dict],
        opponent_bench: List[Dict],
    ) -> NextTurnPreview:
        """次ターンの展望を構築"""
        
        potential_switches = []
        threats = []
        opportunities = []
        
        # 自分の交代候補を分析
        for bench in player_bench:
            name = bench.get("name", "Unknown")
            potential_switches.append(name)
            
            # 交代先として有効か分析
            # (簡易実装: 相手の弱点を突けるタイプがあれば良い)
        
        # 相手の交代による脅威
        for bench in opponent_bench:
            name = bench.get("name", "Unknown")
            bench_types = bench.get("types", [])
            
            # 自分に対する脅威を簡易判定
            for active in player_active:
                active_types = active.get("types", [])
                # 4倍弱点などがあれば脅威として記録
        
        # 機会の分析
        for opp in opponent_active:
            hp = opp.get("hp_fraction", 1.0)
            if hp <= 0.3:
                opportunities.append(f"{opp.get('name', 'Unknown')}がHP30%以下で処理可能")
        
        return NextTurnPreview(
            potential_switches=potential_switches[:3],
            threats_if_switch=threats[:3],
            opportunities=opportunities[:3],
        )
    
    def _build_field_summary(self, field_state: Dict) -> str:
        """フィールド状態のサマリー"""
        parts = []
        
        if field_state.get("weather"):
            parts.append(f"天候: {field_state['weather']}")
        if field_state.get("terrain"):
            parts.append(f"フィールド: {field_state['terrain']}")
        if field_state.get("trick_room"):
            parts.append("トリックルーム発動中")
        if field_state.get("tailwind_player"):
            parts.append("自分側おいかぜ")
        if field_state.get("tailwind_opponent"):
            parts.append("相手側おいかぜ")
        
        return " / ".join(parts) if parts else "特になし"


# Singleton
_context_builder = None

def get_context_builder() -> ContextBuilder:
    global _context_builder
    if _context_builder is None:
        _context_builder = ContextBuilder()
    return _context_builder
