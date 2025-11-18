"""Optional HTTP interface around evaluate_position."""

from __future__ import annotations

from typing import Any, Dict

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover - optional dependency
    raise RuntimeError(
        "FastAPI is not installed. Run `pip install fastapi uvicorn` to use the HTTP API."
    ) from exc

from predictor.core.position_evaluator import evaluate_position


class EvaluateRequest(BaseModel):
    team_a_pokepaste: str
    team_b_pokepaste: str
    battle_log: Dict[str, Any]
    estimated_evs: Dict[str, Dict[str, Dict[str, int]]]
    algorithm: str = "heuristic"


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
    response = evaluate_position(
        payload.team_a_pokepaste,
        payload.team_b_pokepaste,
        payload.battle_log,
        payload.estimated_evs,
        payload.algorithm,
    )
    return response
