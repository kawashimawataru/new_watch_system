"""Placeholder for the shallow MCTS / Monte Carlo evaluator."""

from __future__ import annotations

from predictor.core.models import BattleState


class MCTSEvaluator:
    """
    Implements Algorithm B (shallow Monte Carlo tree search).

    The concrete rollout code requires access to a deterministic battle engine,
    so this file only contains the public interface for now.
    """

    def __init__(self, rollout_count: int = 128, depth: int = 2):
        self.rollout_count = rollout_count
        self.depth = depth

    def evaluate(self, battle_state: BattleState):
        raise NotImplementedError(
            "MCTS evaluation depends on the poke-env powered simulator "
            "and will be implemented after the heuristic baseline."
        )
