import sys
from unittest.mock import MagicMock, patch

# Mock poke-env modules BEFORE importing frontend.battle_ai_player
mock_poke_env = MagicMock()
sys.modules["poke_env"] = mock_poke_env
sys.modules["poke_env.player"] = MagicMock()
sys.modules["poke_env.environment"] = MagicMock()
sys.modules["poke_env.environment.battle"] = MagicMock()
sys.modules["poke_env.environment.move"] = MagicMock()
sys.modules["poke_env.environment.pokemon"] = MagicMock()
sys.modules["poke_env.server_configuration"] = MagicMock()
sys.modules["poke_env.environment.side_condition"] = MagicMock()

# Define Player class in the mock module so AIPlayer can inherit from it
class MockPlayer:
    def __init__(self, **kwargs):
        self.username = "AIPlayer"
    def create_order(self, order):
        return order
    def choose_random_move(self, battle):
        return "random_move"

sys.modules["poke_env.player"].Player = MockPlayer

import pytest
from predictor.player.hybrid_strategist import HybridStrategist, HybridPrediction
from predictor.core.models import BattleState, PlayerState, ActionCandidate
# Now import AIPlayer
from frontend.battle_ai_player import AIPlayer

# Mock classes for poke-env objects used in tests
class MockMove:
    def __init__(self, id):
        self.id = id
        self.entry_name = id
        self.base_power = 90
        self.current_pp = 10
        self.max_pp = 10

class MockPokemon:
    def __init__(self, species):
        self.species = species
        self.current_hp = 100
        self.max_hp = 100
        self.current_hp_fraction = 1.0
        self.status = None
        self.moves = {"tackle": MockMove("tackle")}
        self.item = None
        self.ability = None
        self.active = True
        self.current_hp_fraction = 1.0

class MockBattle:
    def __init__(self):
        self.turn = 1
        self.active_pokemon = MockPokemon("Pikachu")
        self.opponent_active_pokemon = MockPokemon("Charizard")
        self.available_moves = [MockMove("thunderbolt"), MockMove("quickattack")]
        self.available_switches = [MockPokemon("Bulbasaur")]
        self.opponent_username = "Opponent"
        self.opponent_team = {"Charizard": self.opponent_active_pokemon}
        self.battle_tag = "battle-1"
        self.won = False

@pytest.fixture
def hybrid_strategist():
    # Mock MonteCarloStrategist and FastStrategist
    with patch("predictor.player.hybrid_strategist.MonteCarloStrategist") as MockMCTS, \
         patch("predictor.player.hybrid_strategist.FastStrategist") as MockFast:
        
        # Mock MCTS
        mock_mcts_instance = MockMCTS.return_value
        mock_mcts_instance.predict_win_rate.return_value = {
            "player_a_win_rate": 0.6,
            "optimal_action": MagicMock(player_a_actions=[MagicMock(type="move", move_name="thunderbolt", pokemon_slot=0, target_slot=2)]),
            "action_win_rates": {0: 0.6, 1: 0.4},
            "legal_actions": [
                MagicMock(player_a_actions=[MagicMock(type="move", move_name="thunderbolt", pokemon_slot=0, target_slot=2)]),
                MagicMock(player_a_actions=[MagicMock(type="move", move_name="quickattack", pokemon_slot=0, target_slot=2)])
            ]
        }
        
        # Mock FastStrategist
        MockFast.load.return_value = MagicMock()
        
        strategist = HybridStrategist("dummy_path", mcts_rollouts=10)
        return strategist

def test_hybrid_strategist_explanation(hybrid_strategist):
    battle_state = MagicMock(spec=BattleState)
    battle_state.legal_actions = {"A": []}
    
    # Test predict_both (synchronous)
    _, slow_result = hybrid_strategist.predict_both(battle_state)
    
    assert slow_result.source == "slow"
    assert slow_result.p1_win_rate == 0.6
    assert "Win rate: 60.0%" in slow_result.explanation
    assert len(slow_result.alternatives) == 2
    assert slow_result.alternatives[0]["win_rate"] == 0.6
    assert "thunderbolt" in slow_result.alternatives[0]["description"]

def test_ai_player_choose_move():
    # Mock HybridStrategist inside AIPlayer and FastStrategist (called in __init__)
    with patch("frontend.battle_ai_player.HybridStrategist") as MockHybrid:
        mock_instance = MockHybrid.return_value
        mock_instance.predict_both.return_value = (
            MagicMock(), # fast
            HybridPrediction(
                p1_win_rate=0.7,
                recommended_action=MagicMock(player_a_actions=[MagicMock(type="move", move_name="thunderbolt")]),
                confidence=0.9,
                inference_time_ms=10,
                source="slow",
                explanation="Test Explanation",
                alternatives=[{"description": "Alt 1", "win_rate": 0.5}]
            ) # slow
        )
        
        player = AIPlayer(start_listening=False)
        battle = MockBattle()
        
        # Run choose_move
        order = player.choose_move(battle)
        
        # Verify order
        assert order is not None
        # Verify log output (implicitly, by checking if it ran without error)
