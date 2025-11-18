from predictor.core.models import ActionCandidate, BattleState, PlayerState, PokemonBattleState
from predictor.data.showdown_loader import ShowdownDataRepository
from predictor.engine.move_metadata import apply_move_metadata


def _build_state(actions):
    dummy_player = PlayerState(name="Player", active=[PokemonBattleState(name="Flutter Mane")])
    return BattleState(
        player_a=dummy_player,
        player_b=dummy_player,
        turn=1,
        legal_actions={"A": actions},
        raw_log={},
    )


def test_apply_move_metadata_sets_fallback_target_and_metadata():
    repo = ShowdownDataRepository()
    action = ActionCandidate(actor="Flutter Mane", slot=0, move="Protect")
    state = _build_state([action])

    apply_move_metadata(state, repo)

    assert action.target == "self"
    assert action.metadata["showdownTarget"] == "self"
    assert action.metadata["category"] == "Status"
    assert action.metadata["shortDesc"]


def test_apply_move_metadata_handles_spread_moves_and_priority():
    repo = ShowdownDataRepository()
    action = ActionCandidate(actor="Flutter Mane", slot=0, move="Rock Slide")
    quick_action = ActionCandidate(actor="Arcanine", slot=0, move="Extreme Speed")
    state = _build_state([action, quick_action])

    apply_move_metadata(state, repo)

    assert action.target == "spread"
    assert action.metadata["basePower"] > 0
    assert quick_action.priority >= 2
