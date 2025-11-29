"""Test trained AlphaZero model"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from predictor.player.alphazero_strategist import PolicyValueNetwork, AlphaZeroStrategist
from predictor.core.models import BattleState, PokemonBattleState

# Load model
model_path = Path("models/policy_value_v1.pt")
print(f"🧪 Testing AlphaZero Model")
print(f"   Model: {model_path}")

pv_network = PolicyValueNetwork(
    model_path=model_path,
    use_bc_pretraining=True
)

# Create sample state
sample_state = BattleState(
    p1_active=[
        PokemonBattleState(
            species="Calyrex-Shadow",
            hp_current=1,
            hp=100,
            attack=150,
            defense=100,
            sp_attack=200,
            sp_defense=100,
            speed=150
        ),
        PokemonBattleState(
            species="Koraidon",
            hp_current=99,
            hp=100,
            attack=135,
            defense=115,
            sp_attack=85,
            sp_defense=100,
            speed=135
        )
    ],
    p2_active=[
        PokemonBattleState(
            species="Zamazenta-Crowned",
            hp_current=100,
            hp=100,
            attack=130,
            defense=145,
            sp_attack=80,
            sp_defense=145,
            speed=128
        ),
        PokemonBattleState(
            species="Grimmsnarl",
            hp_current=1,
            hp=100,
            attack=120,
            defense=65,
            sp_attack=95,
            sp_defense=75,
            speed=60
        )
    ],
    weather="SunnyDay",
    turn=6
)

# Predict
print(f"\n🔮 Prediction:")
result = pv_network.predict(sample_state)

print(f"   Value: {result.value:.3f} (P1 perspective)")
print(f"   Inference: {result.inference_time_ms:.2f}ms")
print(f"   Policy1 top 3:")
top_actions_p1 = sorted(
    result.policy_pokemon1.items(),
    key=lambda x: x[1],
    reverse=True
)[:3]
for action, prob in top_actions_p1:
    print(f"      {action}: {prob:.3f}")

print(f"   Policy2 top 3:")
top_actions_p2 = sorted(
    result.policy_pokemon2.items(),
    key=lambda x: x[1],
    reverse=True
)[:3]
for action, prob in top_actions_p2:
    print(f"      {action}: {prob:.3f}")

# Test AlphaZeroStrategist integration
print(f"\n🎮 AlphaZero Strategist:")
strategist = AlphaZeroStrategist(
    policy_value_model_path=model_path,
    mcts_rollouts=50,
    fallback_to_pure_mcts=False
)

prediction = strategist.predict(sample_state)
print(f"   P1 win rate: {prediction['p1_win_rate']:.1%}")
print(f"   Inference: {prediction['inference_time_ms']:.1f}ms")
print(f"   Value estimate: {prediction['value_estimate']:.3f}")

print(f"\n✅ Test complete!")
