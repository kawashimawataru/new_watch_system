"""Effort value estimation with Bayesian updates."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from predictor.data.showdown_loader import ShowdownDataRepository

StatDict = Dict[str, int]
NATURE_MODIFIERS = {
    "Adamant": ("atk", "spa"),
    "Bashful": (None, None),
    "Bold": ("def", "atk"),
    "Brave": ("atk", "spe"),
    "Calm": ("spd", "atk"),
    "Careful": ("spd", "spa"),
    "Docile": (None, None),
    "Gentle": ("spd", "def"),
    "Hardy": (None, None),
    "Hasty": ("spe", "def"),
    "Impish": ("def", "spa"),
    "Jolly": ("spe", "spa"),
    "Lax": ("def", "spd"),
    "Lonely": ("atk", "def"),
    "Mild": ("spa", "def"),
    "Modest": ("spa", "atk"),
    "Naive": ("spe", "spd"),
    "Naughty": ("atk", "spd"),
    "Quiet": ("spa", "spe"),
    "Quirky": (None, None),
    "Rash": ("spa", "spd"),
    "Relaxed": ("def", "spe"),
    "Sassy": ("spd", "spe"),
    "Serious": (None, None),
    "Timid": ("spe", "atk"),
}


def normalize_name(name: str) -> str:
    return (
        name.replace(" ", "")
        .replace("-", "")
        .replace(".", "")
        .replace("'", "")
        .replace("_", "")
        .lower()
    )


@dataclass
class SpreadHypothesis:
    label: str
    nature: str
    evs: StatDict
    ivs: StatDict = field(default_factory=dict)
    probability: float = 1.0
    species: Optional[str] = None

    def normalized(self) -> "SpreadHypothesis":
        total = sum(max(ev, 0) for ev in self.evs.values())
        if total <= 510:
            return self
        ratio = 510 / total
        adjusted = {stat: int(ev * ratio) for stat, ev in self.evs.items()}
        return SpreadHypothesis(
            label=self.label, nature=self.nature, evs=adjusted, ivs=self.ivs, probability=self.probability
        )


@dataclass
class EVDistribution:
    pokemon: str
    hypotheses: List[SpreadHypothesis]

    def normalize(self) -> None:
        total = sum(h.probability for h in self.hypotheses)
        if total <= 0:
            # reset to uniform distribution
            weight = 1.0 / len(self.hypotheses)
            for hypo in self.hypotheses:
                hypo.probability = weight
            return
        for hypo in self.hypotheses:
            hypo.probability = hypo.probability / total

    def best_guess(self) -> SpreadHypothesis:
        return max(self.hypotheses, key=lambda h: h.probability)

    def to_weighted_map(self) -> Dict[str, float]:
        return {hypo.label: hypo.probability for hypo in self.hypotheses}


class EVEstimator:
    """Manage EV hypotheses per Pokémon using priors + Bayesian updates."""

    def __init__(
        self,
        prior_path: Optional[Path],
        data_repo: Optional[ShowdownDataRepository] = None,
        default_nature: str = "Timid",
    ):
        self.repo = data_repo or ShowdownDataRepository()
        self.default_nature = default_nature
        self.priors: Dict[str, List[SpreadHypothesis]] = self._load_priors(prior_path or Path("data/ev_priors.json"))
        self.player_distributions: Dict[str, Dict[str, EVDistribution]] = {"A": {}, "B": {}}

    def _load_priors(self, path: Path) -> Dict[str, List[SpreadHypothesis]]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        priors: Dict[str, List[SpreadHypothesis]] = {}
        for name, entries in raw.items():
            species_name = name
            priors[normalize_name(name)] = [
                SpreadHypothesis(
                    label=entry.get("label", "prior"),
                    nature=entry.get("nature", self.default_nature),
                    evs={k.lower(): int(v) for k, v in entry.get("evs", {}).items()},
                    ivs={k.lower(): int(v) for k, v in entry.get("ivs", {}).items()},
                    probability=float(entry.get("weight", 1.0)),
                    species=entry.get("species", species_name),
                )
                for entry in entries
            ]
        return priors

    def initialize_player(
        self,
        player_label: str,
        team_pokemon: Iterable[Dict[str, any]],
        overrides: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> None:
        overrides = overrides or {}
        player = player_label.upper()
        distributions = self.player_distributions[player]

        for poke in team_pokemon:
            name = poke["name"]
            normalized_name = normalize_name(name)
            nature = poke.get("nature") or self.default_nature
            base_spread = overrides.get(name) or poke.get("evs") or {}

            if base_spread:
                hypo = SpreadHypothesis(
                    label="manual",
                    nature=nature,
                    evs={k.lower(): int(v) for k, v in base_spread.items()},
                    ivs=poke.get("ivs") or {},
                    probability=1.0,
                    species=poke.get("species") or name,
                )
                distributions[name] = EVDistribution(pokemon=name, hypotheses=[hypo])
                continue

            priors = self.priors.get(normalized_name)
            if not priors:
                priors = [
                    SpreadHypothesis(
                        label="default",
                        nature=nature,
                        evs={"hp": 252, "spa": 252, "spe": 4},
                        ivs={},
                        probability=1.0,
                        species=poke.get("species") or name,
                    )
                ]
            hypotheses = []
            for base_hypo in priors:
                data = {**base_hypo.__dict__}
                data["species"] = poke.get("species") or name
                hypotheses.append(SpreadHypothesis(**data))
            total_prob = sum(h.probability for h in hypotheses)
            if total_prob > 0:
                for hypo in hypotheses:
                    hypo.probability /= total_prob
            distributions[name] = EVDistribution(pokemon=name, hypotheses=hypotheses)

    def export_estimates(self) -> Dict[str, Dict[str, SpreadHypothesis]]:
        payload: Dict[str, Dict[str, SpreadHypothesis]] = {"A": {}, "B": {}}
        for player, dists in self.player_distributions.items():
            for name, dist in dists.items():
                dist.normalize()
                payload[player][name] = dist.best_guess()
        return payload

    def update_from_log(self, battle_log: Dict[str, any], damage_analyzer) -> None:
        observations = battle_log.get("observations") or {}
        self._apply_speed_observations(observations.get("speed") or [])
        self._apply_damage_observations(observations.get("damage") or [], battle_log, damage_analyzer)

    def _apply_speed_observations(self, events: Iterable[Dict[str, any]]) -> None:
        for event in events:
            player = event.get("player", "A").upper()
            name = event.get("pokemon")
            if not name or name not in self.player_distributions[player]:
                continue
            constraint = event.get("constraint")
            value = event.get("value")
            if constraint not in {"min", "max"} or value is None:
                continue
            dist = self.player_distributions[player][name]
            for hypo in dist.hypotheses:
                stat = self._calculate_speed(name, hypo)
                sigma = 5.0
                if constraint == "min":
                    likelihood = self._sigmoid((stat - value) / sigma)
                else:
                    likelihood = self._sigmoid((value - stat) / sigma)
                hypo.probability *= likelihood
            dist.normalize()

    def _apply_damage_observations(self, events: Iterable[Dict[str, any]], battle_log, damage_analyzer) -> None:
        for event in events:
            defender_meta = event.get("defender") or {}
            player = defender_meta.get("player", "A").upper()
            name = defender_meta.get("pokemon")
            if not name or name not in self.player_distributions[player]:
                continue
            attacker_meta = event.get("attacker") or {}
            attacker_player = attacker_meta.get("player", "B").upper()
            attacker_name = attacker_meta.get("pokemon")
            move = event.get("move")
            if not attacker_name or not move:
                continue

            defender_dist = self.player_distributions[player][name]
            attacker_dist = self.player_distributions.get(attacker_player, {}).get(attacker_name)
            attacker_hypo = attacker_dist.best_guess() if attacker_dist else None

            context = {
                "weather": battle_log.get("state", {}).get("field", {}).get("weather"),
                "terrain": battle_log.get("state", {}).get("field", {}).get("terrain"),
                "isCrit": event.get("isCrit", False),
            }
            observed_percent = event.get("percent")
            if observed_percent is None:
                continue

            for hypo in defender_dist.hypotheses:
                damage_window = damage_analyzer.estimate_percent(
                    attacker_name,
                    attacker_hypo,
                    name,
                    hypo,
                    move,
                    context,
                    attacker_item=event.get("attackerItem"),
                    defender_item=event.get("defenderItem"),
                    attacker_status=event.get("attackerStatus"),
                    defender_status=event.get("defenderStatus"),
                    attacker_ability=event.get("attackerAbility"),
                    defender_ability=event.get("defenderAbility"),
                )
                if not damage_window:
                    continue
                min_pct, max_pct = damage_window.min_percent, damage_window.max_percent
                margin = 3.0
                if observed_percent < min_pct - margin or observed_percent > max_pct + margin:
                    likelihood = 0.05
                else:
                    center = (min_pct + max_pct) / 2
                    diff = abs(observed_percent - center)
                    sigma = max((max_pct - min_pct) / 2, 5.0)
                    likelihood = math.exp(-diff * diff / (2 * sigma * sigma))
                hypo.probability *= max(likelihood, 1e-3)
            defender_dist.normalize()

    def _calculate_speed(self, name: str, hypo: SpreadHypothesis, level: int = 50) -> int:
        species = self.repo.get_species(name)
        base = species.base_stats.get("spe", 0)
        iv = hypo.ivs.get("spe", 31) if hypo.ivs else 31
        ev = hypo.evs.get("spe", 0)
        stat = math.floor(((2 * base + iv + ev // 4) * level) / 100 + 5)
        inc, dec = NATURE_MODIFIERS.get(hypo.nature, (None, None))
        if inc == "spe":
            stat = math.floor(stat * 1.1)
        elif dec == "spe":
            stat = math.floor(stat * 0.9)
        return stat

    @staticmethod
    def _sigmoid(x: float) -> float:
        return 1.0 / (1.0 + math.exp(-x))
