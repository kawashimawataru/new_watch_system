from typing import Optional, List, Dict, Any
from src.domain.adapters.showdown_data_loader import get_showdown_data, MoveData

class Move:
    """
    ドメイン層の技モデル
    Showdownのデータをラップしてロジックを提供する
    """
    def __init__(self, move_id: str):
        self.move_id = move_id
        self._data: Optional[MoveData] = get_showdown_data().get_move(move_id)
        
    @property
    def name(self) -> str:
        return self._data.name if self._data else self.move_id

    @property
    def type(self) -> str:
        return self._data.type if self._data else "Normal"
        
    @property
    def category(self) -> str:
        return self._data.category if self._data else "Physical"
        
    @property
    def base_power(self) -> float:
        return float(self._data.base_power) if self._data else 0.0
        
    @property
    def accuracy(self) -> int:
        return self._data.accuracy if self._data else 100
        
    @property
    def priority(self) -> int:
        return self._data.priority if self._data else 0

    @property
    def target(self) -> str:
        return self._data.target if self._data else "normal"

    @property
    def is_status(self) -> bool:
        return self.category == "Status"

    @property
    def is_physical(self) -> bool:
        return self.category == "Physical"
        
    @property
    def is_special(self) -> bool:
        return self.category == "Special"
        
    def is_spread(self) -> bool:
        """全体技かどうか"""
        return self.target in ["allAdjacent", "allAdjacentFoes"]

    @property
    def flags(self) -> Dict[str, int]:
        return self._data.flags if self._data else {}
        
    def makes_contact(self) -> bool:
        return "contact" in self.flags

    def is_protectable(self) -> bool:
        return "protect" in self.flags
        
    @property
    def secondary(self) -> Optional[Dict[str, Any]]:
        return self._data.secondary if self._data else None
        
    @property
    def drain(self) -> Optional[List[int]]:
        return self._data.drain if self._data else None
        
    @property
    def recoil(self) -> Optional[List[int]]:
        return self._data.recoil if self._data else None
        
    @property
    def heal(self) -> Optional[List[int]]:
        return self._data.heal if self._data else None
        
    @property
    def boosts(self) -> Optional[Dict[str, int]]:
        return self._data.boosts if self._data else None
        
    @property
    def status(self) -> Optional[str]:
        return self._data.status if self._data else None
        
    @property
    def volatile_status(self) -> Optional[str]:
        return self._data.volatile_status if self._data else None

    @property
    def self_boost(self) -> Optional[Dict[str, Any]]:
        return self._data.self_boost if self._data else None
        
    @property
    def ignore_defensive(self) -> bool:
        return self._data.ignore_defensive if self._data else False
        
    @property
    def ignore_evasion(self) -> bool:
        return self._data.ignore_evasion if self._data else False
