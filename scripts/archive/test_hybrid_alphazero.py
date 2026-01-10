"""
Test HybridStrategist with AlphaZero integration
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from predictor.player.hybrid_strategist import HybridStrategist
from predictor.core.models import BattleState, PlayerState, PokemonBattleState

print("🧪 HybridStrategist AlphaZero Integration Test")

# Check if fast model exists
fast_model_path = Path("models/fast_lane_model.pkl")
if not fast_model_path.exists():
    print(f"\n⚠️  Fast model not found, creating dummy...")
    fast_model_path.parent.mkdir(parents=True, exist_ok=True)
    import pickle
    # Create minimal dummy model
    dummy_model = {"type": "dummy"}
    with open(fast_model_path, "wb") as f:
        pickle.dump(dummy_model, f)

# Initialize HybridStrategist with AlphaZero
print("\n📥 Initializing HybridStrategist...")
hybrid = HybridStrategist(
    fast_model_path="models/fast_lane_model.pkl",
    mcts_rollouts=100,
    use_alphazero=True,
    alphazero_model_path="models/policy_value_v1.pt",
    alphazero_rollouts=50
)

# Create sample state
sample_state = BattleState(
    player_a=PlayerState(
        active=[
            PokemonBattleState(name="Calyrex-Shadow", hp_fraction=0.5),
            PokemonBattleState(name="Koraidon", hp_fraction=0.8)
        ],
        reserves=[]
    ),
    player_b=PlayerState(
        active=[
            PokemonBattleState(name="Zamazenta-Crowned", hp_fraction=0.9),
            PokemonBattleState(name="Grimmsnarl", hp_fraction=0.3)
        ],
        reserves=[]
    ),
    turn=5,
    weather="SunnyDay"
)

print("\n🎮 Testing 3-Layer Architecture:")

# Test Fast-Lane
print("\n⚡ Fast-Lane (LightGBM):")
try:
    quick_result = hybrid.predict_quick(sample_state)
    print(f"   Win rate: {quick_result.p1_win_rate:.1%}")
    print(f"   Confidence: {quick_result.confidence:.0%}")
    print(f"   Time: {quick_result.inference_time_ms:.2f}ms")
    print(f"   Source: {quick_result.source}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test Slow-Lane
print("\n🐢 Slow-Lane (Pure MCTS):")
async def test_slow():
    try:
        precise_result = await hybrid.predict_precise(sample_state)
        print(f"   Win rate: {precise_result.p1_win_rate:.1%}")
        print(f"   Confidence: {precise_result.confidence:.0%}")
        print(f"   Time: {precise_result.inference_time_ms:.1f}ms")
        print(f"   Source: {precise_result.source}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

asyncio.run(test_slow())

# Test AlphaZero-Lane
print("\n🚀 AlphaZero-Lane (NN + MCTS):")
async def test_ultimate():
    try:
        ultimate_result = await hybrid.predict_ultimate(sample_state)
        print(f"   Win rate: {ultimate_result.p1_win_rate:.1%}")
        print(f"   Confidence: {ultimate_result.confidence:.0%}")
        print(f"   Time: {ultimate_result.inference_time_ms:.1f}ms")
        print(f"   Source: {ultimate_result.source}")
        if ultimate_result.value_estimate is not None:
            print(f"   Value: {ultimate_result.value_estimate:.3f}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

asyncio.run(test_ultimate())

print("\n✅ Integration test complete!")
