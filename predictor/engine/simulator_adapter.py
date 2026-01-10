"""
SimulatorAdapter - Showdown厳密遷移アダプタ

PokéChamp型アーキテクチャの基盤。
Showdownエンジンを使った正確な状態遷移を提供。

References:
- PokéChamp: https://arxiv.org/abs/2503.04094
- PokeLLMon: https://arxiv.org/abs/2402.01118
"""

from __future__ import annotations

import copy
import hashlib
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

try:
    from poke_env.environment.double_battle import DoubleBattle
    from poke_env.environment.move import Move
    from poke_env.environment.pokemon import Pokemon
    POKE_ENV_AVAILABLE = True
except ImportError:
    try:
        from poke_env.battle import DoubleBattle, Move, Pokemon
        POKE_ENV_AVAILABLE = True
    except ImportError:
        POKE_ENV_AVAILABLE = False
        DoubleBattle = None
        Move = None
        Pokemon = None


# ============================================================================
# データ構造
# ============================================================================

class ActionType(Enum):
    MOVE = "move"
    SWITCH = "switch"
    TERA_MOVE = "tera_move"
    PASS = "pass"


@dataclass
class ActionOrder:
    """1体分の行動"""
    action_type: ActionType
    move_id: Optional[str] = None      # 技ID（move/tera_move時）
    target: Optional[int] = None        # ターゲット位置（-1=相手A, -2=相手B, 1=味方A, 2=味方B）
    switch_index: Optional[int] = None  # 交代先のインデックス（switch時）
    
    def __str__(self) -> str:
        if self.action_type == ActionType.MOVE:
            return f"move:{self.move_id}→{self.target}"
        elif self.action_type == ActionType.TERA_MOVE:
            return f"tera+move:{self.move_id}→{self.target}"
        elif self.action_type == ActionType.SWITCH:
            return f"switch:{self.switch_index}"
        else:
            return "pass"
    
    def __hash__(self):
        return hash((self.action_type, self.move_id, self.target, self.switch_index))
    
    def __eq__(self, other):
        if not isinstance(other, ActionOrder):
            return False
        return (self.action_type == other.action_type and
                self.move_id == other.move_id and
                self.target == other.target and
                self.switch_index == other.switch_index)


@dataclass
class JointAction:
    """2体同時行動"""
    slot0: ActionOrder
    slot1: ActionOrder
    
    def __str__(self) -> str:
        return f"[{self.slot0} | {self.slot1}]"
    
    def __hash__(self):
        return hash((self.slot0, self.slot1))
    
    def __eq__(self, other):
        if not isinstance(other, JointAction):
            return False
        return self.slot0 == other.slot0 and self.slot1 == other.slot1


@dataclass
class BattleSnapshot:
    """
    バトル状態のスナップショット
    
    poke-envのDoubleBattleから必要な情報を抽出した軽量版。
    clone/step用に使用。
    """
    turn: int
    
    # 自分側
    self_active: List[Dict[str, Any]]  # [slot0, slot1]
    self_team: List[Dict[str, Any]]    # 控え含む全6体
    self_tera_used: bool
    
    # 相手側
    opp_active: List[Dict[str, Any]]
    opp_team: List[Dict[str, Any]]
    opp_tera_used: bool
    
    # 場の状態
    weather: Optional[str] = None
    weather_turns: int = 0
    terrain: Optional[str] = None
    terrain_turns: int = 0
    trick_room: int = 0
    
    # サイドコンディション
    self_tailwind: int = 0
    opp_tailwind: int = 0
    self_reflect: int = 0
    self_light_screen: int = 0
    opp_reflect: int = 0
    opp_light_screen: int = 0


# ============================================================================
# SimulatorAdapter
# ============================================================================

