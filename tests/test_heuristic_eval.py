import json
from pathlib import Path

from predictor.core.eval_algorithms.heuristic_eval import HeuristicEvaluator
from predictor.engine.state_rebuilder import StateRebuilder


def load_state():
    data_path = Path(__file__).parent / "data" / "sample_battle_log.json"
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    return StateRebuilder().rebuild(payload)


def test_heuristic_evaluator_returns_probabilities_and_moves():
    evaluator = HeuristicEvaluator()
    state = load_state()
    result = evaluator.evaluate(state).to_dict()

    assert 0.0 < result["playerA"]["winRate"] < 1.0
    assert 0.0 < result["playerB"]["winRate"] < 1.0
    assert abs(result["playerA"]["winRate"] + result["playerB"]["winRate"] - 1.0) < 1e-6

    for player in ("playerA", "playerB"):
        for pokemon in result[player]["active"]:
            scores = [move["score"] for move in pokemon["suggestedMoves"]]
            assert scores, f"{pokemon['name']} should have at least one suggestion"
            assert abs(sum(scores) - 1.0) < 1e-6
