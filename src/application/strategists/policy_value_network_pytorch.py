"""
PyTorch Policy/Value Network for VGC AlphaZero

Architecture:
- Input: 512-dim battle state features
- Hidden: 2 layers (256, 128) + Dropout
- Output: 3 heads
  * Policy1: Pokemon1 action probabilities (softmax)
  * Policy2: Pokemon2 action probabilities (softmax)
  * Value: Position evaluation (tanh, -1~1)
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class BattleStateEncoder:
    """BattleState -> 512-dim feature vector"""
    
    FEATURE_DIM = 512
    
    @staticmethod
    def encode(battle_state) -> np.ndarray:
        """
        盤面を512次元ベクトルに変換
        
        Feature breakdown:
        - P1 active Pokemon (2x100 = 200): HP, stats, moves, status
        - P2 active Pokemon (2x100 = 200): HP, stats, moves, status
        - Field conditions (50): weather, terrain, tricks
        - Turn info (12): turn number, terastallize used
        - Reserve Pokemon (50): team composition
        """
        features = np.zeros(BattleStateEncoder.FEATURE_DIM, dtype=np.float32)
        idx = 0
        
        # P1 active (200 dims)
        idx = BattleStateEncoder._encode_active_pokemon(
            battle_state, "p1", features, idx
        )
        
        # P2 active (200 dims)
        idx = BattleStateEncoder._encode_active_pokemon(
            battle_state, "p2", features, idx
        )
        
        # Field (50 dims)
        idx = BattleStateEncoder._encode_field(
            battle_state, features, idx
        )
        
        # Turn info (12 dims)
        idx = BattleStateEncoder._encode_turn_info(
            battle_state, features, idx
        )
        
        # Padding to 512
        return features
    
    @staticmethod
    def _encode_active_pokemon(
        battle_state,
        player: str,
        features: np.ndarray,
        start_idx: int
    ) -> int:
        """Active Pokemon encoding (100 dims per Pokemon)"""
        active = getattr(battle_state, f"{player}_active", [])
        
        for i in range(2):
            base_idx = start_idx + i * 100
            
            if i < len(active):
                pokemon = active[i]
                
                # HP (1 dim)
                features[base_idx] = pokemon.hp_current / 100.0
                
                # Stats normalized (6 dims)
                stats = [
                    getattr(pokemon, stat, 100) / 200.0
                    for stat in ["hp", "attack", "defense", "sp_attack", "sp_defense", "speed"]
                ]
                features[base_idx+1:base_idx+7] = stats
                
                # Status (7 dims: normal, burn, paralysis, sleep, freeze, poison, toxic)
                status_idx = {
                    None: 0, "brn": 1, "par": 2, "slp": 3,
                    "frz": 4, "psn": 5, "tox": 6
                }.get(getattr(pokemon, "status", None), 0)
                features[base_idx+7+status_idx] = 1.0
                
                # Type (18 dims: one-hot)
                type1_idx = BattleStateEncoder._type_to_idx(
                    getattr(pokemon, "type1", "Normal")
                )
                features[base_idx+14+type1_idx] = 1.0
                
                # Terastallized (1 dim)
                features[base_idx+32] = float(
                    getattr(pokemon, "terastallized", False)
                )
                
                # Moves available (4 dims: binary flags)
                moves = getattr(pokemon, "moves", [])
                for move_idx in range(min(4, len(moves))):
                    features[base_idx+33+move_idx] = 1.0
        
        return start_idx + 200
    
    @staticmethod
    def _encode_field(
        battle_state,
        features: np.ndarray,
        start_idx: int
    ) -> int:
        """Field conditions (50 dims)"""
        # Weather (5 dims)
        weather_idx = {
            None: 0, "SunnyDay": 1, "RainDance": 2,
            "Sandstorm": 3, "Snow": 4
        }.get(getattr(battle_state, "weather", None), 0)
        features[start_idx+weather_idx] = 1.0
        
        # Terrain (5 dims)
        terrain_idx = {
            None: 0, "Electric": 1, "Grassy": 2,
            "Misty": 3, "Psychic": 4
        }.get(getattr(battle_state, "terrain", None), 0)
        features[start_idx+5+terrain_idx] = 1.0
        
        return start_idx + 50
    
    @staticmethod
    def _encode_turn_info(
        battle_state,
        features: np.ndarray,
        start_idx: int
    ) -> int:
        """Turn info (12 dims)"""
        # Turn number normalized (1 dim)
        turn = getattr(battle_state, "turn", 1)
        features[start_idx] = min(turn / 20.0, 1.0)
        
        return start_idx + 12
    
    @staticmethod
    def _type_to_idx(type_name: str) -> int:
        """Pokemon type to index (0-17)"""
        types = [
            "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
            "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
            "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"
        ]
        return types.index(type_name) if type_name in types else 0


class PolicyValueNet(nn.Module):
    """PyTorch Policy/Value Network"""
    
    def __init__(
        self,
        input_dim: int = 512,
        hidden_dims: List[int] = [256, 128],
        policy_dim: int = 32,
        dropout_rate: float = 0.3
    ):
        super().__init__()
        
        # Shared layers
        layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout_rate)
            ])
            prev_dim = hidden_dim
        
        self.shared = nn.Sequential(*layers)
        
        # Policy heads (Factored Action Space)
        self.policy1_head = nn.Linear(prev_dim, policy_dim)
        self.policy2_head = nn.Linear(prev_dim, policy_dim)
        
        # Value head
        self.value_head = nn.Sequential(
            nn.Linear(prev_dim, 1),
            nn.Tanh()
        )
    
    def forward(
        self,
        x: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Args:
            x: [batch_size, 512] battle state features
            
        Returns:
            policy1: [batch_size, 32] Pokemon1 action logits
            policy2: [batch_size, 32] Pokemon2 action logits
            value: [batch_size, 1] position evaluation
        """
        shared = self.shared(x)
        
        policy1 = self.policy1_head(shared)
        policy2 = self.policy2_head(shared)
        value = self.value_head(shared)
        
        return policy1, policy2, value


