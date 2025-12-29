"""
Move Properties - 技の特性を表すValue Objects

技の優先度、特殊な条件、カテゴリなどを定義する。
VGCバトルにおける技選択の判断材料として使用。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict


class MoveCategory(Enum):
    """技のカテゴリ"""
    PHYSICAL = "Physical"
    SPECIAL = "Special"
    STATUS = "Status"


@dataclass(frozen=True)
class MovePriority:
    """技の優先度情報"""
    move_id: str
    priority: int  # -7 ~ +5
    conditional: bool = False  # 条件付き先制技か
    description: Optional[str] = None


# 主要な先制技・優先度変更技の定義
PRIORITY_MOVES: Dict[str, MovePriority] = {
    # +5
    "helpinghand": MovePriority("helpinghand", 5),
    
    # +4
    "protect": MovePriority("protect", 4),
    "detect": MovePriority("detect", 4),
    "spikyshield": MovePriority("spikyshield", 4),
    "silktrap": MovePriority("silktrap", 4),
    "banefulbunker": MovePriority("banefulbunker", 4),
    "kingsshield": MovePriority("kingsshield", 4),
    
    # +3
    "fakeout": MovePriority("fakeout", 3, conditional=True, 
                            description="First turn only"),
    "firstimpression": MovePriority("firstimpression", 3, conditional=True,
                                     description="First turn only"),
    
    # +2
    "extremespeed": MovePriority("extremespeed", 2),
    "feint": MovePriority("feint", 2),
    
    # +1
    "quickattack": MovePriority("quickattack", 1),
    "machpunch": MovePriority("machpunch", 1),
    "bulletpunch": MovePriority("bulletpunch", 1),
    "iceshard": MovePriority("iceshard", 1),
    "shadowsneak": MovePriority("shadowsneak", 1),
    "aquajet": MovePriority("aquajet", 1),
    "accelerock": MovePriority("accelerock", 1),
    "jetpunch": MovePriority("jetpunch", 1),
    "suckerpunch": MovePriority("suckerpunch", 1, conditional=True,
                                description="Fails if opponent uses status move"),
    "thunderclap": MovePriority("thunderclap", 1, conditional=True,
                                description="Fails if opponent uses status move"),
    "upperhand": MovePriority("upperhand", 3, conditional=True,
                              description="Fails if opponent doesn't use priority"),
    
    # +0 だが重要な技
    "tailwind": MovePriority("tailwind", 0, description="Speed control"),
    "trickroom": MovePriority("trickroom", -7, description="Speed control"),
    
    # -1 ~ -7
    "vitalthrow": MovePriority("vitalthrow", -1),
    "focuspunch": MovePriority("focuspunch", -3),
    "avalanche": MovePriority("avalanche", -4),
    "counter": MovePriority("counter", -5),
    "mirrorcoat": MovePriority("mirrorcoat", -5),
}


def get_move_priority(move_id: str) -> int:
    """技の優先度を取得"""
    move_id_lower = move_id.lower().replace(" ", "").replace("-", "")
    if move_id_lower in PRIORITY_MOVES:
        return PRIORITY_MOVES[move_id_lower].priority
    return 0


def is_priority_move(move_id: str) -> bool:
    """先制技かどうかを判定"""
    return get_move_priority(move_id) > 0


def is_conditional_priority(move_id: str) -> bool:
    """条件付き先制技かどうかを判定"""
    move_id_lower = move_id.lower().replace(" ", "").replace("-", "")
    if move_id_lower in PRIORITY_MOVES:
        return PRIORITY_MOVES[move_id_lower].conditional
    return False


# 技の評価スコアボーナス（行動予測用）
MOVE_SCORE_BONUS: Dict[str, int] = {
    # 防御技（高優先度）
    "protect": 40,
    "detect": 40,
    "spikyshield": 40,
    "silktrap": 35,
    
    # 速度操作（非常に重要）
    "tailwind": 60,
    "trickroom": 50,
    "icywind": 25,
    
    # 強力な先制技
    "fakeout": 50,  # 初ターン限定
    "extremespeed": 35,
    "firstimpression": 45,  # 初ターン限定
    
    # 条件付き先制技
    "suckerpunch": 25,
    "thunderclap": 30,
    
    # 通常の先制技
    "bulletpunch": 15,
    "machpunch": 15,
    "aquajet": 15,
    "iceshard": 15,
    "shadowsneak": 15,
    "quickattack": 10,
    
    # サポート技
    "helpinghand": 30,
    "ragepowder": 45,
    "followme": 45,
    "allyswitch": 20,
    "spore": 60,  # 催眠は非常に強力
    
    # 全体技ボーナス
    "heatwave": 15,
    "earthquake": 15,
    "rockslide": 15,
    "dazzlinggleam": 10,
    "bleakwindstorm": 15,
    "sandsearstorm": 15,
}


def get_move_score_bonus(move_id: str) -> int:
    """技の評価スコアボーナスを取得"""
    move_id_lower = move_id.lower().replace(" ", "").replace("-", "")
    return MOVE_SCORE_BONUS.get(move_id_lower, 0)
