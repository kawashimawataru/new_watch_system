"""Optional HTTP interface around evaluate_position."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover - optional dependency
    raise RuntimeError(
        "FastAPI is not installed. Run `pip install fastapi uvicorn` to use the HTTP API."
    ) from exc

from predictor.core.models import BattleState
from predictor.core.position_evaluator import evaluate_position

try:
    from predictor.player.hybrid_strategist import HybridPrediction, HybridStrategist
    HYBRID_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    HybridStrategist = None  # type: ignore
    HybridPrediction = None  # type: ignore
    HYBRID_AVAILABLE = False


class EvaluateRequest(BaseModel):
    team_a_pokepaste: str
    team_b_pokepaste: str
    battle_log: Dict[str, Any]
    estimated_evs: Dict[str, Dict[str, Dict[str, int]]]
    algorithm: str = "heuristic"
    include_hybrid: bool = False


app = FastAPI(title="VGC Predictor", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/evaluate-position")
async def evaluate_position_endpoint(payload: EvaluateRequest):
    need_state = payload.include_hybrid
    result = evaluate_position(
        payload.team_a_pokepaste,
        payload.team_b_pokepaste,
        payload.battle_log,
        payload.estimated_evs,
        payload.algorithm,
        return_battle_state=need_state,
    )
    if not need_state:
        return result

    response, battle_state = result

    if payload.include_hybrid:
        summary = await _build_hybrid_summary(battle_state)
        if summary:
            response["hybridLanes"] = summary

    return response


# --- Hybrid bridge -------------------------------------------------------

_HYBRID_STRATEGIST: Optional[HybridStrategist] = None
_HYBRID_ERROR: Optional[str] = None


def _get_hybrid_strategist() -> Optional[HybridStrategist]:
    global _HYBRID_STRATEGIST, _HYBRID_ERROR
    if not HYBRID_AVAILABLE:
        return None
    if _HYBRID_ERROR:
        return None
    if _HYBRID_STRATEGIST:
        return _HYBRID_STRATEGIST

    project_root = Path(__file__).resolve().parents[2]
    fast_model = project_root / "models" / "fast_lane.pkl"
    alphazero_model = project_root / "models" / "policy_value_v1.pt"
    if not fast_model.exists():
        _HYBRID_ERROR = f"Fast-Lane model not found: {fast_model}"
        return None
    try:
        _HYBRID_STRATEGIST = HybridStrategist(
            fast_model_path=fast_model,
            mcts_rollouts=200,
            mcts_max_turns=30,
            use_alphazero=alphazero_model.exists(),
            alphazero_model_path=alphazero_model if alphazero_model.exists() else None,
            alphazero_rollouts=64,
        )
        return _HYBRID_STRATEGIST
    except Exception as exc:  # pragma: no cover - defensive
        _HYBRID_ERROR = str(exc)
        return None


async def _build_hybrid_summary(battle_state: BattleState) -> Optional[list[Dict[str, Any]]]:
    strategist = _get_hybrid_strategist()
    if strategist is None:
        return None

    fast_result, slow_result = strategist.predict_both(battle_state)
    lanes = [
        _serialize_lane("Fast-Lane", "fast", fast_result),
        _serialize_lane("Slow-Lane (MCTS)", "slow", slow_result),
    ]

    if strategist.use_alphazero:
        try:
            az_result = await strategist.predict_ultimate(battle_state)
            lanes.append(_serialize_lane("AlphaZero-Lane", "alphazero", az_result))
        except Exception:  # pragma: no cover - avoid crashing API
            pass

    return lanes


def _serialize_lane(label: str, key: str, result: HybridPrediction) -> Dict[str, Any]:
    return {
        "lane": key,
        "label": label,
        "p1WinRate": result.p1_win_rate,
        "p2WinRate": 1.0 - result.p1_win_rate,
        "confidence": result.confidence,
        "inferenceTimeMs": result.inference_time_ms,
        "recommendedAction": _serialize_action(result.recommended_action),
    }


def _serialize_action(action) -> Optional[Dict[str, Any]]:
    if action is None:
        return None
    return {
        "actor": getattr(action, "actor", None),
        "move": getattr(action, "move", None),
        "target": getattr(action, "target", None),
        "slot": getattr(action, "slot", None),
    }
