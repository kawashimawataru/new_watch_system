# VGC Position Evaluator — P1 Implementation Spec

This document distills the requirements discussed with the stakeholder into an implementation-ready plan for the first milestone. It is meant to be handed directly to the engineers who will own the P1 deliverable (local-only execution, later upgradeable to an HTTP API).

---

## 1. Scope & Goals

- **Input**: Open Team Sheet Pokepaste for both sides (6 Pokémon each, EVs missing), the latest battle log serialized to JSON, and the current EV estimates per Pokémon.
- **Output**:
  - Per-player win-rate estimate (0.0–1.0, UI renders as %).
  - Recommended moves for each active Pokémon (move name, target, normalized score).
- **Constraints**:
  - Runs locally; no managed services required.
  - Architecture must be ready to expose the same entry point via HTTP (FastAPI) without refactoring core logic.
  - Start with Algorithm A (heuristic + one-turn lookahead) and keep the interface extensible so Algorithm B (shallow MCTS) and Algorithm C (ML value model) can plug in.

Non-goals for P1: Online EV inference, long-horizon rollouts, production-grade Showdown automation, data collection pipelines.

---

## 2. System Overview

```
Pokepaste / Logs / EVs
        │
        ▼
 ┌─────────────────────────┐
 │ predictor.evaluate_pos. │  handle parsing, reconstruction, algo dispatch
 └─────────────────────────┘
        │
        ├─ engine.team_parser → Showdown team strings (future battle replay)
        ├─ engine.state_rebuilder → BattleState dataclass
        └─ core.eval_algorithms  → Algorithm A/B/C (select via `algorithm` flag)
```

`evaluate_position` acts as the single entry point for both the CLI/SDK call and the future `/evaluate-position` HTTP endpoint. All heavy dependencies (poke-env, FastAPI) are optional so tests can run without them.

---

## 3. Directory Layout (P1)

```
predictor/
  __init__.py                # expose evaluate_position
  api/server.py              # FastAPI adapter (optional)
  core/
    models.py                # shared dataclasses
    ev_estimator.py          # placeholder (future online learning)
    position_evaluator.py    # orchestrator
    eval_algorithms/
      heuristic_eval.py      # Algorithm A (implemented)
      mcts_eval.py           # Algorithm B stub
      ml_eval.py             # Algorithm C stub
  engine/
    team_parser.py           # Pokepaste → Showdown format + EV fill
    state_rebuilder.py       # log → BattleState
    showdown_adapter.py      # poke-env glue (skeleton)
docs/
  P1_spec.md                 # this file
```

---

## 4. Data Interfaces

### 4.1 Entry Point

```python
def evaluate_position(
    team_a_pokepaste: str,
    team_b_pokepaste: str,
    battle_log: Dict[str, Any],
    estimated_evs: Dict[str, Dict[str, Dict[str, int]]],
    algorithm: str = "heuristic",
) -> Dict[str, Any]:
    ...
```

`estimated_evs` uses `{"A": {"Flutter Mane": {...}}, "B": {...}}`. Missing spreads fall back to template defaults or a 4/252/252 placeholder.

### 4.2 Return Payload

```json
{
  "playerA": {
    "winRate": 0.46,
    "active": [
      {
        "name": "Flutter Mane",
        "suggestedMoves": [
          {"move": "Protect", "target": "self", "score": 0.41},
          {"move": "Moonblast", "target": "B_slot1", "score": 0.37}
        ]
      }
    ]
  },
  "playerB": { "... same shape ..." }
}
```

Scores are normalized per Pokémon (≈1). Consumers can directly render bars/buttons.

### 4.3 HTTP Overlay (Future)

`POST /evaluate-position` with the same payload. FastAPI wiring already exists (`predictor/api/server.py`) and only needs to be mounted via `uvicorn predictor.api.server:app`.

---

## 5. Module Responsibilities

### 5.1 `engine.team_parser`

- Split Pokepaste text into entries, parse headers/abilities/tera/moves.
- Fill EVs from `estimated_evs[player][name]`; if absent fallback to local template JSON or the hardcoded 4/252/252 spread.
- Emit canonical Showdown team strings (saved later for simulator replay).

### 5.2 `engine.state_rebuilder`

