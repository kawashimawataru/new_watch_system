"""Derive EV-relevant observations (speed/damage) from battle logs."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def build_observations(battle_log: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Ensure battle_log contains an `observations` block."""

    observations = battle_log.setdefault("observations", {"speed": [], "damage": []})
    speed_seen = {
        (entry.get("player"), entry.get("pokemon"), entry.get("constraint"), entry.get("value"))
        for entry in observations.get("speed", [])
    }
    damage_seen = {
        (
            entry.get("move"),
            entry.get("attacker", {}).get("pokemon"),
            entry.get("defender", {}).get("pokemon"),
            entry.get("percent"),
        )
        for entry in observations.get("damage", [])
    }

    for turn in battle_log.get("turns", []):
        events = turn.get("events") or []
        prev_move = None
        for event in events:
            if event.get("type") != "move":
                continue
            _extract_speed(event, observations["speed"], speed_seen)
            if prev_move:
                _extract_relative_speed(prev_move, event, observations["speed"], speed_seen)
            _extract_damage(event, observations["damage"], damage_seen)
            prev_move = event

    return observations


def _extract_speed(event: Dict[str, Any], bucket: List[Dict[str, Any]], seen: set) -> None:
    value = event.get("speed") or event.get("effectiveSpeed")
    if value is None:
        return
    key = (event.get("player"), event.get("pokemon"), "min", value)
    if key in seen:
        return
    bucket.append(
        {
            "player": event.get("player"),
            "pokemon": event.get("pokemon"),
            "constraint": "min",
            "value": value,
        }
    )
    seen.add(key)


def _extract_relative_speed(
    prev_event: Dict[str, Any],
    current_event: Dict[str, Any],
    bucket: List[Dict[str, Any]],
    seen: set,
) -> None:
    if prev_event.get("priorityResolved") != current_event.get("priorityResolved"):
        return
    prev_speed = prev_event.get("speed") or prev_event.get("effectiveSpeed")
    if prev_speed is None:
        return
    key = (current_event.get("player"), current_event.get("pokemon"), "max", prev_speed)
    if key in seen:
        return
    bucket.append(
        {
            "player": current_event.get("player"),
            "pokemon": current_event.get("pokemon"),
            "constraint": "max",
            "value": prev_speed,
            "reason": f"acted after {prev_event.get('pokemon')}",
        }
    )
    seen.add(key)


def _extract_damage(
    event: Dict[str, Any],
    bucket: List[Dict[str, Any]],
    seen: set,
) -> None:
    percent = event.get("damagePercent")
    if percent is None:
        return
    key = (
        event.get("move"),
        event.get("pokemon"),
        event.get("targetPokemon"),
        percent,
    )
    if key in seen:
        return
    bucket.append(
        {
            "attacker": {"player": event.get("player"), "pokemon": event.get("pokemon")},
            "defender": {
                "player": event.get("targetPlayer"),
                "pokemon": event.get("targetPokemon"),
            },
            "move": event.get("move"),
            "percent": percent,
            "isCrit": event.get("isCrit", False),
            "attackerStatus": event.get("attackerStatus"),
            "defenderStatus": event.get("defenderStatus"),
        }
    )
    seen.add(key)
