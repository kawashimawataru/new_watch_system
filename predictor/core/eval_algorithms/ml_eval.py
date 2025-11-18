"""Future machine-learning based evaluator."""

from __future__ import annotations

from predictor.core.models import BattleState


class MLEvaluator:
    """
    Wrapper around a learned value / policy network.

    This placeholder documents the interface that Algorithm C will satisfy.
    """

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self.model = None

    def load(self):
        raise NotImplementedError("Model loading will be added when the ML baseline is trained.")

    def evaluate(self, battle_state: BattleState):
        raise NotImplementedError("ML evaluation is out of scope for P1.")
