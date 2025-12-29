import json
import os
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

@dataclass
class MoveData:
    id: str
    name: str
    type: str
    category: str
    base_power: int
    accuracy: int  # true becomes 101 or similar? Need to handle "true"
    priority: int
    target: str
    flags: Dict[str, int]
    secondary: Optional[Dict[str, Any]] = None
    drain: Optional[List[int]] = None
    recoil: Optional[List[int]] = None
    heal: Optional[List[int]] = None
    boosts: Optional[Dict[str, int]] = None
    status: Optional[str] = None
    volatile_status: Optional[str] = None
    self_boost: Optional[Dict[str, Any]] = None
    ignore_defensive: bool = False
    ignore_evasion: bool = False
    
    @classmethod
    def from_dict(cls, move_id: str, data: Dict[str, Any]) -> 'MoveData':
        # Handle accuracy being boolean (true = cannot miss)
        acc = data.get("accuracy", 100)
        if acc is True:
            acc = 101 # Special value for "always hits"
            
        return cls(
            id=move_id,
            name=data.get("name", ""),
            type=data.get("type", "Normal"),
            category=data.get("category", "Status"),
            base_power=data.get("basePower", 0),
            accuracy=acc,
            priority=data.get("priority", 0),
            target=data.get("target", "normal"),
            flags=data.get("flags", {}),
            secondary=data.get("secondary"),
            drain=data.get("drain"),
            recoil=data.get("recoil"),
            heal=data.get("heal"),
            boosts=data.get("boosts"),
            status=data.get("status"),
            volatile_status=data.get("volatileStatus"),
            self_boost=data.get("self") if "self" in data and "boosts" in data["self"] else None,
            ignore_defensive=data.get("ignoreDefensive", False),
            ignore_evasion=data.get("ignoreEvasion", False)
        )

@dataclass
class ItemData:
    id: str
    name: str
    desc: str
    is_berry: bool
    fling_power: int
    natural_gift_power: int
    natural_gift_type: Optional[str]
    mega_stone: Optional[str]
    is_choice: bool = False
    is_gem: bool = False
    boosts: Optional[Dict[str, int]] = None
    z_move: Optional[Any] = None  # Can be string (move name) or boolean
    z_move_from: Optional[str] = None
    z_move_type: Optional[str] = None
    plate: Optional[str] = None
    drive: Optional[str] = None
    memory: Optional[str] = None
    ignore_klutz: bool = False
    
    @classmethod
    def from_dict(cls, item_id: str, data: Dict[str, Any]) -> 'ItemData':
        return cls(
            id=item_id,
            name=data.get("name", ""),
            desc=data.get("desc", ""),
            is_berry=data.get("isBerry", False),
            fling_power=data.get("fling", {}).get("basePower", 0),
            natural_gift_power=data.get("naturalGift", {}).get("basePower", 0),
            natural_gift_type=data.get("naturalGift", {}).get("type"),
            mega_stone=data.get("megaStone"),
            is_choice=data.get("isChoice", False),
            is_gem=data.get("isGem", False),
            boosts=data.get("boosts"),
            z_move=data.get("zMove"),
            z_move_from=data.get("zMoveFrom"),
            z_move_type=data.get("zMoveType"),
            plate=data.get("onPlate"),
            drive=data.get("onDrive"),
            memory=data.get("onMemory"),
            ignore_klutz=data.get("ignoreKlutz", False)
        )

class ShowdownDataLoader:
    """ShowdownのJSONデータを読み込んでドメインオブジェクトを提供する"""
    
    _instance = None
    _moves: Dict[str, MoveData] = {}
    _items: Dict[str, ItemData] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ShowdownDataLoader, cls).__new__(cls)
            cls._instance._load_data()
        return cls._instance
    
    def _load_data(self):
        # パスは環境に合わせて調整
        base_path = os.path.join(os.getcwd(), "data", "showdown")
        moves_path = os.path.join(base_path, "moves.json")
        items_path = os.path.join(base_path, "items.json")
        
        # Load Moves
        if os.path.exists(moves_path):
            with open(moves_path, 'r') as f:
                raw_moves = json.load(f)
                for mid, mdata in raw_moves.items():
                    self._moves[mid] = MoveData.from_dict(mid, mdata)
        
        # Load Items
        if os.path.exists(items_path):
            with open(items_path, 'r') as f:
                raw_items = json.load(f)
                for iid, idata in raw_items.items():
                    self._items[iid] = ItemData.from_dict(iid, idata)

    def get_move(self, move_id: str) -> Optional[MoveData]:
        return self._moves.get(move_id.lower().replace(" ", "").replace("-", ""))

    def get_item(self, item_id: str) -> Optional[ItemData]:
        return self._items.get(item_id.lower().replace(" ", "").replace("-", ""))

# Global Accessor
def get_showdown_data() -> ShowdownDataLoader:
    return ShowdownDataLoader()
