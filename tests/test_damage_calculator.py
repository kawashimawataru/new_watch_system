from predictor.core.ev_estimator import SpreadHypothesis
from predictor.engine.damage_calculator import DamageCalculator


def test_damage_calculator_returns_reasonable_range():
    calc = DamageCalculator()
    attacker = SpreadHypothesis(
        label="att",
        nature="Timid",
        evs={"spa": 252, "spe": 252},
        ivs={},
        probability=1.0,
        species="Flutter Mane",
    )
    defender = SpreadHypothesis(
        label="def",
        nature="Relaxed",
        evs={"hp": 236, "def": 156},
        ivs={},
        probability=1.0,
        species="Amoonguss",
    )
    window = calc.estimate_percent(
        "Flutter Mane",
        attacker,
        "Amoonguss",
        defender,
        "Moonblast",
        {"weather": None},
        attacker_item="focus sash",
        defender_item="sitrus berry",
    )
    assert window is not None
    assert 10 < window.min_percent < 90
    assert window.max_percent >= window.min_percent
