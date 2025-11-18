import json
from pathlib import Path

from predictor.core.position_evaluator import evaluate_position


def read_text(name: str) -> str:
    return (Path(__file__).parent / "data" / name).read_text(encoding="utf-8")


def read_json(name: str) -> dict:
    return json.loads(read_text(name))


def test_evaluate_position_returns_expected_schema():
    team_a = read_text("team_a.paste")
    team_b = read_text("team_b.paste")
    battle_log = read_json("sample_battle_log.json")
    estimated_evs = {
        "A": {
            "Flutter Mane": {"hp": 0, "def": 4, "spa": 252, "spe": 252},
            "Arcanine": {"hp": 252, "atk": 252, "spe": 4},
        },
        "B": {
            "Iron Bundle": {"hp": 0, "spa": 252, "spe": 252, "def": 4},
            "Amoonguss": {"hp": 252, "def": 124, "spd": 132},
        },
    }

    result = evaluate_position(
        team_a,
        team_b,
        battle_log,
        estimated_evs,
        algorithm="heuristic",
    )

    for player in ("playerA", "playerB"):
        assert "winRate" in result[player]
        assert 0.0 <= result[player]["winRate"] <= 1.0
        assert len(result[player]["active"]) == 2
        for pokemon in result[player]["active"]:
            assert "name" in pokemon
            assert "suggestedMoves" in pokemon
            assert pokemon["suggestedMoves"], "Each active Pokémon needs suggestions."
