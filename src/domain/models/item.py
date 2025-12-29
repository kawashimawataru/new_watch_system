from typing import Optional, Dict, Any
from src.domain.adapters.showdown_data_loader import get_showdown_data, ItemData
from src.domain.models.item_effects import ITEM_EFFECTS, ItemCategory

class Item:
    """
    ドメイン層のアイテムモデル
    Showdownのデータをラップしてロジックを提供する
    
    Staticなルール(item_effects.py)とDynamicなデータ(Showdown JSON)を統合する。
    """
    def __init__(self, item_id: str):
        self.item_id = item_id
        # Normalize ID similarly to ShowdownDataLoader
        self._normalized_id = item_id.lower().replace(" ", "").replace("-", "")
        self._data: Optional[ItemData] = get_showdown_data().get_item(self._normalized_id)
        self._static_effect = ITEM_EFFECTS.get(self._normalized_id)
        
    @property
    def name(self) -> str:
        return self._data.name if self._data else self.item_id
        
    @property
    def exists(self) -> bool:
        return self._data is not None

    @property
    def is_berry(self) -> bool:
        if self._data and self._data.is_berry:
            return True
        return self._static_effect.category == ItemCategory.BERRY if self._static_effect else False
        
    @property
    def is_choice(self) -> bool:
        if self._data and self._data.is_choice:
            return True
        return self._static_effect.category == ItemCategory.CHOICE if self._static_effect else False
        
    @property
    def is_gem(self) -> bool:
        return self._data.is_gem if self._data else False

    @property
    def fling_power(self) -> int:
        return self._data.fling_power if self._data else 0

    @property
    def natural_gift_power(self) -> int:
        return self._data.natural_gift_power if self._data else 0
        
    @property
    def natural_gift_type(self) -> Optional[str]:
        return self._data.natural_gift_type if self._data else None

    @property
    def mega_stone(self) -> Optional[str]:
        return self._data.mega_stone if self._data else None
        
    @property
    def z_move(self) -> Optional[Any]:
        return self._data.z_move if self._data else None
        
    @property
    def plate_type(self) -> Optional[str]:
        return self._data.plate if self._data else None
        
    @property
    def drive_type(self) -> Optional[str]:
        return self._data.drive if self._data else None
        
    @property
    def memory_type(self) -> Optional[str]:
        return self._data.memory if self._data else None
        
    def get_boosts(self) -> Dict[str, int]:
        """
        ランク補正（Absorb Bulbなど）を返す。
        """
        return self._data.boosts if self._data and self._data.boosts else {}

    def get_type_boost(self) -> Optional[str]:
        """
        タイプ強化アイテムの強化タイプを返す。
        """
        if not self._data:
            return None
            
        # 1. Plate / Memory / Drive / Gem
        if self.plate_type: return self.plate_type
        if self.memory_type: return self.memory_type
        # Gems check
        if self.is_gem and self.name.endswith(" Gem"):
            return self.name.replace(" Gem", "")
            
        # 2. Check Static Effect explicit definition (if added in future) or inferred from category
        if self._static_effect and self._static_effect.category == ItemCategory.BOOST:
            # item_effects.py doesn't currently store the boost TYPE, only description/multiplier.
            # So fallback to description parsing or hardcoded list.
            pass

        # 3. Fallback for specific known items (moved from previous implementation)
        known_boosts = {
            "charcoal": "Fire", "mysticwater": "Water", "magnet": "Electric",
            "miracleseed": "Grass", "nevermeltice": "Ice", "blackbelt": "Fighting",
            "poisonbarb": "Poison", "softsand": "Ground", "sharpbeak": "Flying",
            "twistedspoon": "Psychic", "silverpowder": "Bug", "hardstone": "Rock",
            "spelltag": "Ghost", "dragonfang": "Dragon", "blackglasses": "Dark",
            "metalcoat": "Steel", "silkscarf": "Normal", "fairyfeather": "Fairy"
        }
        if self._normalized_id in known_boosts:
            return known_boosts[self._normalized_id]
            
        return None

    def blocks_status_moves(self) -> bool:
        if self._static_effect:
            return self._static_effect.blocks_status
        return False

    def get_damage_modifier(self, move_type: str, is_physical: bool, is_super_effective: bool = False) -> float:
        """
        簡易的なダメージ倍率計算
        """
        modifier = 1.0
        
        # Type Boost
        boost_type = self.get_type_boost()
        if boost_type and boost_type == move_type:
            if self.is_gem:
                modifier *= 1.3
            else:
                modifier *= 1.2
                
        # Universal Boosts (Static Rules)
        if self._static_effect:
            if self._static_effect.category == ItemCategory.BOOST or \
               self._static_effect.category == ItemCategory.CHOICE:
                   
                # Choice Band/Specs
                if self.is_choice:
                    if self._normalized_id == "choiceband" and is_physical:
                        modifier *= 1.5
                    elif self._normalized_id == "choicespecs" and not is_physical:
                        modifier *= 1.5
                # Life Orb
                elif self._normalized_id == "lifeorb":
                    modifier *= 1.3
                # Expert Belt
                elif self._normalized_id == "expertbelt" and is_super_effective:
                    modifier *= 1.2
                # Muscle Band / Wise Glasses
                elif self._normalized_id == "muscleband" and is_physical:
                    modifier *= 1.1
                elif self._normalized_id == "wiseglasses" and not is_physical:
                    modifier *= 1.1

        return modifier

    def get_resist_berry_type(self) -> Optional[str]:
        if self._static_effect:
            return self._static_effect.resist_type
        return None
        
    def get_recoil_fraction(self) -> float:
        if self._static_effect and self._static_effect.recoil_pct > 0:
            return self._static_effect.recoil_pct / 100.0
        return 0.0

    def get_healing_fraction(self) -> float:
        """
        回復実や食べ残しの回復量
        """
        if self._normalized_id == "leftovers":
            return 1/16
        if self._static_effect and self._static_effect.heal_pct > 0:
            return self._static_effect.heal_pct
        return 0.0
