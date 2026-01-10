"""
BattleMemory - ターン間状態追跡

Phase B: 対戦中の履歴を追跡し、次のターンの判断に活用する

機能:
- ターンごとの行動履歴
- Protect連続回数の追跡
- 見えた技/持ち物/特性の記録
- 相手のプレイスタイル推定
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set, Any
from enum import Enum


# =============================================================================
# データクラス
# =============================================================================

class ActionType(Enum):
    """行動タイプ"""
    MOVE = "move"
    SWITCH = "switch"
    PASS = "pass"


@dataclass
class TurnAction:
    """1体の1ターンの行動"""
    slot: int                    # 0 or 1
    action_type: ActionType
    move_id: Optional[str] = None      # 技ID
    target_slot: Optional[int] = None  # ターゲット
    switch_to: Optional[str] = None    # 交代先
    terastallized: bool = False


@dataclass
class TurnRecord:
    """1ターンの記録"""
    turn_number: int
    self_actions: List[TurnAction]   # 自分の行動
    opp_actions: List[TurnAction]    # 相手の行動
    
    # ダメージ結果
    damage_dealt: Dict[str, int] = field(default_factory=dict)  # {pokemon: damage}
    damage_taken: Dict[str, int] = field(default_factory=dict)
    
    # 倒れたポケモン
    fainted_self: List[str] = field(default_factory=list)
    fainted_opp: List[str] = field(default_factory=list)


@dataclass
class PokemonMemory:
    """1匹のポケモンに関する記憶"""
    species: str
    seen_moves: Set[str] = field(default_factory=set)
    seen_item: Optional[str] = None
    item_consumed: bool = False
    seen_ability: Optional[str] = None
    terastallized: bool = False
    tera_type: Optional[str] = None
    
    # Protect追跡
    last_protect_turn: Optional[int] = None
    consecutive_protects: int = 0
    total_protects: int = 0
    
    # 行動パターン
    total_moves: int = 0
    total_switches: int = 0


# =============================================================================
# BattleMemory
# =============================================================================

class BattleMemory:
    """
    対戦中の履歴を管理するクラス
    
    役割:
    - ターンごとの行動を記録
    - Protect連打の検出
    - 相手の情報を蓄積
    """
    
    def __init__(self):
        """初期化"""
        self.current_turn: int = 0
        self.turn_history: List[TurnRecord] = []
        
        # ポケモンごとの記憶
        self.self_pokemon: Dict[str, PokemonMemory] = {}
        self.opp_pokemon: Dict[str, PokemonMemory] = {}
        
        # 相手のプレイスタイル
        self.opp_style: Dict[str, float] = {
            "aggressive": 0.5,      # 攻撃的
            "defensive": 0.5,       # 守備的
            "switch_happy": 0.5,    # 交代が多い
        }
    
    # =========================================================================
    # 記録系
    # =========================================================================
    
    def record_turn(
        self,
        turn_number: int,
        self_actions: List[TurnAction],
        opp_actions: List[TurnAction],
    ) -> None:
        """
        ターンを記録
        
        Args:
            turn_number: ターン番号
            self_actions: 自分の行動リスト
            opp_actions: 相手の行動リスト
        """
        self.current_turn = turn_number
        
        record = TurnRecord(
            turn_number=turn_number,
            self_actions=self_actions,
            opp_actions=opp_actions,
        )
        self.turn_history.append(record)
        
        # 各行動を解析して記憶を更新
        for action in self_actions:
            self._update_pokemon_memory(action, is_opponent=False)
        
        for action in opp_actions:
            self._update_pokemon_memory(action, is_opponent=True)
    
    def record_seen_move(
        self, species: str, move_id: str, is_opponent: bool = True
    ) -> None:
        """見えた技を記録"""
        memory = self._get_or_create_memory(species, is_opponent)
        memory.seen_moves.add(move_id.lower())
    
    def record_seen_item(
        self, species: str, item: str, is_opponent: bool = True
    ) -> None:
        """見えた持ち物を記録"""
        memory = self._get_or_create_memory(species, is_opponent)
        memory.seen_item = item.lower()
    
    def record_seen_ability(
        self, species: str, ability: str, is_opponent: bool = True
    ) -> None:
        """見えた特性を記録"""
        memory = self._get_or_create_memory(species, is_opponent)
        memory.seen_ability = ability.lower()
    
    def record_protect(self, species: str, is_opponent: bool = True) -> None:
        """Protect使用を記録"""
        memory = self._get_or_create_memory(species, is_opponent)
        
        # 連続Protect判定
        if memory.last_protect_turn == self.current_turn - 1:
            memory.consecutive_protects += 1
        else:
            memory.consecutive_protects = 1
        
        memory.last_protect_turn = self.current_turn
        memory.total_protects += 1
    
    def record_terastallize(
        self, species: str, tera_type: str, is_opponent: bool = True
    ) -> None:
        """テラスタル使用を記録"""
        memory = self._get_or_create_memory(species, is_opponent)
        memory.terastallized = True
        memory.tera_type = tera_type
    
    # =========================================================================
    # 参照系
    # =========================================================================
    
    def get_consecutive_protects(
        self, species: str, is_opponent: bool = True
    ) -> int:
        """連続Protect回数を取得"""
        memory = self._get_memory(species, is_opponent)
        if not memory:
            return 0
        
        # 直前のターンがProtectでなければリセット
        if memory.last_protect_turn != self.current_turn - 1:
            return 0
        
        return memory.consecutive_protects
    
    def get_protect_probability(
        self, species: str, is_opponent: bool = True
    ) -> float:
        """
        Protect成功確率を取得
        
        連続Protectは失敗しやすい:
        - 1回目: 100%
        - 2回目: 33%
        - 3回目以降: 11%
        """
        consecutive = self.get_consecutive_protects(species, is_opponent)
        
        if consecutive == 0:
            return 1.0
        elif consecutive == 1:
            return 1/3
        else:
            return 1/9
    
    def get_seen_moves(
        self, species: str, is_opponent: bool = True
    ) -> Set[str]:
        """見えた技一覧を取得"""
        memory = self._get_memory(species, is_opponent)
        return memory.seen_moves if memory else set()
    
    def get_seen_item(
        self, species: str, is_opponent: bool = True
    ) -> Optional[str]:
        """見えた持ち物を取得"""
        memory = self._get_memory(species, is_opponent)
        return memory.seen_item if memory else None
    
    def get_seen_ability(
        self, species: str, is_opponent: bool = True
    ) -> Optional[str]:
        """見えた特性を取得"""
        memory = self._get_memory(species, is_opponent)
        return memory.seen_ability if memory else None
    
    def has_terastallized(self, is_opponent: bool = True) -> bool:
        """テラスタルを使用済みか"""
        pokemon_dict = self.opp_pokemon if is_opponent else self.self_pokemon
        return any(m.terastallized for m in pokemon_dict.values())
    
    def get_last_actions(
        self, n_turns: int = 1, is_opponent: bool = True
    ) -> List[List[TurnAction]]:
        """直近n ターンの行動を取得"""
        result = []
        for record in self.turn_history[-n_turns:]:
            actions = record.opp_actions if is_opponent else record.self_actions
            result.append(actions)
        return result
    
    # =========================================================================
    # プレイスタイル推定
    # =========================================================================
    
    def estimate_protect_likelihood(
        self,
        species: str,
        is_being_focused: bool = False,
        is_unfavorable_matchup: bool = False,
        hp_ratio: float = 1.0,
    ) -> float:
        """
        Protect使用確率を推定
        
        Args:
            species: ポケモン種族
            is_being_focused: 集中攻撃されそうか
            is_unfavorable_matchup: 不利対面か
            hp_ratio: 残りHP比率 (0.0 ~ 1.0)
            
        Returns:
            float: Protect使用確率 (0.0 ~ 1.0)
        """
        base_prob = 0.1  # ベース確率
        
        # 集中されそうなら上昇
        if is_being_focused:
            base_prob += 0.3
        
        # 不利対面なら上昇
        if is_unfavorable_matchup:
            base_prob += 0.15
        
        # HP低いと上昇
        if hp_ratio < 0.4:
            base_prob += 0.2
        
        # 連続Protectは成功率ダウン（使いにくい）
        consecutive = self.get_consecutive_protects(species, is_opponent=True)
        if consecutive >= 1:
            base_prob *= 0.3  # 連続Protectは避けがち
        
        return min(0.8, base_prob)  # 最大80%
    
    def estimate_switch_likelihood(
        self,
        species: str,
        is_one_shot_range: bool = False,
        is_unfavorable_matchup: bool = False,
        has_better_switch: bool = False,
    ) -> float:
        """
        交代確率を推定
        
        Args:
            species: ポケモン種族
            is_one_shot_range: ワンパン圏内か
            is_unfavorable_matchup: 不利対面か
            has_better_switch: より良い交代先があるか
            
        Returns:
            float: 交代確率 (0.0 ~ 1.0)
        """
        base_prob = 0.05  # ベース確率
        
        if is_one_shot_range:
            base_prob += 0.25
        
        if is_unfavorable_matchup:
            base_prob += 0.15
        
        if has_better_switch:
            base_prob += 0.1
        
        # 相手のプレイスタイル補正
        base_prob *= (0.5 + self.opp_style["switch_happy"])
        
        return min(0.6, base_prob)  # 最大60%
    
    # =========================================================================
    # Private Methods
    # =========================================================================
    
    def _get_or_create_memory(
        self, species: str, is_opponent: bool
    ) -> PokemonMemory:
        """ポケモンの記憶を取得（なければ作成）"""
        species_lower = species.lower()
        pokemon_dict = self.opp_pokemon if is_opponent else self.self_pokemon
        
        if species_lower not in pokemon_dict:
            pokemon_dict[species_lower] = PokemonMemory(species=species_lower)
        
        return pokemon_dict[species_lower]
    
    def _get_memory(
        self, species: str, is_opponent: bool
    ) -> Optional[PokemonMemory]:
        """ポケモンの記憶を取得（なければNone）"""
        species_lower = species.lower()
        pokemon_dict = self.opp_pokemon if is_opponent else self.self_pokemon
        return pokemon_dict.get(species_lower)
    
    def _update_pokemon_memory(
        self, action: TurnAction, is_opponent: bool
    ) -> None:
        """行動からポケモンの記憶を更新"""
        # 注: 現在の実装では species 情報が action に含まれていないため、
        # 外部から record_seen_move 等を呼ぶ必要がある
        pass


# =============================================================================
# シングルトン
# =============================================================================

_memory: Optional[BattleMemory] = None


def get_battle_memory() -> BattleMemory:
    """BattleMemory のシングルトンを取得"""
    global _memory
    if _memory is None:
        _memory = BattleMemory()
    return _memory


def reset_battle_memory() -> None:
    """BattleMemory をリセット（新しい対戦開始時）"""
    global _memory
    _memory = BattleMemory()