class ExpertTrajectoryDataset(Dataset):
    """Training dataset from expert replays"""
    
    def __init__(self, trajectories_path: Path):
        with open(trajectories_path, "r") as f:
            self.data = json.load(f)
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        example = self.data[idx]
        
        # State -> features
        state_features = self._encode_state_from_dict(example["state"])
        
        # Action -> labels
        p1_action_label, p2_action_label = self._encode_actions(
            example["action"]
        )
        
        # Outcome -> value
        value_label = float(example["outcome"])
        
        return (
            torch.tensor(state_features, dtype=torch.float32),
            torch.tensor(p1_action_label, dtype=torch.long),
            torch.tensor(p2_action_label, dtype=torch.long),
            torch.tensor(value_label, dtype=torch.float32)
        )
    
    def _encode_state_from_dict(self, state_dict: Dict) -> np.ndarray:
        """Simplified state encoding from dict"""
        features = np.zeros(512, dtype=np.float32)
        
        # P1 active
        for i, pokemon in enumerate(state_dict.get("p1_active", [])[:2]):
            base_idx = i * 100
            features[base_idx] = pokemon["hp_current"] / 100.0
            if pokemon.get("status"):
                features[base_idx+7] = 1.0
            if pokemon.get("terastallized"):
                features[base_idx+32] = 1.0
        
        # P2 active
        for i, pokemon in enumerate(state_dict.get("p2_active", [])[:2]):
            base_idx = 200 + i * 100
            features[base_idx] = pokemon["hp_current"] / 100.0
            if pokemon.get("status"):
                features[base_idx+7] = 1.0
            if pokemon.get("terastallized"):
                features[base_idx+32] = 1.0
        
        # Weather
        if state_dict.get("weather"):
            features[400] = 1.0
        
        return features
    
    def _encode_actions(
        self,
        action_dict: Dict
    ) -> Tuple[int, int]:
        """Action to label (simplified: move index)"""
        p1_actions = action_dict.get("p1_actions", [])
        p2_actions = action_dict.get("p2_actions", [])
        
        # Use first action for each player
        p1_label = 0
        p2_label = 0
        
        if p1_actions and "move" in p1_actions[0]:
            p1_label = hash(p1_actions[0]["move"]) % 32
        
        if p2_actions and "move" in p2_actions[0]:
            p2_label = hash(p2_actions[0]["move"]) % 32
        
        return p1_label, p2_label


