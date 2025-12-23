"""High-level entry point for evaluating a battle position."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from predictor.core.eval_algorithms.heuristic_eval import HeuristicEvaluator
from predictor.core.eval_algorithms.mcts_eval import MCTSEvaluator
from predictor.core.eval_algorithms.ml_eval import MLEvaluator
from predictor.core.ev_estimator import EVEstimator
from predictor.core.models import BattleState, EvaluationResult
from predictor.data.showdown_loader import ShowdownDataRepository
from predictor.engine.action_annotator import annotate_actions
from predictor.engine.damage_calculator import DamageCalculator
from predictor.engine.move_metadata import apply_move_metadata
from predictor.engine.observation_builder import build_observations
from predictor.engine.state_rebuilder import StateRebuilder
from predictor.engine.team_parser import TeamParser

DATA_REPO = ShowdownDataRepository()
TEAM_PARSER = TeamParser()
DAMAGE_CALCULATOR = DamageCalculator(DATA_REPO)
ALGORITHMS = {
    "heuristic": HeuristicEvaluator(),
    "mcts": MCTSEvaluator(),
    "ml": MLEvaluator(),
}


def evaluate_position(
    team_a_pokepaste: str,
    team_b_pokepaste: str,
    battle_log: Dict[str, Any],
    estimated_evs: Optional[Dict[str, Dict[str, Dict[str, int]]]] = None,
    algorithm: str = "heuristic",
    *,
    parser: Optional[TeamParser] = None,
    state_rebuilder: Optional[StateRebuilder] = None,
    ev_prior_path: Optional[Path] = None,
    return_battle_state: bool = False,
) -> Dict[str, Any]:
    """
    Evaluate a double battle position and return win rates plus move suggestions.
    """

    parser = parser or TEAM_PARSER
    estimated_evs = estimated_evs or {}

    team_a_entries = parser.parse_entries(team_a_pokepaste, estimated_evs.get("A") or {})
    team_b_entries = parser.parse_entries(team_b_pokepaste, estimated_evs.get("B") or {})

    team_metadata = {
        "A": {entry.name: {"nature": entry.nature, "ability": entry.ability, "species": entry.species} for entry in team_a_entries},
        "B": {entry.name: {"nature": entry.nature, "ability": entry.ability, "species": entry.species} for entry in team_b_entries},
    }

    battle_state = _build_battle_state(
        team_a_entries=team_a_entries,
        team_b_entries=team_b_entries,
        battle_log=battle_log,
        estimated_evs=estimated_evs,
        ev_prior_path=ev_prior_path,
        state_rebuilder=state_rebuilder,
        team_metadata=team_metadata,
    )

    evaluator = _get_evaluator(algorithm)
    try:
        evaluation: EvaluationResult = evaluator.evaluate(battle_state)
    except NotImplementedError as exc:
        raise RuntimeError(f"Algorithm '{algorithm}' is not ready yet.") from exc

    payload = evaluation.to_dict()
    if return_battle_state:
        return payload, battle_state
    return payload


def _build_battle_state(
    *,
    team_a_entries,
    team_b_entries,
    battle_log: Dict[str, Any],
    estimated_evs: Dict[str, Dict[str, Dict[str, int]]],
    ev_prior_path: Optional[Path],
    state_rebuilder: Optional[StateRebuilder],
    team_metadata: Dict[str, Dict[str, Dict[str, str]]],
) -> "BattleState":
    """Rebuild BattleState from inputs so other services (Hybrid/AlphaZero) can reuse it."""
    estimator = EVEstimator(ev_prior_path, data_repo=DATA_REPO)
    estimator.initialize_player("A", [entry.to_payload() for entry in team_a_entries], overrides=estimated_evs.get("A"))
    estimator.initialize_player("B", [entry.to_payload() for entry in team_b_entries], overrides=estimated_evs.get("B"))

    build_observations(battle_log)

    state_rebuilder = state_rebuilder or StateRebuilder(team_metadata=team_metadata)
    ev_assignments = estimator.export_estimates()
    battle_state = state_rebuilder.rebuild(battle_log, ev_assignments)
    apply_move_metadata(battle_state, DATA_REPO)
    estimator.update_from_log(battle_state.raw_log, DAMAGE_CALCULATOR)
    ev_assignments = estimator.export_estimates()
    battle_state.ev_estimates = ev_assignments

    annotate_actions(battle_state, ev_assignments, DAMAGE_CALCULATOR)
    return battle_state


def _get_evaluator(algorithm: str):
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Unsupported algorithm '{algorithm}'. Expected one of {list(ALGORITHMS)}")
    return ALGORITHMS[algorithm]