class SimulatorAdapter:
    """
    Showdown厳密遷移アダプタ
    
    主な機能:
    - enumerate_legal_joint_actions: 合法な2体同時行動を列挙
    - step: 1ターン進める（seed固定で乱数制御）
    - clone: 状態のディープコピー
    """
    
    def __init__(self, use_showdown: bool = True):
        """
        Args:
            use_showdown: Showdownエンジンを使うかどうか
                         Falseの場合は簡易シミュレーション
        """
        self.use_showdown = use_showdown and POKE_ENV_AVAILABLE
    
    # ========================================================================
    # 合法手列挙
    # ========================================================================
    
    def enumerate_legal_joint_actions(
        self,
        battle: DoubleBattle,
        side: Literal["self", "opp"] = "self"
    ) -> List[JointAction]:
        """
        合法な2体同時行動を全列挙
        
        Args:
            battle: poke-envのDoubleBattleオブジェクト
            side: "self"（自分）または "opp"（相手）
            
        Returns:
            JointActionのリスト
        """
        if side == "self":
            return self._enumerate_self_actions(battle)
        else:
            return self._enumerate_opp_actions(battle)
    
    def _enumerate_self_actions(self, battle: DoubleBattle) -> List[JointAction]:
        """自分側の合法手を列挙"""
        slot0_actions = self._get_slot_actions(battle, 0)
        slot1_actions = self._get_slot_actions(battle, 1)
        
        # 全組み合わせ
        joint_actions = []
        for a0 in slot0_actions:
            for a1 in slot1_actions:
                # 同じポケモンへの交代は不可
                if (a0.action_type == ActionType.SWITCH and 
                    a1.action_type == ActionType.SWITCH and
                    a0.switch_index == a1.switch_index):
                    continue
                joint_actions.append(JointAction(a0, a1))
        
        return joint_actions
    
    def _enumerate_opp_actions(self, battle: DoubleBattle) -> List[JointAction]:
        """
        相手側の合法手を列挙（OTS前提で相手の技も既知）
        
        Note: poke-envでは opponent_team が OTS で公開されている場合、
              相手の技/特性/持ち物も取得可能
        """
        slot0_actions = self._get_opp_slot_actions(battle, 0)
        slot1_actions = self._get_opp_slot_actions(battle, 1)
        
        joint_actions = []
        for a0 in slot0_actions:
            for a1 in slot1_actions:
                if (a0.action_type == ActionType.SWITCH and 
                    a1.action_type == ActionType.SWITCH and
                    a0.switch_index == a1.switch_index):
                    continue
                joint_actions.append(JointAction(a0, a1))
        
        return joint_actions
    
    def _get_slot_actions(self, battle: DoubleBattle, slot: int) -> List[ActionOrder]:
        """自分のスロットの合法手を取得"""
        actions = []
        
        # アクティブポケモンがいない場合はpass
        if slot >= len(battle.active_pokemon) or battle.active_pokemon[slot] is None:
            actions.append(ActionOrder(ActionType.PASS))
            return actions
        
        pokemon = battle.active_pokemon[slot]
        
        # 瀕死ならpass
        if pokemon.fainted:
            actions.append(ActionOrder(ActionType.PASS))
            return actions
        
        # 技
        if slot < len(battle.available_moves) and battle.available_moves[slot]:
            for move in battle.available_moves[slot]:
                targets = self._get_valid_targets(battle, move, slot)
                for target in targets:
                    actions.append(ActionOrder(
                        ActionType.MOVE,
                        move_id=move.id,
                        target=target
                    ))
                    # テラスタル可能なら追加
                    can_tera = False
                    try:
                        if battle.can_tera and not pokemon.terastallized:
                            can_tera = True
                    except Exception:
                        pass
                    
                    if can_tera:
                        actions.append(ActionOrder(
                            ActionType.TERA_MOVE,
                            move_id=move.id,
                            target=target
                        ))
        
        # 交代
        if slot < len(battle.available_switches) and battle.available_switches[slot]:
            for i, switch_pokemon in enumerate(battle.available_switches[slot]):
                actions.append(ActionOrder(
                    ActionType.SWITCH,
                    switch_index=i
                ))
        
        # 何もできない場合はpass
        if not actions:
            actions.append(ActionOrder(ActionType.PASS))
        
        return actions
    
    def _get_opp_slot_actions(self, battle: DoubleBattle, slot: int) -> List[ActionOrder]:
        """相手のスロットの合法手を取得（OTS前提）"""
        actions = []
        
        if slot >= len(battle.opponent_active_pokemon) or battle.opponent_active_pokemon[slot] is None:
            actions.append(ActionOrder(ActionType.PASS))
            return actions
        
        pokemon = battle.opponent_active_pokemon[slot]
        
        if pokemon.fainted:
            actions.append(ActionOrder(ActionType.PASS))
            return actions
        
        # OTSで相手の技が分かっている場合
        if pokemon.moves:
            for move_id, move in pokemon.moves.items():
                # PP残りをチェック（不明な場合は使用可能と仮定）
                targets = self._get_valid_targets_for_opp(battle, move, slot)
                for target in targets:
                    actions.append(ActionOrder(
                        ActionType.MOVE,
                        move_id=move_id,
                        target=target
                    ))
        else:
            # 技不明の場合はダミー技を1つ
            actions.append(ActionOrder(
                ActionType.MOVE,
                move_id="struggle",
                target=-1
            ))
        
        # 相手の交代先（OTSで既知）
        bench_count = 0
        for p in battle.opponent_team.values():
            if p and not p.fainted and p not in battle.opponent_active_pokemon:
                actions.append(ActionOrder(
                    ActionType.SWITCH,
                    switch_index=bench_count
                ))
                bench_count += 1
        
        if not actions:
            actions.append(ActionOrder(ActionType.PASS))
        
        return actions
    
    def _get_valid_targets(self, battle: DoubleBattle, move: Move, slot: int) -> List[int]:
        """技の有効なターゲットを取得"""
        targets = []
        
        target_type = getattr(move, 'target', 'normal')
        
        if target_type == 'self':
            # 自分自身
            targets = [slot + 1]  # 1 or 2
        elif target_type == 'allySide':
            # 味方サイド全体（追い風等）：ターゲット指定不要
            targets = [0]
        elif target_type == 'allAdjacentFoes':
            # 相手全体（ハイパーボイス等）：ターゲット指定不要
            targets = [0]
        elif target_type == 'allAdjacent':
            # 自分以外全体（じしん等）：ターゲット指定不要
            targets = [0]
        elif target_type == 'all':
            # 全体（天候技等）：ターゲット指定不要
            targets = [0]
        else:
            # 単体技：相手2体 + 味方1体がターゲット候補
            # poke-envのターゲット: -1=相手slot0, -2=相手slot1, 1=味方slot0, 2=味方slot1
            for i, opp in enumerate(battle.opponent_active_pokemon):
                if opp and not opp.fainted:
                    targets.append(-(i + 1))
            # 味方殴り（基本は入れない、特殊ケースのみ）
            # targets.append(2 if slot == 0 else 1)
        
        if not targets:
            targets = [0]  # フォールバック
        
        return targets
    
    def _get_valid_targets_for_opp(self, battle: DoubleBattle, move: Move, slot: int) -> List[int]:
        """相手の技の有効なターゲットを取得"""
        targets = []
        
        target_type = getattr(move, 'target', 'normal')
        
        if target_type in ('self', 'allySide', 'allAdjacentFoes', 'allAdjacent', 'all'):
            targets = [0]
        else:
            # 単体技：自分側がターゲット
            for i, my_pokemon in enumerate(battle.active_pokemon):
                if my_pokemon and not my_pokemon.fainted:
                    targets.append(-(i + 1))  # 相手視点での自分
        
        if not targets:
            targets = [0]
        
        return targets
    
    # ========================================================================
    # 状態遷移（step）
    # ========================================================================
    
    def step(
        self,
        battle: DoubleBattle,
        joint_self: JointAction,
        joint_opp: JointAction,
        seed: int = 0
    ) -> DoubleBattle:
        """
        1ターン進める
        
        Args:
            battle: 現在の状態
            joint_self: 自分の行動
            joint_opp: 相手の行動
            seed: 乱数シード（同速/急所/ダメ乱数/追加効果）
            
        Returns:
            次の状態
            
        Note:
            現在は簡易シミュレーション。
            将来的にはShowdownエンジンを直接呼び出す。
        """
        # TODO: Showdown厳密遷移を実装
        # 現在は状態をコピーして返すだけ（プレースホルダー）
        return self.clone(battle)
    
    # ========================================================================
    # 状態コピー（clone）
    # ========================================================================
    
    def clone(self, battle: DoubleBattle) -> DoubleBattle:
        """
        状態のディープコピー
        
        Note:
            poke-envのDoubleBattleは直接deepcopyできないため、
            必要な情報だけ抽出してスナップショットを作成。
        """
        # 現時点では同じオブジェクトを返す（プレースホルダー）
        # TODO: 完全なクローン実装
        return battle
    
    def to_snapshot(self, battle: DoubleBattle) -> BattleSnapshot:
        """DoubleBattleをスナップショットに変換"""
        # 自分のアクティブ
        self_active = []
        for p in battle.active_pokemon[:2]:
            if p:
                self_active.append(self._pokemon_to_dict(p))
            else:
                self_active.append(None)
        
        # 自分のチーム
        self_team = []
        for p in battle.team.values():
            if p:
                self_team.append(self._pokemon_to_dict(p))
        
        # 相手のアクティブ
        opp_active = []
        for p in battle.opponent_active_pokemon[:2]:
            if p:
                opp_active.append(self._pokemon_to_dict(p))
            else:
                opp_active.append(None)
        
        # 相手のチーム
        opp_team = []
        for p in battle.opponent_team.values():
            if p:
                opp_team.append(self._pokemon_to_dict(p))
        
        # 天候
        weather = None
        weather_turns = 0
        if battle.weather:
            if isinstance(battle.weather, dict):
                for w, turns in battle.weather.items():
                    weather = w.name if hasattr(w, 'name') else str(w)
                    weather_turns = turns
                    break
            else:
                weather = battle.weather.name if hasattr(battle.weather, 'name') else str(battle.weather)
        
        # フィールド
        terrain = None
        terrain_turns = 0
        if battle.fields:
            if isinstance(battle.fields, dict):
                for f, turns in battle.fields.items():
                    terrain = f.name if hasattr(f, 'name') else str(f)
                    terrain_turns = turns
                    break
        
        return BattleSnapshot(
            turn=battle.turn,
            self_active=self_active,
            self_team=self_team,
            self_tera_used=False,  # TODO
            opp_active=opp_active,
            opp_team=opp_team,
            opp_tera_used=False,  # TODO
            weather=weather,
            weather_turns=weather_turns,
            terrain=terrain,
            terrain_turns=terrain_turns,
        )
    
    def _pokemon_to_dict(self, pokemon: Pokemon) -> Dict[str, Any]:
        """ポケモンを辞書に変換"""
        return {
            "species": pokemon.species,
            "hp_fraction": pokemon.current_hp_fraction,
            "fainted": pokemon.fainted,
            "status": str(pokemon.status) if pokemon.status else None,
            "boosts": dict(pokemon.boosts) if pokemon.boosts else {},
            "moves": list(pokemon.moves.keys()) if pokemon.moves else [],
            "item": pokemon.item,
            "ability": pokemon.ability,
            "tera_type": pokemon.tera_type.name if pokemon.tera_type else None,
            "terastallized": pokemon.terastallized,
        }


# ============================================================================
# ユーティリティ
# ============================================================================

def action_order_from_dict(d: Dict[str, Any]) -> ActionOrder:
    """辞書からActionOrderを作成"""
    return ActionOrder(
        action_type=ActionType(d.get("action_type", "pass")),
        move_id=d.get("move_id"),
        target=d.get("target"),
        switch_index=d.get("switch_index")
    )


def joint_action_from_dict(d: Dict[str, Any]) -> JointAction:
    """辞書からJointActionを作成"""
    return JointAction(
        slot0=action_order_from_dict(d.get("slot0", {})),
        slot1=action_order_from_dict(d.get("slot1", {}))
    )


# ============================================================================
# シングルトン
# ============================================================================

_simulator: Optional[SimulatorAdapter] = None

def get_simulator() -> SimulatorAdapter:
    """SimulatorAdapterのシングルトンを取得"""
    global _simulator
    if _simulator is None:
        _simulator = SimulatorAdapter()
    return _simulator
