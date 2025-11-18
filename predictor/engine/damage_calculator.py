"""
⚠️ DEPRECATED: このダメージ計算実装は非推奨です ⚠️

【理由】
- Multiscale等の重要特性が未実装
- テラスタル非対応
- @smogon/calc との比較で30%以上の計算誤差を確認

【代替】
predictor/engine/smogon_calc_wrapper.py を使用してください。
Pokémon Showdown公式の @smogon/calc を使用します。

【移行日】
2025年11月19日 (Phase 1.2完了)

【詳細】
docs/phase1_2_smogon_calc_integration.md を参照

---

Damage calculator built on top of Showdown data.
(Legacy implementation - for compatibility only)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

from predictor.core.ev_estimator import NATURE_MODIFIERS, SpreadHypothesis
from predictor.data.showdown_loader import ShowdownDataRepository

DEFAULT_LEVEL = 50
IV_DEFAULT = 31
STAT_ORDER = ["hp", "atk", "def", "spa", "spd", "spe"]
STATUS_DAMAGE_BOOST = {"brn", "par", "psn", "tox"}
OFFENSIVE_ITEMS = {"life orb", "choice specs", "choice band", "expert belt"}
DEFENSIVE_ITEMS = {"assault vest", "eviolite"}
ABILITY_ATTACK_BOOSTS = {
    "huge power": 2.0,
    "pure power": 2.0,
}
DEFENSIVE_ABILITIES = {
    "filter": 0.75,
    "solid rock": 0.75,
    "prism armor": 0.75,
    "thick fat": 0.5,
}
SPREAD_MODIFIER = 0.75


@dataclass
class PokemonSnapshot:
    name: str
    item: Optional[str]
    ability: Optional[str]
    types: tuple[str, ...]
    nature: str
    evs: Dict[str, int]
    ivs: Dict[str, int]
    level: int = DEFAULT_LEVEL
    status: Optional[str] = None


@dataclass
class DamageWindow:
    min_percent: float
    max_percent: float
    hit_chance: float
    ko_chance: float
    survival_chance: float


class DamageCalculator:
    def __init__(self, data_repo: Optional[ShowdownDataRepository] = None):
        self.repo = data_repo or ShowdownDataRepository()

    def build_snapshot(
        self,
        name: str,
        hypo: Optional[SpreadHypothesis],
        item: Optional[str] = None,
        ability: Optional[str] = None,
    ) -> PokemonSnapshot:
        species_name = hypo.species if hypo and hypo.species else name
        species = self.repo.get_species(species_name)
        evs = hypo.evs if hypo else {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
        ivs = hypo.ivs if hypo and hypo.ivs else {}
        return PokemonSnapshot(
            name=species.name,
            item=item,
            ability=ability,
            types=species.types,
            nature=hypo.nature if hypo else "Serious",
            evs=evs,
            ivs=ivs,
        )

    def estimate_percent(
        self,
        attacker_name: str,
        attacker_hypo: Optional[SpreadHypothesis],
        defender_name: str,
        defender_hypo: SpreadHypothesis,
        move_name: str,
        context: Optional[Dict[str, any]] = None,
        attacker_item: Optional[str] = None,
        defender_item: Optional[str] = None,
        attacker_status: Optional[str] = None,
        defender_status: Optional[str] = None,
        attacker_ability: Optional[str] = None,
        defender_ability: Optional[str] = None,
    ) -> Optional[DamageWindow]:
        context = context or {}
        try:
            move = self.repo.get_move(move_name)
        except KeyError:
            return None
        if move.category == "Status" or move.base_power <= 0:
            return None
        attacker = self.build_snapshot(attacker_name, attacker_hypo, item=attacker_item, ability=attacker_ability)
        defender = self.build_snapshot(defender_name, defender_hypo, item=defender_item, ability=defender_ability)
        attacker.status = attacker_status
        defender.status = defender_status
        damage_values, hit_chance = self._calculate_damage(attacker, defender, move, context)
        if not damage_values:
            return None
        hp = self._stat(defender, "hp", include_nature=False)
        percentages = [min(100.0, dmg / hp * 100) for dmg in damage_values]
        min_pct = min(percentages)
        max_pct = max(percentages)
        ko_count = sum(1 for pct in percentages if pct >= 100.0)
        ko_chance = ko_count / len(percentages)
        survival_chance = 1.0 - ko_chance
        return DamageWindow(
            min_percent=min_pct,
            max_percent=max_pct,
            hit_chance=hit_chance,
            ko_chance=ko_chance,
            survival_chance=survival_chance,
        )

    def _calculate_damage(self, attacker: PokemonSnapshot, defender: PokemonSnapshot, move, context):
        attack_stat_name = "atk" if move.category == "Physical" else "spa"
        defense_stat_name = "def" if move.category == "Physical" else "spd"

        attack = self._stat(attacker, attack_stat_name)
        defense = self._stat(defender, defense_stat_name)

        ability = (attacker.ability or "").lower()
        defender_ability = (defender.ability or "").lower()
        attacker_item = (attacker.item or "").lower()
        defender_item = (defender.item or "").lower()

        if ability in ABILITY_ATTACK_BOOSTS and move.category == "Physical":
            attack = math.floor(attack * ABILITY_ATTACK_BOOSTS[ability])
        if ability == "guts" and attacker.status in STATUS_DAMAGE_BOOST and move.category == "Physical":
            attack = math.floor(attack * 1.5)
        hustle_penalty = False
        if ability == "hustle" and move.category == "Physical":
            attack = math.floor(attack * 1.5)
            hustle_penalty = True

        if defender_item == "assault vest" and move.category == "Special":
            defense = math.floor(defense * 1.5)
        if defender_item == "eviolite":
            defense = math.floor(defense * 1.5)

        base = math.floor(((2 * attacker.level / 5 + 2) * move.base_power * attack / max(defense, 1)) / 50) + 2

        modifier = 1.0
        if move.type in attacker.types:
            modifier *= 1.5

        type_multiplier = self.repo.type_multiplier(move.type, defender.types)
        modifier *= type_multiplier

        if defender_ability in {"filter", "solid rock", "prism armor"} and type_multiplier > 1:
            modifier *= DEFENSIVE_ABILITIES[defender_ability]
        if defender_ability == "thick fat" and move.type in {"Fire", "Ice"}:
            modifier *= DEFENSIVE_ABILITIES[defender_ability]

        weather = (context.get("weather") or "").lower()
        if weather == "rain":
            if move.type == "Water":
                modifier *= 1.5
            elif move.type == "Fire":
                modifier *= 0.5
        elif weather == "sun":
            if move.type == "Fire":
                modifier *= 1.5
            elif move.type == "Water":
                modifier *= 0.5

        if move.is_spread:
            modifier *= SPREAD_MODIFIER

        if ability == "sheer force" and move.has_secondary:
            modifier *= 1.3

        if attacker.status == "brn" and move.category == "Physical" and ability != "guts":
            modifier *= 0.5

        if attacker_item == "life orb":
            modifier *= 1.3
        elif attacker_item == "choice band" and move.category == "Physical":
            modifier *= 1.5
        elif attacker_item == "choice specs" and move.category == "Special":
            modifier *= 1.5
        elif attacker_item == "expert belt" and type_multiplier > 1:
            modifier *= 1.2

        if context.get("isCrit"):
            modifier *= 1.5

        base_damage = max(1, math.floor(base * modifier))

        roll_values = [0.85 + i * 0.01 for i in range(16)]
        per_hit = [math.floor(base_damage * roll) for roll in roll_values]
        hit_counts = self._resolve_hit_counts(move.multihit)

        damages: List[int] = []
        for hits in hit_counts:
            for dmg in per_hit:
                damages.append(max(1, dmg * hits))

        accuracy = move.accuracy if move.accuracy is not None else 100.0
        if hustle_penalty:
            accuracy *= 0.8
        hit_chance = min(1.0, accuracy / 100.0)
        return damages, hit_chance

    @staticmethod
    def _resolve_hit_counts(multihit) -> List[int]:
        if not multihit:
            return [1]
        if isinstance(multihit, list) and len(multihit) == 2:
            start, end = multihit
            return list(range(int(start), int(end) + 1))
        try:
            count = int(multihit)
            return [count]
        except (TypeError, ValueError):
            return [1]

    def _stat(self, pokemon: PokemonSnapshot, stat: str, include_nature: bool = True) -> int:
        species = self.repo.get_species(pokemon.name)
        base = species.base_stats.get(stat, 0)
        ev = pokemon.evs.get(stat, 0)
        iv = pokemon.ivs.get(stat, IV_DEFAULT)
        if stat == "hp":
            if base == 1:
                return 1
            value = math.floor(((2 * base + iv + ev // 4) * pokemon.level) / 100) + pokemon.level + 10
            return value
        value = math.floor(((2 * base + iv + ev // 4) * pokemon.level) / 100) + 5
        if include_nature:
            inc, dec = NATURE_MODIFIERS.get(pokemon.nature, (None, None))
            if inc == stat:
                value = math.floor(value * 1.1)
            elif dec == stat:
                value = math.floor(value * 0.9)
        return value
