"""
Generation Config - 世代別ルール設定

VGC Gen 6-9 の各世代固有ギミックとルールを定義。
ユーザーが世代を切り替えて使用できるようにする。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class SpecialMechanic(Enum):
    """特殊ギミックの種類"""
    NONE = "none"               # 特殊ギミックなし (Gen 1-5)
    MEGA = "mega"               # メガシンカ (Gen 6-7)
    ZMOVE = "zmove"             # Zワザ (Gen 7)
    DYNAMAX = "dynamax"         # ダイマックス (Gen 8)
    TERASTAL = "terastal"       # テラスタル (Gen 9)


@dataclass
class GenerationConfig:
    """世代設定"""
    gen: int                            # 世代番号 (6, 7, 8, 9)
    name: str                           # 表示名 ("XY", "SM", "SwSh", "SV")
    full_name: str                      # フルネーム
    special_mechanic: SpecialMechanic   # 特殊ギミック
    
    # ギミック使用ルール
    uses_per_battle: int = 1            # 1試合あたりの使用回数
    duration_turns: int = 0             # 持続ターン (0 = 永続)
    requires_item: bool = False         # 専用アイテムが必要か
    
    # ダブルバトルルール
    bring_count: int = 4                # 選出可能数
    battle_count: int = 4               # 場に出せる最大数
    
    # 禁止伝説ルール
    restricted_count: int = 2           # 禁止伝説の選出可能数 (レギュG等)
    
    # 追加ルール
    item_clause: bool = True            # 同じアイテム禁止
    species_clause: bool = True         # 同じポケモン禁止
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "gen": self.gen,
            "name": self.name,
            "full_name": self.full_name,
            "special_mechanic": self.special_mechanic.value,
            "uses_per_battle": self.uses_per_battle,
            "duration_turns": self.duration_turns,
            "requires_item": self.requires_item,
            "bring_count": self.bring_count,
            "restricted_count": self.restricted_count,
        }


@dataclass
class MechanicEffect:
    """特殊ギミックの効果"""
    name: str
    japanese_name: str
    stat_multiplier: Dict[str, float] = field(default_factory=dict)  # ステータス倍率
    hp_multiplier: float = 1.0          # HP倍率 (ダイマックス)
    move_power_modifier: float = 1.0    # 技威力倍率
    type_change: bool = False           # タイプ変更あり (テラスタル)
    stab_boost: float = 1.5             # タイプ一致ボーナス
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "japanese_name": self.japanese_name,
            "stat_multiplier": self.stat_multiplier,
            "hp_multiplier": self.hp_multiplier,
            "move_power_modifier": self.move_power_modifier,
            "type_change": self.type_change,
        }


# ===== 世代別設定 =====

GENERATION_CONFIGS: Dict[int, GenerationConfig] = {
    6: GenerationConfig(
        gen=6,
        name="XY",
        full_name="X・Y / ORAS",
        special_mechanic=SpecialMechanic.MEGA,
        uses_per_battle=1,
        duration_turns=0,  # 永続
        requires_item=True,  # メガストーン必須
        restricted_count=0,  # VGC2014-2016
    ),
    7: GenerationConfig(
        gen=7,
        name="SM",
        full_name="Sun・Moon / USUM",
        special_mechanic=SpecialMechanic.ZMOVE,
        uses_per_battle=1,
        duration_turns=0,  # 1回の技発動
        requires_item=True,  # Zクリスタル必須
        restricted_count=2,  # VGC2019
    ),
    8: GenerationConfig(
        gen=8,
        name="SwSh",
        full_name="Sword・Shield",
        special_mechanic=SpecialMechanic.DYNAMAX,
        uses_per_battle=1,
        duration_turns=3,  # 3ターン持続
        requires_item=False,
        restricted_count=2,  # VGC2022
    ),
    9: GenerationConfig(
        gen=9,
        name="SV",
        full_name="Scarlet・Violet",
        special_mechanic=SpecialMechanic.TERASTAL,
        uses_per_battle=1,
        duration_turns=0,  # 永続
        requires_item=False,
        restricted_count=2,  # VGC2024 Regulation G
    ),
}


# ===== 特殊ギミック効果 =====

MECHANIC_EFFECTS: Dict[SpecialMechanic, MechanicEffect] = {
    SpecialMechanic.MEGA: MechanicEffect(
        name="Mega Evolution",
        japanese_name="メガシンカ",
        stat_multiplier={
            # 各メガシンカで異なるが、一般的に合計100上昇
            "total_boost": 100
        },
        move_power_modifier=1.0,
    ),
    SpecialMechanic.ZMOVE: MechanicEffect(
        name="Z-Move",
        japanese_name="Zワザ",
        move_power_modifier=1.8,  # 平均的なZ技威力上昇
        stab_boost=1.5,
    ),
    SpecialMechanic.DYNAMAX: MechanicEffect(
        name="Dynamax",
        japanese_name="ダイマックス",
        hp_multiplier=2.0,  # HP2倍
        move_power_modifier=1.3,  # ダイマックス技は基本威力上昇
    ),
    SpecialMechanic.TERASTAL: MechanicEffect(
        name="Terastallization",
        japanese_name="テラスタル",
        type_change=True,
        stab_boost=2.0,  # テラスタイプ一致は2倍
    ),
}


# ===== ダイマックス技威力表 =====

DYNAMAX_MOVE_POWER: Dict[str, Dict[int, int]] = {
    # 元技威力 -> ダイマックス技威力
    "physical": {
        40: 90, 50: 100, 60: 110, 70: 120, 80: 130,
        90: 130, 100: 140, 110: 140, 120: 140, 130: 140,
    },
    "special": {
        40: 90, 50: 100, 60: 110, 70: 120, 80: 130,
        90: 130, 100: 140, 110: 140, 120: 140, 130: 140,
    },
}


# ===== Zワザ威力表 =====

ZMOVE_POWER: Dict[int, int] = {
    # 元技威力 -> Zワザ威力
    40: 100, 50: 100, 55: 100, 60: 110, 65: 120,
    70: 140, 75: 140, 80: 160, 85: 160, 90: 175,
    95: 175, 100: 180, 110: 185, 120: 190, 130: 195,
}


class GenerationManager:
    """世代管理サービス"""
    
    def __init__(self, default_gen: int = 9):
        self._current_gen = default_gen
        self._mechanic_used = False  # ギミック使用済みフラグ
        self._dynamax_turns_left = 0
    
    @property
    def current_config(self) -> GenerationConfig:
        return GENERATION_CONFIGS.get(self._current_gen, GENERATION_CONFIGS[9])
    
    @property
    def current_mechanic(self) -> SpecialMechanic:
        return self.current_config.special_mechanic
    
    def set_generation(self, gen: int) -> None:
        """世代を切り替える"""
        if gen in GENERATION_CONFIGS:
            self._current_gen = gen
            self._mechanic_used = False
            self._dynamax_turns_left = 0
    
    def get_available_generations(self) -> List[Dict[str, Any]]:
        """利用可能な世代リストを返す"""
        return [
            {"gen": g.gen, "name": g.name, "full_name": g.full_name}
            for g in GENERATION_CONFIGS.values()
        ]
    
    def can_use_mechanic(self) -> bool:
        """特殊ギミックが使用可能か"""
        return not self._mechanic_used
    
    def use_mechanic(self) -> bool:
        """特殊ギミックを使用"""
        if self._mechanic_used:
            return False
        
        self._mechanic_used = True
        
        # ダイマックスの場合、ターン数をセット
        if self.current_mechanic == SpecialMechanic.DYNAMAX:
            self._dynamax_turns_left = self.current_config.duration_turns
        
        return True
    
    def tick_turn(self) -> None:
        """ターン経過処理"""
        if self._dynamax_turns_left > 0:
            self._dynamax_turns_left -= 1
    
    def is_dynamax_active(self) -> bool:
        """ダイマックス中か"""
        return self._dynamax_turns_left > 0
    
    def get_mechanic_effect(self) -> Optional[MechanicEffect]:
        """現在の世代のギミック効果を取得"""
        return MECHANIC_EFFECTS.get(self.current_mechanic)
    
    def calculate_zmove_power(self, base_power: int) -> int:
        """Zワザの威力を計算"""
        if self.current_mechanic != SpecialMechanic.ZMOVE:
            return base_power
        
        # 最も近い威力を取得
        for bp, zp in sorted(ZMOVE_POWER.items()):
            if base_power <= bp:
                return zp
        return 200  # 最大威力
    
    def calculate_dynamax_power(self, base_power: int, category: str = "physical") -> int:
        """ダイマックス技の威力を計算"""
        if self.current_mechanic != SpecialMechanic.DYNAMAX:
            return base_power
        
        power_table = DYNAMAX_MOVE_POWER.get(category, DYNAMAX_MOVE_POWER["physical"])
        
        # 最も近い威力を取得
        for bp, dp in sorted(power_table.items()):
            if base_power <= bp:
                return dp
        return 140  # 最大威力
    
    def get_terastal_stab(self, move_type: str, tera_type: str, original_types: List[str]) -> float:
        """テラスタル時のタイプ一致ボーナスを計算"""
        if self.current_mechanic != SpecialMechanic.TERASTAL:
            return 1.5 if move_type in original_types else 1.0
        
        is_tera_stab = move_type == tera_type
        is_original_stab = move_type in original_types
        
        if is_tera_stab and is_original_stab:
            return 2.25  # 両方一致
        elif is_tera_stab or is_original_stab:
            return 1.5   # どちらか一致
        else:
            return 1.0   # 不一致


# Singleton
_generation_manager = None

def get_generation_manager(default_gen: int = 9) -> GenerationManager:
    global _generation_manager
    if _generation_manager is None:
        _generation_manager = GenerationManager(default_gen)
    return _generation_manager


def set_generation(gen: int) -> GenerationConfig:
    """世代を切り替えて設定を返す"""
    manager = get_generation_manager()
    manager.set_generation(gen)
    return manager.current_config
