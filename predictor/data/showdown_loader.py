"""Load Pokémon Showdown data files (pokedex, moves, type chart)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "showdown"


def _normalize_key(name: str) -> str:
    return (
        name.replace(" ", "")
        .replace("-", "")
        .replace(".", "")
        .replace("'", "")
        .replace(":", "")
        .replace("_", "")
        .lower()
    )


@dataclass
class SpeciesEntry:
    name: str
    types: tuple[str, ...]
    base_stats: Dict[str, int]
    abilities: Dict[str, str]


@dataclass
class MoveEntry:
    name: str
    type: str
    base_power: int
    accuracy: Optional[float]
    category: str
    target: str
    priority: int
    is_spread: bool
    multihit: Optional[Any] = None
    has_secondary: bool = False
    short_desc: Optional[str] = None
    desc: Optional[str] = None
    flags: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ItemEntry:
    name: str
    short_desc: Optional[str]
    desc: Optional[str]
    flags: Dict[str, Any]


class ShowdownDataRepository:
    """Lazy loader for Showdown's JSON resources."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or DATA_DIR
        self._pokedex = None
        self._moves = None
        self._type_chart = None
        self._items = None

    @property
    def pokedex(self) -> Dict[str, Any]:
        if self._pokedex is None:
            self._pokedex = self._load_json("pokedex.json")
        return self._pokedex

    @property
    def moves(self) -> Dict[str, Any]:
        if self._moves is None:
            self._moves = self._load_json("moves.json")
        return self._moves

    @property
    def type_chart(self) -> Dict[str, Any]:
        if self._type_chart is None:
            self._type_chart = self._load_json("typechart.json")
        return self._type_chart

    @property
    def items(self) -> Dict[str, Any]:
        if self._items is None:
            self._items = self._load_json("items.json")
        return self._items

    def _load_json(self, filename: str) -> Dict[str, Any]:
        path = self.data_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Required Showdown data file '{filename}' not found in {self.data_dir}. "
                "Run scripts/fetch_showdown_data.py to download the latest dataset."
            )
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @lru_cache(maxsize=512)
    def get_species(self, name: str) -> SpeciesEntry:
        key = _normalize_key(name)
        data = self.pokedex.get(key)
        if not data:
            raise KeyError(f"Unknown species '{name}'. Please update pokedex.json.")
        return SpeciesEntry(
            name=data.get("name", name),
            types=tuple(data.get("types", [])),
            base_stats=data.get("baseStats", {}),
            abilities=data.get("abilities", {}),
        )

    @lru_cache(maxsize=2048)
    def get_move(self, name: str) -> MoveEntry:
        key = _normalize_key(name)
        data = self.moves.get(key)
        if not data:
            raise KeyError(f"Unknown move '{name}'. Please update moves.json.")
        accuracy = data.get("accuracy")
        if isinstance(accuracy, bool):
            accuracy = 100.0 if accuracy else 0.0
        elif accuracy is not None:
            accuracy = float(accuracy)
        return MoveEntry(
            name=data.get("name", name),
            type=data.get("type", "Normal"),
            base_power=int(data.get("basePower", 0) or 0),
            accuracy=accuracy,
            category=data.get("category", "Status"),
            target=data.get("target", "normal"),
            priority=int(data.get("priority", 0) or 0),
            is_spread=data.get("target", "") in {"allAdjacentFoes", "allAdjacent"},
            multihit=data.get("multihit"),
            has_secondary=bool(data.get("secondary") or data.get("secondaries")),
            short_desc=data.get("shortDesc"),
            desc=data.get("desc"),
            flags=data.get("flags") or {},
        )

    @lru_cache(maxsize=512)
    def get_item(self, name: str) -> ItemEntry:
        key = _normalize_key(name)
        data = self.items.get(key)
        if not data:
            raise KeyError(f"Unknown item '{name}'. Please update items.json.")
        return ItemEntry(
            name=data.get("name", name),
            short_desc=data.get("shortDesc"),
            desc=data.get("desc"),
            flags=data.get("flags") or {},
        )

    def type_multiplier(self, attack_type: str, defender_types: tuple[str, ...]) -> float:
        attack_key = attack_type.capitalize()
        chart = self.type_chart.get(attack_key)
        if not chart:
            return 1.0
        multiplier = 1.0
        for dtype in defender_types:
            dtype_key = dtype.capitalize()
            if dtype_key in chart.get("damageTaken", {}):
                category = chart["damageTaken"][dtype_key]
                # BattleTypeChart uses numeric codes: 0 neutral, 1 resist, 2 immune, 3 weak
                if category == 1:
                    multiplier *= 0.5
                elif category == 2:
                    multiplier *= 0.0
                elif category == 3:
                    multiplier *= 2.0
            else:
                # fallback to explicit tables if present
                multiplier *= chart.get("effectiveness", {}).get(dtype_key, 1.0)
        return multiplier


repository = ShowdownDataRepository()
