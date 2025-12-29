"""
Action Filter Service - 行動フィルタリングサービス

ポケモンの持ち物・特性・状態に基づいて、
選択可能な行動をフィルタリングするドメインサービス。

責務:
1. こだわり系アイテムによる技ロック
2. Assault Vestによる変化技禁止
3. 先制技の優先度に基づくスコア補正
4. 技の評価スコア計算
"""

from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass

# Domain Models からインポート
from src.domain.models.item_effects import (
    is_choice_item,
    blocks_status_moves,
    get_item_effect,
    get_boost_multiplier,
    ItemCategory,
)
from src.domain.models.move_properties import (
    get_move_priority,
    get_move_score_bonus,
    is_priority_move,
    is_conditional_priority,
)


@dataclass
class FilteredAction:
    """フィルタリング後の行動"""
    move_id: str
    is_available: bool
    score: float
    reason: Optional[str] = None  # 使用不可の理由


@dataclass
class PokemonActionContext:
    """行動選択時のポケモンのコンテキスト"""
    species: str
    item: Optional[str]
    last_used_move: Optional[str]  # こだわり系でロックされている技
    is_first_turn: bool  # 場に出た最初のターンか
    current_hp_pct: float  # 現在HP%
    available_moves: List[Any]  # poke-envのMoveオブジェクト


class ActionFilterService:
    """
    行動フィルタリングサービス
    
    DDD原則:
    - ドメインロジックをカプセル化
    - 外部依存（poke-env）への直接参照を最小化
    - 純粋関数として実装（副作用なし）
    """
    
    def __init__(self):
        # ロック状態の追跡（ポケモンID -> ロックされた技）
        self._locked_moves: Dict[str, str] = {}
    
    def filter_available_moves(
        self,
        context: PokemonActionContext,
        opponent_pokemon_names: List[str]
    ) -> List[FilteredAction]:
        """
        利用可能な技をフィルタリングし、スコア付きで返す
        
        Args:
            context: ポケモンの行動コンテキスト
            opponent_pokemon_names: 相手のアクティブポケモン名
            
        Returns:
            フィルタリング済み・スコア付きの行動リスト
        """
        filtered_actions: List[FilteredAction] = []
        
        for move in context.available_moves:
            move_id = self._get_move_id(move)
            is_available = True
            reason = None
            score = self._calculate_base_score(move)
            
            # 1. こだわり系ロックチェック
            if is_choice_item(context.item or ""):
                locked_move = self._locked_moves.get(context.species)
                if locked_move and locked_move != move_id:
                    is_available = False
                    reason = f"Choice locked to {locked_move}"
            
            # 2. Assault Vestによる変化技禁止
            if blocks_status_moves(context.item or ""):
                category = self._get_move_category(move)
                if category == "Status":
                    is_available = False
                    reason = "Assault Vest blocks status moves"
            
            # 3. 初ターン限定技のチェック
            if move_id in ["fakeout", "firstimpression"]:
                if not context.is_first_turn:
                    is_available = False
                    reason = "First turn only move"
                else:
                    # 初ターンなら大幅ボーナス
                    score += 50
            
            # 4. 先制技・重要技のスコアボーナス
            score += get_move_score_bonus(move_id)
            
            # 5. 優先度に基づくボーナス
            priority = get_move_priority(move_id)
            if priority > 0:
                score += priority * 10
            
            filtered_actions.append(FilteredAction(
                move_id=move_id,
                is_available=is_available,
                score=score,
                reason=reason
            ))
        
        return filtered_actions
    
    def update_lock_status(
        self,
        pokemon_species: str,
        item: Optional[str],
        used_move: Optional[str]
    ) -> None:
        """
        こだわり系アイテムのロック状態を更新
        
        Args:
            pokemon_species: ポケモンの種族名
            item: 持っているアイテム
            used_move: 使用した技
        """
        if is_choice_item(item or ""):
            if used_move:
                self._locked_moves[pokemon_species] = used_move
        else:
            # Choice系でなければロック解除
            self._locked_moves.pop(pokemon_species, None)
    
    def get_locked_move(self, pokemon_species: str) -> Optional[str]:
        """ロックされている技を取得"""
        return self._locked_moves.get(pokemon_species)
    
    def clear_lock(self, pokemon_species: str) -> None:
        """ロック状態をクリア（交代時など）"""
        self._locked_moves.pop(pokemon_species, None)
    
    def clear_all_locks(self) -> None:
        """全てのロック状態をクリア（バトル終了時など）"""
        self._locked_moves.clear()
    
    def calculate_action_scores(
        self,
        moves: List[Any],
        item: Optional[str],
        is_first_turn: bool
    ) -> Dict[str, float]:
        """
        技ごとの評価スコアを計算
        
        Args:
            moves: 技リスト
            item: 持っているアイテム
            is_first_turn: 初ターンか
            
        Returns:
            {move_id: score} の辞書
        """
        scores = {}
        
        for move in moves:
            move_id = self._get_move_id(move)
            
            # 基本スコア（威力ベース）
            base_score = self._calculate_base_score(move, item)
            
            # ボーナス
            bonus = get_move_score_bonus(move_id)
            
            # 初ターンボーナス
            if is_first_turn and move_id in ["fakeout", "firstimpression"]:
                bonus += 50
            
            # 優先度ボーナス
            priority = get_move_priority(move_id)
            if priority > 0:
                bonus += priority * 10
            
            scores[move_id] = base_score + bonus
        
        return scores
    
    def _get_move_id(self, move) -> str:
        """技IDを取得（poke-env互換）"""
        if hasattr(move, 'id'):
            return move.id
        return str(move).lower().replace(" ", "").replace("-", "")
    
    def _get_move_category(self, move) -> str:
        """技カテゴリを取得"""
        if hasattr(move, 'category'):
            category = move.category
            if hasattr(category, 'name'):
                return category.name
            return str(category)
        return "Physical"  # デフォルト
    
    def _calculate_base_score(self, move, item: Optional[str] = None) -> float:
        """
        基本スコア（威力ベース）を計算
        アイテム補正を反映
        """
        # Move Domain Model via ID
        move_id = self._get_move_id(move)
        # 循環参照を防ぐため、または軽量化のためここで都度生成（Flyweight）
        # 本来は依存注入すべきだが、Phase 2段階ではこれで対応
        from src.domain.models.move import Move
        from src.domain.models.item import Item

        move_model = Move(move_id)
        base_power = float(move_model.base_power)
            
        # アイテム補正の適用
        if item:
            item_model = Item(item)
            # Itemモデルに委譲
            modifier = item_model.get_damage_modifier(
                move_type=move_model.type,
                is_physical=move_model.is_physical
            )
            base_power *= modifier
        
        return base_power


# シングルトンインスタンス
_action_filter_service: Optional[ActionFilterService] = None


def get_action_filter_service() -> ActionFilterService:
    """ActionFilterServiceのシングルトンを取得"""
    global _action_filter_service
    if _action_filter_service is None:
        _action_filter_service = ActionFilterService()
    return _action_filter_service
