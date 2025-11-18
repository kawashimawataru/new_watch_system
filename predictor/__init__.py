"""
Predictor package entry point.

Expose the high-level evaluate_position function so application code can import
`predictor.evaluate_position` without reaching into the internals.
"""

from .core.position_evaluator import evaluate_position

__all__ = ["evaluate_position"]