- Accept either:
  1. Rich JSON logs that contain per-turn snapshots (`state.active`, `field`, `legalActions`), or
  2. (Future) Showdown logs applied onto a poke-env battle (`StateRebuilder.showdown_adapter` hook).
- Return a `BattleState` dataclass capturing active Pokémon, HP%, boosts, status, weather/terrain/room flags, and legal actions per player.

### 5.3 `core.eval_algorithms`

- **Algorithm A — `HeuristicEvaluator` (implemented)**:
  - Feature-based board evaluation (HP delta, reserves, status, speed boosts, field control).
  - Sigmoid maps score to win rate.
  - Legal actions scored via lightweight tag heuristics (`protect`, `speed_control`, `is_super_effective`, etc.).
- **Algorithm B — `MCTSEvaluator` (stub)**:
  - Interface defined (`rollout_count`, `depth`), ready to plug into poke-env once deterministic rollouts exist.
- **Algorithm C — `MLEvaluator` (stub)**:
  - Placeholder for loading a learned value/policy network.

### 5.4 `core.position_evaluator`

- Validates teams by converting Pokepaste → Showdown format.
- Builds the `BattleState` via `StateRebuilder`.
- Dispatches to the selected evaluator and returns JSON-ready dict via `EvaluationResult.to_dict()`.

### 5.5 `api.server`

- Maps HTTP POST → `evaluate_position`.
- Strictly optional dependency (FastAPI + Pydantic).

---

## 6. Algorithm Details

### 6.1 Algorithm A — Heuristic + One-Turn View

| Component         | Description                                                                 |
| ----------------- | --------------------------------------------------------------------------- |
| Board features    | Active HP diff, reserve count diff, bad-status diff, speed boost diff, field bonus (Trick Room, weather). |
| Win-rate mapping  | `winRate = sigmoid(weighted_sum)` with tunable weights.                     |
| Action scoring    | Tag/metadata-driven additive model. Protect / speed control / super-effective hits get extra weight, switches penalized, normalized per Pokémon. |
| Complexity        | O(number of legal actions). Suitable for real-time responses.               |

### 6.2 Algorithm B — Shallow MCTS (Future)

1. Generate `(a_i, b_j)` joint actions from legal sets.
2. Roll out 50–200 stochastic simulations (poke-env) to depth 2.
3. Use Algorithm A as the leaf value.
4. Aggregate into `Q(a_i)` / `Q(b_j)` and normalize.

Requires deterministic access to the Showdown engine; the class skeleton already exposes configuration fields so plugging in the implementation later doesn’t require touching the API surface.

### 6.3 Algorithm C — ML Value Model (Future)

1. Collect labelled states from Showdown replays (win/loss outcome).
2. Train value/policy network (e.g., Tsé’s Gen8 VGC architecture).
3. Inference pipeline mirrors Algorithm A but uses `model(s')` to score next states.

---

## 7. Environment & Tooling

1. Clone Pokémon Showdown locally and start the server (refer to [心雅流ブログ](https://shingaryu.hatenablog.com/entry/2021/07/10/225407)).
2. `pip install poke-env fastapi uvicorn`.
3. Validate poke-env connectivity with its sample double battle.
4. Set default format via `ShowdownAdapterConfig.format_id`.
5. Run unit tests (to be added) with pure Python — heuristics/state parsing do not require Showdown.

---

## 8. Testing Strategy

- **Unit tests** (Pytest) for:
  - Pokepaste parsing (missing EVs, tera, blank lines).
  - Battle log reconstruction (HP normalization, legal action normalization).
  - Heuristic evaluator (win rate monotonicity, normalization of suggestions).
- **Integration smoke test**:
  - Use canned battle log JSON to call `evaluate_position`.
  - Verify deterministic output in CI.
- **Manual**:
  - Start FastAPI server locally and hit `/evaluate-position`.
  - Optional: Connect to local Showdown and ensure the adapter can authenticate (once implemented).

---

## 9. Deliverables for P1

- Python package `predictor` with callable `evaluate_position`.
- Scaffolded adapters for Showdown/poke-env and HTTP API.
- Documentation (this spec) outlining algorithms, module responsibilities, and future-proofing plan.
- Placeholder classes for Algorithms B/C to keep interfaces stable.

With these components in place we can iterate on the heuristics and plug in poke-env driven rollouts or ML models without rewriting the public API or the surrounding infrastructure.
