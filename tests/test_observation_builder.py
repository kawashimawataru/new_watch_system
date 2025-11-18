import json
from pathlib import Path

from predictor.engine.observation_builder import build_observations


def load_log():
    data_path = Path(__file__).parent / "data" / "sample_battle_log.json"
    return json.loads(data_path.read_text(encoding="utf-8"))


def test_build_observations_populates_speed_and_damage():
    log = load_log()
    log.pop("observations", None)
    obs = build_observations(log)

    assert obs["speed"], "speed observations should be generated"
    assert obs["damage"], "damage observations should be generated"

    # ensure both min and max constraints exist
    constraints = {entry["constraint"] for entry in obs["speed"]}
    assert "min" in constraints
    assert "max" in constraints

    dmg_entry = obs["damage"][0]
    assert "attacker" in dmg_entry and "defender" in dmg_entry
    assert dmg_entry["percent"] > 0