class PolicyValueTrainer:
    """Behavioral Cloning trainer"""
    
    def __init__(
        self,
        model: PolicyValueNet,
        device: str = "mps",
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-4
    ):
        self.model = model.to(device)
        self.device = device
        
        self.optimizer = torch.optim.Adam(
            model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay
        )
        
        self.policy_loss_fn = nn.CrossEntropyLoss()
        self.value_loss_fn = nn.MSELoss()
    
    def train_epoch(
        self,
        dataloader: DataLoader,
        epoch: int
    ) -> Dict[str, float]:
        """Train one epoch"""
        self.model.train()
        
        total_loss = 0.0
        total_policy1_acc = 0.0
        total_policy2_acc = 0.0
        n_batches = 0
        
        for batch in dataloader:
            states, p1_labels, p2_labels, value_labels = [
                x.to(self.device) for x in batch
            ]
            
            # Forward
            policy1_logits, policy2_logits, value_pred = self.model(states)
            
            # Loss
            policy1_loss = self.policy_loss_fn(policy1_logits, p1_labels)
            policy2_loss = self.policy_loss_fn(policy2_logits, p2_labels)
            value_loss = self.value_loss_fn(
                value_pred.squeeze(), value_labels
            )
            
            loss = policy1_loss + policy2_loss + value_loss
            
            # Backward
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()
            
            # Metrics
            total_loss += loss.item()
            total_policy1_acc += (
                policy1_logits.argmax(1) == p1_labels
            ).float().mean().item()
            total_policy2_acc += (
                policy2_logits.argmax(1) == p2_labels
            ).float().mean().item()
            n_batches += 1
        
        return {
            "loss": total_loss / n_batches,
            "policy1_acc": total_policy1_acc / n_batches,
            "policy2_acc": total_policy2_acc / n_batches
        }
    
    def validate(self, dataloader: DataLoader) -> Dict[str, float]:
        """Validation"""
        self.model.eval()
        
        total_loss = 0.0
        total_policy1_acc = 0.0
        n_batches = 0
        
        with torch.no_grad():
            for batch in dataloader:
                states, p1_labels, p2_labels, value_labels = [
                    x.to(self.device) for x in batch
                ]
                
                policy1_logits, policy2_logits, value_pred = self.model(states)
                
                policy1_loss = self.policy_loss_fn(policy1_logits, p1_labels)
                policy2_loss = self.policy_loss_fn(policy2_logits, p2_labels)
                value_loss = self.value_loss_fn(
                    value_pred.squeeze(), value_labels
                )
                
                loss = policy1_loss + policy2_loss + value_loss
                
                total_loss += loss.item()
                total_policy1_acc += (
                    policy1_logits.argmax(1) == p1_labels
                ).float().mean().item()
                n_batches += 1
        
        return {
            "val_loss": total_loss / n_batches,
            "val_policy1_acc": total_policy1_acc / n_batches
        }
    
    def save_checkpoint(self, path: Path):
        """Save model"""
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict()
        }, path)
        print(f"💾 Saved: {path}")
    
    def load_checkpoint(self, path: Path):
        """Load model"""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        print(f"📥 Loaded: {path}")


def train_behavioral_cloning(
    trajectories_path: Path,
    output_model_path: Path,
    epochs: int = 50,
    batch_size: int = 32,
    val_split: float = 0.2
):
    """BC training main function"""
    print(f"🎓 Behavioral Cloning Training")
    print(f"   Data: {trajectories_path}")
    print(f"   Output: {output_model_path}")
    
    # Dataset
    dataset = ExpertTrajectoryDataset(trajectories_path)
    print(f"   Total examples: {len(dataset)}")
    
    # Train/val split
    val_size = int(len(dataset) * val_split)
    train_size = len(dataset) - val_size
    train_dataset, val_dataset = torch.utils.data.random_split(
        dataset, [train_size, val_size]
    )
    
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True
    )
    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False
    )
    
    # Model
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"   Device: {device}")
    
    model = PolicyValueNet()
    trainer = PolicyValueTrainer(model, device=device)
    
    # Training loop
    best_val_loss = float("inf")
    patience = 3
    patience_counter = 0
    
    for epoch in range(1, epochs + 1):
        train_metrics = trainer.train_epoch(train_loader, epoch)
        val_metrics = trainer.validate(val_loader)
        
        print(
            f"   Epoch {epoch}/{epochs} | "
            f"Loss: {train_metrics['loss']:.4f} | "
            f"Policy1 Acc: {train_metrics['policy1_acc']:.3f} | "
            f"Val Loss: {val_metrics['val_loss']:.4f}"
        )
        
        # Early stopping
        if val_metrics["val_loss"] < best_val_loss:
            best_val_loss = val_metrics["val_loss"]
            patience_counter = 0
            trainer.save_checkpoint(output_model_path)
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"   Early stopping at epoch {epoch}")
                break
    
    print(f"✅ Training complete!")
    return model


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/training/expert_trajectories.json")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("models/policy_value_v1.pt")
    )
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=32)
    
    args = parser.parse_args()
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    train_behavioral_cloning(
        args.data,
        args.output,
        epochs=args.epochs,
        batch_size=args.batch_size
    )
