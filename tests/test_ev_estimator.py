import json
from pathlib import Path

from predictor.core.ev_estimator import EVEstimator
from predictor.engine.damage_calculator import DamageCalculator


def load_sample_log():
    data_path = Path(__file__).parent / "data" / "sample_battle_log.json"
    return json.loads(data_path.read_text(encoding="utf-8"))


def test_speed_observation_updates_distribution(tmp_path):
    estimator = EVEstimator(Path("data/ev_priors.json"))
    team = [{"name": "Flutter Mane", "species": "Flutter Mane", "nature": "Timid", "evs": {}, "ivs": {}}]
    estimator.initialize_player("A", team, overrides=None)

    before = estimator.player_distributions["A"]["Flutter Mane"].best_guess().label
    assert before in {"timid_focus_sash", "bulky_speed"}

    estimator._apply_speed_observations(
        [
            {"player": "A", "pokemon": "Flutter Mane", "constraint": "min", "value": 200},
        ]
    )
    after = estimator.player_distributions["A"]["Flutter Mane"].best_guess().label
    assert after == "timid_focus_sash"


def test_damage_observation_prefers_bulky_option():
    estimator = EVEstimator(Path("data/ev_priors.json"))
    damage_calc = DamageCalculator()
    team_a = [{"name": "Flutter Mane", "species": "Flutter Mane", "nature": "Timid", "evs": {}, "ivs": {}}]
    team_b = [{"name": "Amoonguss", "species": "Amoonguss", "nature": "Relaxed", "evs": {}, "ivs": {}}]
    estimator.initialize_player("A", team_a, overrides=None)
    estimator.initialize_player("B", team_b, overrides=None)

    battle_log = load_sample_log()
    estimator._apply_damage_observations(
        [
            {
                "attacker": {"player": "A", "pokemon": "Flutter Mane"},
                "defender": {"player": "B", "pokemon": "Amoonguss"},
                "move": "Moonblast",
                "percent": 60,
            }
        ],
        battle_log,
        damage_calc,
    )

    guess = estimator.player_distributions["B"]["Amoonguss"].best_guess().label
    assert guess in {"trick_room", "spd_focus"}
