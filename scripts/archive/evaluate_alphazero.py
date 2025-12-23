"""
Evaluate AlphaZero vs Pure MCTS

Compare:
1. Inference speed
2. Policy quality (entropy, top-1 confidence)
3. Value estimation accuracy
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict

import numpy as np

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from predictor.player.alphazero_strategist import PolicyValueNetwork, AlphaZeroMCTS
from predictor.player.monte_carlo_strategist import MonteCarloStrategist
from predictor.core.models import BattleState


def load_test_states(trajectories_path: Path, n_samples: int = 100) -> List[Dict]:
    """Load test states from expert trajectories"""
    with open(trajectories_path, "r") as f:
        data = json.load(f)
    
    # Sample diverse states
    sampled = []
    for i in range(0, len(data), len(data) // n_samples):
        if len(sampled) >= n_samples:
            break
        sampled.append(data[i])
    
    return sampled


def state_dict_to_battlestate(state_dict: Dict) -> BattleState:
    """Convert dict to BattleState (simplified)"""
    from predictor.core.models import PokemonBattleState
    
    p1_active = []
    for p in state_dict.get("p1_active", []):
        if p["hp_current"] > 0:  # Skip fainted
            p1_active.append(PokemonBattleState(
                species=p["species"],
                hp_current=p["hp_current"],
                hp=p["hp_max"],
                status=p.get("status")
            ))
    
    p2_active = []
    for p in state_dict.get("p2_active", []):
        if p["hp_current"] > 0:  # Skip fainted
            p2_active.append(PokemonBattleState(
                species=p["species"],
                hp_current=p["hp_current"],
                hp=p["hp_max"],
                status=p.get("status")
            ))
    
    # Only return if both sides have active Pokemon
    if not p1_active or not p2_active:
        return None
    
    return BattleState(
        p1_active=p1_active,
        p2_active=p2_active,
        weather=state_dict.get("weather"),
        terrain=state_dict.get("terrain")
    )


def evaluate_policy_quality(policy_probs: Dict[str, float]) -> Dict[str, float]:
    """Measure policy quality"""
    probs = list(policy_probs.values())
    
    if not probs:
        return {"entropy": 0.0, "top1_conf": 0.0, "top3_mass": 0.0}
    
    # Entropy (lower = more confident)
    probs_arr = np.array(probs)
    entropy = -np.sum(probs_arr * np.log(probs_arr + 1e-10))
    
    # Top-1 confidence
    top1_conf = max(probs)
    
    # Top-3 cumulative probability
    sorted_probs = sorted(probs, reverse=True)
    top3_mass = sum(sorted_probs[:3])
    
    return {
        "entropy": entropy,
        "top1_conf": top1_conf,
        "top3_mass": top3_mass
    }


def main():
    print("🧪 AlphaZero Evaluation")
    
    # Load model
    model_path = Path("models/policy_value_v1.pt")
    print(f"\n📥 Loading: {model_path}")
    
    pv_network = PolicyValueNetwork(model_path=model_path)
    
    # Load test states
    trajectories_path = Path("data/training/expert_trajectories.json")
    print(f"📂 Loading test states: {trajectories_path}")
    
    test_samples = load_test_states(trajectories_path, n_samples=50)
    print(f"   Test samples: {len(test_samples)}")
    
    # Evaluation
    results = {
        "alphazero": {
            "inference_times": [],
            "entropies": [],
            "top1_confs": [],
            "values": []
        }
    }
    
    print(f"\n🔬 Running inference...")
    for i, sample in enumerate(test_samples):
        if i % 10 == 0:
            print(f"   Progress: {i}/{len(test_samples)}")
        
        # Convert to BattleState
        try:
            battle_state = state_dict_to_battlestate(sample["state"])
            if battle_state is None:
                continue
        except Exception as e:
            continue
        
        # AlphaZero inference
        output = pv_network.predict(battle_state)
        
        results["alphazero"]["inference_times"].append(output.inference_time_ms)
        results["alphazero"]["values"].append(output.value)
        
        # Policy quality
        policy_quality = evaluate_policy_quality(output.policy_pokemon1)
        results["alphazero"]["entropies"].append(policy_quality["entropy"])
        results["alphazero"]["top1_confs"].append(policy_quality["top1_conf"])
    
    # Print results
    print(f"\n📊 Results:")
    print(f"\n🤖 AlphaZero (Policy/Value NN):")
    print(f"   Inference time: {np.mean(results['alphazero']['inference_times']):.2f}ms ± {np.std(results['alphazero']['inference_times']):.2f}ms")
    print(f"   Policy entropy: {np.mean(results['alphazero']['entropies']):.3f} ± {np.std(results['alphazero']['entropies']):.3f}")
    print(f"   Top-1 confidence: {np.mean(results['alphazero']['top1_confs']):.3f} ± {np.std(results['alphazero']['top1_confs']):.3f}")
    print(f"   Value estimate: {np.mean(results['alphazero']['values']):.3f} ± {np.std(results['alphazero']['values']):.3f}")
    
    # Compare with random baseline
    print(f"\n📈 Analysis:")
    
    avg_entropy = np.mean(results['alphazero']['entropies'])
    uniform_entropy = np.log(32)  # 32 actions
    
    print(f"   Entropy reduction: {(1 - avg_entropy/uniform_entropy)*100:.1f}% vs uniform")
    print(f"   Avg top-1 conf: {np.mean(results['alphazero']['top1_confs'])*100:.1f}% (random: 3.1%)")
    
    if np.mean(results['alphazero']['top1_confs']) > 0.1:
        print(f"   ✅ Model shows strong policy preferences")
    else:
        print(f"   ⚠️  Model close to random policy")
    
    # Save results
    output_path = Path("data/evaluation/alphazero_eval.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump({
            "model": str(model_path),
            "n_samples": len(test_samples),
            "alphazero": {
                "inference_time_ms": {
                    "mean": float(np.mean(results['alphazero']['inference_times'])),
                    "std": float(np.std(results['alphazero']['inference_times']))
                },
                "policy_entropy": {
                    "mean": float(np.mean(results['alphazero']['entropies'])),
                    "std": float(np.std(results['alphazero']['entropies']))
                },
                "top1_confidence": {
                    "mean": float(np.mean(results['alphazero']['top1_confs'])),
                    "std": float(np.std(results['alphazero']['top1_confs']))
                }
            }
        }, f, indent=2)
    
    print(f"\n💾 Saved: {output_path}")
    print(f"\n✅ Evaluation complete!")


if __name__ == "__main__":
    main()
