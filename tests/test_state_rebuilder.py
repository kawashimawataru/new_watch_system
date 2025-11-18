import json
from pathlib import Path

from predictor.engine.state_rebuilder import StateRebuilder


def load_battle_log() -> dict:
    path = Path(__file__).parent / "data" / "sample_battle_log.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_state_rebuilder_from_log_extracts_core_fields():
    builder = StateRebuilder(team_metadata={})
    battle_state = builder.rebuild(load_battle_log(), {"A": {}, "B": {}})

    assert battle_state.player_a.name == "Player A"
    assert battle_state.turn == 5
    assert battle_state.weather == "rain"
    assert len(battle_state.player_a.active) == 2
    assert len(battle_state.player_b.active) == 2

    flutter = battle_state.player_a.active[0]
    assert flutter.name == "Flutter Mane"
    assert 0.7 < flutter.hp_fraction < 0.8
    assert flutter.boosts["spe"] == 1

    legal_a = battle_state.legal_actions["A"]
    assert any(action.move == "Moonblast" for action in legal_a)
    assert any(action.tags and "protect" in action.tags for action in legal_a)
