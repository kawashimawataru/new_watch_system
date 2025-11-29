"""
Self-Play Data Generation for AlphaZero

Generate additional training data by having the model play against itself.
This improves policy diversity beyond the N=3545 expert samples.
"""

import json
import random
import sys
from pathlib import Path
from typing import List, Dict, Tuple

import numpy as np

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from predictor.player.alphazero_strategist import PolicyValueNetwork, AlphaZeroMCTS
from predictor.core.models import BattleState, PokemonBattleState


class SelfPlayGenerator:
    """Generate training data through self-play"""
    
    def __init__(self, model_path: Path):
        self.pv_network = PolicyValueNetwork(model_path=model_path)
        self.mcts = AlphaZeroMCTS(
            policy_value_network=self.pv_network,
            n_rollouts=50,
            c_puct=1.0
        )
    
    def generate_random_state(self) -> BattleState:
        """Generate random battle state for self-play"""
        common_pokemon = [
            "Calyrex-Shadow", "Koraidon", "Miraidon", "Groudon", "Kyogre",
            "Rillaboom", "Incineroar", "Amoonguss", "Grimmsnarl", "Tornadus",
            "Urshifu", "Zamazenta-Crowned", "Flutter Mane", "Iron Hands"
        ]
        
        # Random teams
        p1_species = random.sample(common_pokemon, 2)
        p2_species = random.sample(common_pokemon, 2)
        
        # Random HP
        p1_active = [
            PokemonBattleState(
                name=species,
                hp_fraction=random.uniform(0.3, 1.0)
            )
            for species in p1_species
        ]
        
        p2_active = [
            PokemonBattleState(
                name=species,
                hp_fraction=random.uniform(0.3, 1.0)
            )
            for species in p2_species
        ]
        
        # Random field
        weathers = [None, "SunnyDay", "RainDance", "Sandstorm", "Snow"]
        terrains = [None, "Electric", "Grassy", "Misty", "Psychic"]
        
        return BattleState(
            p1_active=p1_active,
            p2_active=p2_active,
            weather=random.choice(weathers),
            terrain=random.choice(terrains),
            turn=random.randint(1, 10)
        )
    
    def play_one_turn(self, state: BattleState) -> Tuple[Dict, Dict, float]:
        """
        Play one turn of self-play
        
        Returns:
            state_dict, action_dict, value_estimate
        """
        # Get policy/value prediction
        output = self.pv_network.predict(state)
        
        # Sample actions from policy
        p1_actions = self._sample_action(output.policy_pokemon1)
        p2_actions = self._sample_action(output.policy_pokemon2)
        
        # Convert to training format
        state_dict = {
            "p1_active": [
                {
                    "species": p.name,
                    "hp_current": int(p.hp_fraction * 100),
                    "hp_max": 100,
                    "status": p.status,
                    "terastallized": False,
                    "tera_type": None
                }
                for p in state.p1_active
            ],
            "p2_active": [
                {
                    "species": p.name,
                    "hp_current": int(p.hp_fraction * 100),
                    "hp_max": 100,
                    "status": p.status,
                    "terastallized": False,
                    "tera_type": None
                }
                for p in state.p2_active
            ],
            "weather": state.weather,
            "terrain": state.terrain
        }
        
        action_dict = {
            "p1_actions": [{"type": "move", "move": p1_actions, "slot": "p1a"}],
            "p2_actions": [{"type": "move", "move": p2_actions, "slot": "p2a"}]
        }
        
        return state_dict, action_dict, output.value
    
    def _sample_action(self, policy_probs: Dict[str, float]) -> str:
        """Sample action from policy distribution"""
        if not policy_probs:
            return "tackle"
        
        actions = list(policy_probs.keys())
        probs = list(policy_probs.values())
        
        # Normalize
        total = sum(probs)
        if total > 0:
            probs = [p / total for p in probs]
        else:
            probs = [1.0 / len(probs)] * len(probs)
        
        return np.random.choice(actions, p=probs)
    
    def generate_games(self, n_games: int = 100) -> List[Dict]:
        """Generate n self-play games"""
        trajectories = []
        
        for game_idx in range(n_games):
            if game_idx % 10 == 0:
                print(f"   Game {game_idx}/{n_games}")
            
            # Generate random starting state
            state = self.generate_random_state()
            
            # Play one turn (simplified)
            state_dict, action_dict, value = self.play_one_turn(state)
            
            # Random outcome (weighted by value estimate)
            outcome = 1 if value > 0 else -1
            
            trajectory = {
                "replay_id": f"selfplay_{game_idx}",
                "turn": state.turn,
                "state": state_dict,
                "action": action_dict,
                "outcome": outcome
            }
            
            trajectories.append(trajectory)
        
        return trajectories


def main():
    print("🎮 Self-Play Data Generation")
    
    model_path = Path("models/policy_value_v1.pt")
    output_path = Path("data/training/selfplay_trajectories.json")
    
    print(f"   Model: {model_path}")
    print(f"   Output: {output_path}")
    
    # Generate self-play data
    generator = SelfPlayGenerator(model_path)
    
    print(f"\n🔄 Generating self-play games...")
    trajectories = generator.generate_games(n_games=500)
    
    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(trajectories, f, indent=2)
    
    print(f"\n✅ Generated {len(trajectories)} self-play trajectories")
    print(f"💾 Saved: {output_path}")
    
    # Merge with expert data
    expert_path = Path("data/training/expert_trajectories.json")
    merged_path = Path("data/training/combined_trajectories.json")
    
    if expert_path.exists():
        with open(expert_path, "r") as f:
            expert_data = json.load(f)
        
        combined = expert_data + trajectories
        
        with open(merged_path, "w") as f:
            json.dump(combined, f, indent=2)
        
        print(f"📦 Combined: {len(expert_data)} expert + {len(trajectories)} self-play = {len(combined)} total")
        print(f"💾 Saved: {merged_path}")


if __name__ == "__main__":
    main()
