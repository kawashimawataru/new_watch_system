"""Enrich legal actions with authoritative move metadata from Showdown."""

from __future__ import annotations

from typing import Dict

from predictor.core.models import ActionCandidate, BattleState
from predictor.data.showdown_loader import ShowdownDataRepository

TARGET_MAP = {
    "self": "self",
    "ally": "ally",
    "adjacentally": "ally",
    "adjacentallyorself": "ally",
    "adjacentfoe": "opponent",
    "adjacentfoes": "opponent",
    "adjacentfoeorself": "opponent",
    "randomnormal": "opponent",
    "any": "opponent",
    "normal": None,  # requires explicit selection, logs should provide slot
    "allyteam": "team",
    "foeside": "opponent",
    "alladjacentfoes": "spread",
    "alladjacent": "spread",
    "all": "spread",
    "allyfield": "team",
    "field": "team",
    "scripted": None,
}


def apply_move_metadata(battle_state: BattleState, data_repo: ShowdownDataRepository) -> None:
    """Ensure each action carries Showdown's target/effect metadata."""

    for actions in battle_state.legal_actions.values():
        for action in actions:
            _enrich_action(action, data_repo)


def _enrich_action(action: ActionCandidate, data_repo: ShowdownDataRepository) -> None:
    try:
        move = data_repo.get_move(action.move)
    except KeyError:
        return
    action.metadata.setdefault("type", move.type)
    action.metadata.setdefault("category", move.category)
    action.metadata.setdefault("basePower", move.base_power)
    action.metadata.setdefault("accuracy", move.accuracy)
    action.metadata.setdefault("priority", move.priority)
    action.metadata.setdefault("shortDesc", move.short_desc)
    if move.flags:
        flags = action.metadata.setdefault("moveFlags", {})
        for key, value in move.flags.items():
            flags.setdefault(key, value)
    action.metadata.setdefault("showdownTarget", move.target)
    if not action.target:
        fallback = _translate_target(move.target)
        if fallback:
            action.target = fallback
    if action.priority == 0 and move.priority != 0:
        action.priority = move.priority


def _translate_target(target: str | None) -> str | None:
    if not target:
        return None
    key = target.replace(" ", "").replace("-", "").lower()
    return TARGET_MAP.get(key)
