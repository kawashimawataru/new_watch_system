"""
Item Effects - アイテム効果を表すValue Objects

こだわり系、Assault Vest、Life Orbなどの効果を定義。
行動選択時のフィルタリングや評価に使用。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Set, Dict


class ItemCategory(Enum):
    """アイテムのカテゴリ"""
    CHOICE = "choice"           # こだわり系
    ASSAULT = "assault"         # Assault Vest
    BOOST = "boost"             # 火力・速度ブースト
    PROTECTION = "protection"   # 防御系
    BERRY = "berry"             # きのみ
    OTHER = "other"


@dataclass(frozen=True)
class ItemEffect:
    """アイテム効果の定義"""
    item_id: str
    category: ItemCategory
    # 基本特性
    locks_move: bool = False      # 技をロックするか
    blocks_status: bool = False    # 変化技を使えなくなるか
    
    # 補正
    stat_boost: Optional[str] = None  # 上昇するステータス
    boost_multiplier: float = 1.0  # ブースト倍率
    recoil_pct: float = 0.0       # 反動ダメージ (%)
    
    # 特殊効果
    resist_type: Optional[str] = None  # 半減する技タイプ (半減実)
    heal_pct: float = 0.0        # 回復割合 (オボンのみ等)
    trigger_threshold_pct: float = 0.0 # 発動するHP閾値 (25% or 50%)
    cures_status: bool = False    # 状態異常回復 (ラムのみ等)
    description: Optional[str] = None


# 主要アイテムの効果定義
ITEM_EFFECTS: Dict[str, ItemEffect] = {
    # --- こだわり系 (Choice Items) ---
    "choicescarf": ItemEffect(
        "choicescarf", ItemCategory.CHOICE,
        locks_move=True, stat_boost="speed", boost_multiplier=1.5,
        description="Speed x1.5, locks into one move"
    ),
    "choicespecs": ItemEffect(
        "choicespecs", ItemCategory.CHOICE,
        locks_move=True, stat_boost="special_attack", boost_multiplier=1.5,
        description="SpA x1.5, locks into one move"
    ),
    "choiceband": ItemEffect(
        "choiceband", ItemCategory.CHOICE,
        locks_move=True, stat_boost="attack", boost_multiplier=1.5,
        description="Atk x1.5, locks into one move"
    ),
    
    # --- 防御・耐久系 (Defensive) ---
    "assaultvest": ItemEffect(
        "assaultvest", ItemCategory.ASSAULT,
        blocks_status=True, stat_boost="special_defense", boost_multiplier=1.5,
        description="SpD x1.5, cannot use status moves"
    ),
    "eviolite": ItemEffect(
        "eviolite", ItemCategory.PROTECTION,
        boost_multiplier=1.5, description="Def/SpD x1.5 if not fully evolved"
    ),
    "focussash": ItemEffect(
        "focussash", ItemCategory.PROTECTION,
        description="Survives one KO hit at full HP"
    ),
    "safetygoggles": ItemEffect(
        "safetygoggles", ItemCategory.PROTECTION,
        description="Immune to powder moves and weather damage"
    ),
    "covertcloak": ItemEffect(
        "covertcloak", ItemCategory.PROTECTION,
        description="Immune to secondary effects"
    ),
    "rockyhelmet": ItemEffect(
        "rockyhelmet", ItemCategory.PROTECTION,
        recoil_pct=16.6, description="Attacker takes 1/6 damage on contact"
    ),

    # --- 火力ブースト系 (Damage Boost) ---
    "lifeorb": ItemEffect(
        "lifeorb", ItemCategory.BOOST,
        boost_multiplier=1.3, recoil_pct=10,
        description="Damage x1.3, takes 10% recoil"
    ),
    "expertbelt": ItemEffect(
        "expertbelt", ItemCategory.BOOST,
        boost_multiplier=1.2,
        description="Super effective moves x1.2"
    ),
    "weaknesspolicy": ItemEffect(
        "weaknesspolicy", ItemCategory.BOOST,
        description="+2 Atk/SpA when hit by super effective move"
    ),
    "throatspray": ItemEffect(
        "throatspray", ItemCategory.BOOST,
        description="+1 SpA after using sound move"
    ),
    
    # --- 回復実 (Healing Berries) ---
    "sitrusberry": ItemEffect(
        "sitrusberry", ItemCategory.BERRY,
        heal_pct=0.25, trigger_threshold_pct=0.5,
        description="Restores 1/4 HP when at 1/2 HP or less"
    ),
    "figyberry": ItemEffect(
        "figyberry", ItemCategory.BERRY,
        heal_pct=0.33, trigger_threshold_pct=0.25,
        description="Restores 1/3 HP when at 1/4 HP or less"
    ),
    "wikiberry": ItemEffect(
        "wikiberry", ItemCategory.BERRY,
        heal_pct=0.33, trigger_threshold_pct=0.25,
        description="Restores 1/3 HP when at 1/4 HP or less"
    ),
    "magoberry": ItemEffect(
        "magoberry", ItemCategory.BERRY,
        heal_pct=0.33, trigger_threshold_pct=0.25,
        description="Restores 1/3 HP when at 1/4 HP or less"
    ),
    "aguavberry": ItemEffect(
        "aguavberry", ItemCategory.BERRY,
        heal_pct=0.33, trigger_threshold_pct=0.25,
        description="Restores 1/3 HP when at 1/4 HP or less"
    ),
    "iapapaberry": ItemEffect(
        "iapapaberry", ItemCategory.BERRY,
        heal_pct=0.33, trigger_threshold_pct=0.25,
        description="Restores 1/3 HP when at 1/4 HP or less"
    ),

    # --- 状態異常回復実 (Status Berries) ---
    "lumberry": ItemEffect(
        "lumberry", ItemCategory.BERRY,
        cures_status=True, description="Cures any status condition"
    ),
    "chestoberry": ItemEffect(
        "chestoberry", ItemCategory.BERRY,
        description="Cures sleep"
    ),
    
    # --- 半減実 (Type-Resist Berries) ---
    "occaberry": ItemEffect("occaberry", ItemCategory.BERRY, resist_type="Fire"),
    "passhoberry": ItemEffect("passhoberry", ItemCategory.BERRY, resist_type="Water"),
    "wacanberry": ItemEffect("wacanberry", ItemCategory.BERRY, resist_type="Electric"),
    "rindoberry": ItemEffect("rindoberry", ItemCategory.BERRY, resist_type="Grass"),
    "yacheberry": ItemEffect("yacheberry", ItemCategory.BERRY, resist_type="Ice"),
    "chopleberry": ItemEffect("chopleberry", ItemCategory.BERRY, resist_type="Fighting"),
    "kebiaberry": ItemEffect("kebiaberry", ItemCategory.BERRY, resist_type="Poison"),
    "shucaberry": ItemEffect("shucaberry", ItemCategory.BERRY, resist_type="Ground"),
    "cobaberry": ItemEffect("cobaberry", ItemCategory.BERRY, resist_type="Flying"),
    "payapaberry": ItemEffect("payapaberry", ItemCategory.BERRY, resist_type="Psychic"),
    "tangaberry": ItemEffect("tangaberry", ItemCategory.BERRY, resist_type="Bug"),
    "chartiberry": ItemEffect("chartiberry", ItemCategory.BERRY, resist_type="Rock"),
    "kasibberry": ItemEffect("kasibberry", ItemCategory.BERRY, resist_type="Ghost"),
    "habanberry": ItemEffect("habanberry", ItemCategory.BERRY, resist_type="Dragon"),
    "colburberry": ItemEffect("colburberry", ItemCategory.BERRY, resist_type="Dark"),
    "babiriberry": ItemEffect("babiriberry", ItemCategory.BERRY, resist_type="Steel"),
    "roseliberry": ItemEffect("roseliberry", ItemCategory.BERRY, resist_type="Fairy"),
    "chilanberry": ItemEffect("chilanberry", ItemCategory.BERRY, resist_type="Normal"),

    # --- ハーブ・便利系 (Utility) ---
    "whiteherb": ItemEffect(
        "whiteherb", ItemCategory.OTHER,
        description="Restores lowered stats"
    ),
    "mentalherb": ItemEffect(
        "mentalherb", ItemCategory.OTHER,
        description="Cures infatuation, Taunt, Encore, etc."
    ),
    "powerherb": ItemEffect(
        "powerherb", ItemCategory.OTHER,
        description="Single-turn two-turn moves"
    ),
    "roomservice": ItemEffect(
        "roomservice", ItemCategory.OTHER,
        description="-1 Speed when Trick Room activates"
    ),
    "ejectbutton": ItemEffect(
        "ejectbutton", ItemCategory.OTHER,
        description="Switch out after taking a hit"
    ),
    "redcard": ItemEffect(
        "redcard", ItemCategory.OTHER,
        description="Force opponent to switch after taking a hit"
    ),
    "clearamulet": ItemEffect(
        "clearamulet", ItemCategory.PROTECTION,
        description="Prevents stat drops"
    ),
    
    # --- 能力上昇系 (Misc) ---
    "boosterenergy": ItemEffect(
        "boosterenergy", ItemCategory.BOOST,
        description="Activates Protosynthesis/Quark Drive"
    ),
    
    # --- タイプ強化系 ---
    "charcoal": ItemEffect("charcoal", ItemCategory.BOOST, boost_multiplier=1.2, description="Fire x1.2"),
    "mysticwater": ItemEffect("mysticwater", ItemCategory.BOOST, boost_multiplier=1.2, description="Water x1.2"),
    "miracleseed": ItemEffect("miracleseed", ItemCategory.BOOST, boost_multiplier=1.2, description="Grass x1.2"),
    "magnet": ItemEffect("magnet", ItemCategory.BOOST, boost_multiplier=1.2, description="Electric x1.2"),
    "hardstone": ItemEffect("hardstone", ItemCategory.BOOST, boost_multiplier=1.2, description="Rock x1.2"),
    "nevermeltice": ItemEffect("nevermeltice", ItemCategory.BOOST, boost_multiplier=1.2, description="Ice x1.2"),
    "blackglasses": ItemEffect("blackglasses", ItemCategory.BOOST, boost_multiplier=1.2, description="Dark x1.2"),
    "spelltag": ItemEffect("spelltag", ItemCategory.BOOST, boost_multiplier=1.2, description="Ghost x1.2"),
    "dragonfang": ItemEffect("dragonfang", ItemCategory.BOOST, boost_multiplier=1.2, description="Dragon x1.2"),
    "twistedspoon": ItemEffect("twistedspoon", ItemCategory.BOOST, boost_multiplier=1.2, description="Psychic x1.2"),
    "sharpbeak": ItemEffect("sharpbeak", ItemCategory.BOOST, boost_multiplier=1.2, description="Flying x1.2"),
    "poisonbarb": ItemEffect("poisonbarb", ItemCategory.BOOST, boost_multiplier=1.2, description="Poison x1.2"),
    "softsand": ItemEffect("softsand", ItemCategory.BOOST, boost_multiplier=1.2, description="Ground x1.2"),
    "silkscarf": ItemEffect("silkscarf", ItemCategory.BOOST, boost_multiplier=1.2, description="Normal x1.2"),
    "silverpowder": ItemEffect("silverpowder", ItemCategory.BOOST, boost_multiplier=1.2, description="Bug x1.2"),
    "metalcoat": ItemEffect("metalcoat", ItemCategory.BOOST, boost_multiplier=1.2, description="Steel x1.2"),
}


def get_item_effect(item_name: str) -> Optional[ItemEffect]:
    """アイテム名から効果を取得"""
    if not item_name:
        return None
    
    # 正規化: 小文字化、スペース・ハイフン除去
    normalized = item_name.lower().replace(" ", "").replace("-", "").replace("_", "")
    return ITEM_EFFECTS.get(normalized)


def is_choice_item(item_name: str) -> bool:
    """こだわり系アイテムかどうかを判定"""
    effect = get_item_effect(item_name)
    return effect is not None and effect.category == ItemCategory.CHOICE


def blocks_status_moves(item_name: str) -> bool:
    """変化技を使えなくするアイテムかどうかを判定"""
    effect = get_item_effect(item_name)
    return effect is not None and effect.blocks_status


def get_boost_multiplier(item_name: str) -> float:
    """火力/ステータスブースト倍率を取得"""
    effect = get_item_effect(item_name)
    if effect:
        return effect.boost_multiplier
    return 1.0


# こだわり系アイテムのセット（高速判定用）
CHOICE_ITEMS: Set[str] = {
    "choicescarf", "choicespecs", "choiceband"
}

# 変化技使用不可アイテムのセット
STATUS_BLOCKING_ITEMS: Set[str] = {
    "assaultvest"
}

