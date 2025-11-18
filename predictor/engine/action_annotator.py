"""Annotate legal actions with damage estimates."""

from __future__ import annotations

from typing import Dict, Optional

from predictor.core.models import ActionCandidate, BattleState, PokemonBattleState
from predictor.core.ev_estimator import SpreadHypothesis
from predictor.engine.damage_calculator import DamageCalculator


def annotate_actions(
    battle_state: BattleState,
    ev_estimates: Dict[str, Dict[str, SpreadHypothesis]],
    damage_calc: DamageCalculator,
) -> None:
    for player_label, actions in battle_state.legal_actions.items():
        controller = battle_state.player_a if player_label == "A" else battle_state.player_b
        opponents = battle_state.player_b if player_label == "A" else battle_state.player_a
        for action in actions:
            target_state = _resolve_target(action, controller, opponents)
            if not target_state:
                continue
            attacker_state = controller.active[action.slot] if action.slot < len(controller.active) else None
            attacker_estimate = ev_estimates.get(player_label, {}).get(action.actor)
            defender_estimate = ev_estimates.get("B" if player_label == "A" else "A", {}).get(target_state.name)
            if not defender_estimate:
                continue
            window = damage_calc.estimate_percent(
                action.actor,
                attacker_estimate,
                target_state.name,
                defender_estimate,
                action.move,
                {
                    "weather": battle_state.weather,
                    "terrain": battle_state.terrain,
                    "isCrit": action.metadata.get("is_crit"),
                },
                attacker_item=attacker_state.item if attacker_state else None,
                defender_item=target_state.item,
                attacker_status=attacker_state.status if attacker_state else None,
                defender_status=target_state.status,
                attacker_ability=attacker_state.ability if attacker_state else None,
                defender_ability=target_state.ability,
            )
            if window:
                action.metadata["estimatedDamage"] = {
                    "minPercent": window.min_percent,
                    "maxPercent": window.max_percent,
                    "koChance": window.ko_chance,
                    "hitChance": window.hit_chance,
                }


def _resolve_target(
    action: ActionCandidate,
    controller,
    opponents,
) -> Optional[PokemonBattleState]:
    if action.metadata.get("is_switch"):
        return None
    target_key = (action.target or "").lower()
    if target_key in ("self", "ally"):
        idx = action.slot if target_key == "self" else (0 if action.slot == 1 else 1)
        return controller.active[idx] if idx < len(controller.active) else None
    if target_key.startswith("a_slot"):
        idx = int(target_key.split("a_slot", 1)[1])
        return controller.active[idx] if idx < len(controller.active) else None
    if target_key.startswith("b_slot"):
        idx = int(target_key.split("b_slot", 1)[1])
        return opponents.active[idx] if idx < len(opponents.active) else None
    if target_key in {"opponent", "foe", "randomfoe"}:
        return opponents.active[0] if opponents.active else None
    if target_key == "spread" and opponents.active:
        return opponents.active[0]
    if opponents.active:
        return opponents.active[0]
    return None
