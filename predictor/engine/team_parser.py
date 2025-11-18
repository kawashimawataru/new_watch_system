"""Utilities for converting Pokepaste text into Showdown-ready team strings."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_EV_PATTERN = re.compile(r"(\d+)\s+([A-Za-z]+)")
_STAT_ALIAS = {
    "hp": "HP",
    "atk": "Atk",
    "def": "Def",
    "spa": "SpA",
    "spd": "SpD",
    "spe": "Spe",
}


@dataclass
class ParsedPokemon:
    """Structured representation of a Pokepaste entry."""

    name: str
    species: Optional[str]
    item: Optional[str]
    ability: Optional[str]
    moves: List[str]
    nature: Optional[str]
    tera_type: Optional[str]
    level: int = 50
    evs: Dict[str, int] = field(default_factory=dict)
    ivs: Dict[str, int] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "species": self.species or self.name,
            "item": self.item,
            "ability": self.ability,
            "moves": self.moves,
            "nature": self.nature,
            "teraType": self.tera_type,
            "level": self.level,
            "evs": self.evs,
            "ivs": self.ivs,
        }


class TeamParser:
    """Convert Pokepaste strings to Showdown team format."""

    def __init__(self, template_path: Optional[Path] = None):
        self.ev_templates = self._load_templates(template_path)

    @staticmethod
    def _load_templates(template_path: Optional[Path]) -> Dict[str, Dict[str, int]]:
        if template_path is None:
            return {}
        if not template_path.exists():
            raise FileNotFoundError(f"EV template file not found: {template_path}")
        with template_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return {name.lower(): {k.lower(): v for k, v in stats.items()} for name, stats in data.items()}

    def parse_entries(
        self,
        pokepaste: str,
        estimated_evs: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> List[ParsedPokemon]:
        normalized_evs = self._normalize_ev_map(estimated_evs or {})
        parsed_entries = []
        for block in self._split_blocks(pokepaste):
            parsed_entries.append(self._parse_block(block, normalized_evs))
        return parsed_entries

    def parse_to_showdown(
        self,
        pokepaste: str,
        estimated_evs: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> str:
        entries = self.parse_entries(pokepaste, estimated_evs)
        return "\n\n".join(self._to_showdown_format(entry) for entry in entries)

    @staticmethod
    def _split_blocks(pokepaste: str) -> Iterable[List[str]]:
        buffer: List[str] = []
        for raw_line in pokepaste.splitlines():
            line = raw_line.rstrip()
            if not line:
                if buffer:
                    yield buffer
                    buffer = []
                continue
            buffer.append(line)
        if buffer:
            yield buffer

    def _parse_block(
        self,
        block: Iterable[str],
        estimated_evs: Dict[str, Dict[str, int]],
    ) -> ParsedPokemon:
        block_iter = list(block)
        header = block_iter[0]
        name, item, species = self._parse_header(header)

        ability = None
        nature = None
        tera = None
        level = 50
        moves: List[str] = []
        evs: Dict[str, int] = {}
        ivs: Dict[str, int] = {}

        for line in block_iter[1:]:
            if line.startswith("Ability:"):
                ability = line.split("Ability:", 1)[1].strip()
            elif line.startswith("Level:"):
                level = int(line.split("Level:", 1)[1].strip())
            elif line.startswith("Tera Type:"):
                tera = line.split("Tera Type:", 1)[1].strip()
            elif line.startswith("EVs:"):
                evs = self._parse_stat_line(line)
            elif line.startswith("IVs:"):
                ivs = self._parse_stat_line(line)
            elif line.endswith("Nature"):
                nature = line.replace("Nature", "").strip()
            elif line.startswith("- "):
                moves.append(line[2:].strip())

        evs = self._apply_ev_defaults(species or name, evs, estimated_evs)

        return ParsedPokemon(
            name=name,
            species=species or name,
            item=item,
            ability=ability,
            moves=moves,
            nature=nature,
            tera_type=tera,
            level=level,
            evs=evs,
            ivs=ivs,
        )

    @staticmethod
    def _parse_header(header: str) -> (str, Optional[str], Optional[str]):
        item = None
        if "@" in header:
            header, item = header.split("@", 1)
        header = header.strip()
        species = None
        name = header
        if "(" in header and ")" in header:
            nickname, rest = header.split("(", 1)
            species = rest.split(")", 1)[0].strip()
            name = nickname.strip() or species
        return name.strip(), (item.strip() if item else None), species

    @staticmethod
    def _parse_stat_line(line: str) -> Dict[str, int]:
        stats: Dict[str, int] = {}
        for amount, stat in _EV_PATTERN.findall(line):
            stats[stat.lower()] = int(amount)
        return stats

    def _apply_ev_defaults(
        self,
        name: str,
        evs: Dict[str, int],
        estimated_evs: Dict[str, Dict[str, int]],
    ) -> Dict[str, int]:
        normalized_name = name.lower()
        if evs:
            return {k.lower(): v for k, v in evs.items()}
        if normalized_name in estimated_evs:
            return estimated_evs[normalized_name]
        if normalized_name in self.ev_templates:
            return self.ev_templates[normalized_name]
        # Fallback to a simple 4/252/252 spread
        return {"hp": 4, "spa": 252, "spe": 252}

    @staticmethod
    def _normalize_ev_map(raw: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
        normalized: Dict[str, Dict[str, int]] = {}
        for name, stats in raw.items():
            normalized[name.lower()] = {k.lower(): v for k, v in stats.items()}
        return normalized

    def _to_showdown_format(self, pokemon: ParsedPokemon) -> str:
        lines = []
        header = pokemon.name
        if pokemon.item:
            header += f" @ {pokemon.item}"
        lines.append(header)

        if pokemon.ability:
            lines.append(f"Ability: {pokemon.ability}")
        lines.append(f"Level: {pokemon.level}")
        if pokemon.tera_type:
            lines.append(f"Tera Type: {pokemon.tera_type}")
        if pokemon.evs:
            lines.append(f"EVs: {self._format_stats(pokemon.evs)}")
        if pokemon.ivs:
            lines.append(f"IVs: {self._format_stats(pokemon.ivs)}")
        if pokemon.nature:
            lines.append(f"{pokemon.nature} Nature")
        for move in pokemon.moves:
            lines.append(f"- {move}")
        return "\n".join(lines)

    @staticmethod
    def _format_stats(stats: Dict[str, int]) -> str:
        parts = []
        for key in ["hp", "atk", "def", "spa", "spd", "spe"]:
            if key in stats and stats[key] > 0:
                parts.append(f"{stats[key]} {_STAT_ALIAS.get(key, key.title())}")
        return " / ".join(parts)
