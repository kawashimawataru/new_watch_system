"""
AlphaZero-Style Strategist: Neural Network + MCTS Hybrid

AlphaZeroの戦略を採用した、VGC（ダブルバトル）用の高度な意思決定エンジン。

アーキテクチャ:
1. Policy Network: 各ポケモンの行動確率を予測 (Factored Action Space)
2. Value Network: 現在の盤面の勝率を予測
3. MCTS: Policy/Valueで誘導された効率的な探索

データ効率化:
- Behavioral Cloning (BC): 少数(N=500)の上位プレイヤーログで初期学習
- Regularization: Dropout + Weight Decay で過学習を防止
- Self-Play: 学習済みモデル同士で対戦してデータ拡張

Usage:
    strategist = AlphaZeroStrategist(
        policy_value_model_path="models/policy_value.pt",
        mcts_rollouts=100,
        use_bc_pretraining=True
    )
    
    result = strategist.predict(battle_state)
    # => {
    #     "p1_win_rate": 0.73,
    #     "recommended_action": TurnAction(...),
    #     "policy_probs": {...},
    #     "value_estimate": 0.46
    # }

実装フェーズ: P1-4 (Week 4+)
優先度: HIGH 🔥
"""

from __future__ import annotations

import copy
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from predictor.core.models import BattleState, ActionCandidate
from predictor.player.monte_carlo_strategist import Action, TurnAction, MonteCarloStrategist

try:
    import torch
    from predictor.player.policy_value_network_pytorch import (
        PolicyValueNet, BattleStateEncoder
    )
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


@dataclass
class PolicyValueOutput:
    """
    Policy/Value Network の出力
    
    Attributes:
        policy_pokemon1: ポケモン1の行動確率分布 (Factored)
        policy_pokemon2: ポケモン2の行動確率分布 (Factored)
        value: 現在の盤面評価値 (-1.0 ~ 1.0, P1視点)
        inference_time_ms: 推論時間
    """
    policy_pokemon1: Dict[str, float]  # {action_id: probability}
    policy_pokemon2: Dict[str, float]
    value: float  # -1.0 (P2勝利確実) ~ 1.0 (P1勝利確実)
    inference_time_ms: float


class PolicyValueNetwork:
    """
    Policy/Value Network
    
    構造:
    - Input: BattleStateの特徴量ベクトル (盤面表現)
    - Hidden: 複数の全結合層 + Dropout
    - Output:
      * Policy Head 1: ポケモン1の行動確率 (softmax)
      * Policy Head 2: ポケモン2の行動確率 (softmax)
      * Value Head: 勝率評価値 (tanh, -1~1)
    
    Phase 1実装: 簡易版 (ランダム出力)
    Phase 2実装: PyTorch/TensorFlowで本格実装
    """
    
    def __init__(
        self,
        model_path: Optional[Path] = None,
        use_bc_pretraining: bool = True,
        dropout_rate: float = 0.3,
        weight_decay: float = 1e-4
    ):
        self.model_path = model_path
        self.use_bc_pretraining = use_bc_pretraining
        self.dropout_rate = dropout_rate
        self.weight_decay = weight_decay
        
        self.model = None
        self.device = "mps" if TORCH_AVAILABLE and torch.backends.mps.is_available() else "cpu"
        
        if TORCH_AVAILABLE and model_path and Path(model_path).exists():
            self._load_model(model_path)
        else:
            if TORCH_AVAILABLE:
                self._initialize_random_model()
            else:
                print("⚠️  PyTorch not available, using dummy model")
    
    def predict(self, battle_state: BattleState) -> PolicyValueOutput:
        start_time = time.perf_counter()
        
        if not TORCH_AVAILABLE or self.model is None:
            return self._dummy_predict(battle_state, start_time)
        
        # Encode state
        state_features = BattleStateEncoder.encode(battle_state)
        state_tensor = torch.tensor(
            state_features, dtype=torch.float32
        ).unsqueeze(0).to(self.device)
        
        # Forward pass
        self.model.eval()
        with torch.no_grad():
            policy1_logits, policy2_logits, value = self.model(state_tensor)
            
            policy1_probs = torch.softmax(policy1_logits, dim=1)[0]
            policy2_probs = torch.softmax(policy2_logits, dim=1)[0]
            value_scalar = value[0, 0].item()
        
        # Convert to dict
        policy_p1 = {
            f"action_{i}": prob.item()
            for i, prob in enumerate(policy1_probs)
        }
        policy_p2 = {
            f"action_{i}": prob.item()
            for i, prob in enumerate(policy2_probs)
        }
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        return PolicyValueOutput(
            policy_pokemon1=policy_p1,
            policy_pokemon2=policy_p2,
            value=value_scalar,
            inference_time_ms=elapsed_ms
        )
    
    def _dummy_predict(self, battle_state: BattleState, start_time: float) -> PolicyValueOutput:
        legal_actions_p1 = self._get_legal_actions_for_pokemon(battle_state, player="A", slot=0)
        legal_actions_p2 = self._get_legal_actions_for_pokemon(battle_state, player="A", slot=1)
        
        policy_p1 = {action: 1.0 / len(legal_actions_p1) for action in legal_actions_p1} if legal_actions_p1 else {}
        policy_p2 = {action: 1.0 / len(legal_actions_p2) for action in legal_actions_p2} if legal_actions_p2 else {}
        
        value = np.random.uniform(-0.5, 0.5)
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        return PolicyValueOutput(
            policy_pokemon1=policy_p1,
            policy_pokemon2=policy_p2,
            value=value,
            inference_time_ms=elapsed_ms
        )
    
    def train_behavioral_cloning(
        self,
        expert_trajectories: List[Dict[str, Any]],
        epochs: int = 50,
        batch_size: int = 32,
        learning_rate: float = 1e-3
    ) -> Dict[str, float]:
        """
        Behavioral Cloning (BC) による事前学習
        
        上位プレイヤーのログ (N=500試合) から、
        「この盤面でプロはどう打つか」を学習する。
        
        Args:
            expert_trajectories: [{"state": BattleState, "action": TurnAction}, ...]
            epochs: 学習エポック数
            batch_size: バッチサイズ
            learning_rate: 学習率
            
        Returns:
            {"loss": final_loss, "accuracy": final_accuracy}
        """
        print(f"🎓 Behavioral Cloning 開始: {len(expert_trajectories)} trajectories")
        
        # Phase 2実装:
        # 1. expert_trajectories を訓練データに変換
        # 2. Cross-Entropy Loss で Policy を学習
        # 3. MSE Loss で Value を学習
        # 4. Dropout + Weight Decay で正則化
        
        # Phase 1: ダミー実装
        return {
            "loss": 0.0,
            "accuracy": 0.0
        }
    
    def _load_model(self, model_path: Path):
        print(f"📥 Loading: {model_path}")
        if TORCH_AVAILABLE:
            self.model = PolicyValueNet().to(self.device)
            checkpoint = torch.load(model_path, map_location=self.device)
            self.model.load_state_dict(checkpoint["model_state_dict"])
            self.model.eval()
    
    def _initialize_random_model(self):
        print("🎲 Random init")
        if TORCH_AVAILABLE:
            self.model = PolicyValueNet().to(self.device)
    
    def _get_legal_actions_for_pokemon(
        self,
        battle_state: BattleState,
        player: str,
        slot: int
    ) -> List[str]:
        """
        指定されたポケモンの合法手リストを取得
        
        Args:
            battle_state: 対戦状態
            player: "A" or "B"
            slot: ポケモンスロット (0 or 1)
            
        Returns:
            ["move_Moonblast_target2", "move_ShadowBall_target2", ...]
        """
        # Phase 1: 簡易実装
        legal_actions = battle_state.legal_actions.get(player, [])
        
        # スロット指定のフィルタリング (Phase 2で改善)
        action_strings = []
        for action in legal_actions:
            if hasattr(action, 'slot') and action.slot == slot:
                action_id = f"move_{action.move}_target{action.target or 0}"
                action_strings.append(action_id)
        
        # ダミーデータ
        if not action_strings:
            action_strings = [f"move_{i}" for i in range(4)]
        
        return action_strings


class AlphaZeroMCTS:
    """
    Policy/Value Network で誘導される MCTS
    
    通常のMCTSとの違い:
    - Policy Networkの予測確率で探索を偏らせる (UCB式に組み込む)
    - Value Networkの評価値でロールアウトを短縮
    - 探索効率が劇的に向上 (100 rollouts で 1000 rollouts相当の精度)
    """
    
    def __init__(
        self,
        policy_value_network: PolicyValueNetwork,
        n_rollouts: int = 100,
        c_puct: float = 1.0,
        temperature: float = 1.0
    ):
        """
        Args:
            policy_value_network: Policy/Value Network
            n_rollouts: MCTS rollout回数 (NNあり → 少なくてもOK)
            c_puct: UCBの探索係数 (大きいほど探索重視)
            temperature: 行動選択のランダム性 (0=貪欲, 1=確率的)
        """
        self.policy_value_network = policy_value_network
        self.n_rollouts = n_rollouts
        self.c_puct = c_puct
        self.temperature = temperature
        
        # MCTS統計: {state_hash: {action: {"N": visit_count, "W": win_count, "Q": mean_value, "P": prior_prob}}}
        self.stats = {}
    
    def search(self, battle_state: BattleState) -> Tuple[TurnAction, float]:
        """
        MCTS探索を実行し、最適な行動を返す
        
        Args:
            battle_state: 現在の対戦状態
            
        Returns:
            (optimal_action, win_rate)
        """
        # Policy/Value 推論
        pv_output = self.policy_value_network.predict(battle_state)
        
        # 状態のハッシュ化
        state_hash = self._hash_state(battle_state)
        
        # 初回訪問: Policy を Prior として登録
        if state_hash not in self.stats:
            self.stats[state_hash] = {}
            
            # Factored Action Space: 2つのポケモンの行動を組み合わせる
            for action1_id, prob1 in pv_output.policy_pokemon1.items():
                for action2_id, prob2 in pv_output.policy_pokemon2.items():
                    combined_action_id = f"{action1_id}|{action2_id}"
                    prior_prob = prob1 * prob2  # 独立として扱う
                    
                    self.stats[state_hash][combined_action_id] = {
                        "N": 0,  # 訪問回数
                        "W": 0.0,  # 勝利数
                        "Q": 0.0,  # 平均価値
                        "P": prior_prob  # Prior確率 (Policy)
                    }
        
        # n_rollouts 回のシミュレーション
        for _ in range(self.n_rollouts):
            self._simulate(battle_state, state_hash)
        
        # 最も訪問回数が多い行動を選択
        best_action_id = max(
            self.stats[state_hash],
            key=lambda a: self.stats[state_hash][a]["N"]
        )
        
        best_action = self._decode_action(best_action_id, battle_state)
        win_rate = self.stats[state_hash][best_action_id]["Q"]
        
        return best_action, win_rate
    
    def _simulate(self, battle_state: BattleState, state_hash: str) -> float:
        """
        1回のMCTSシミュレーション
        
        Returns:
            評価値 (-1.0 ~ 1.0)
        """
        # UCB式で次の行動を選択
        action_id = self._select_action_ucb(state_hash)
        
        # 行動を適用 (簡易シミュレーション)
        # Phase 2: 実際のゲームエンジン統合
        next_state = copy.deepcopy(battle_state)
        
        # Value Networkで評価
        pv_output = self.policy_value_network.predict(next_state)
        value = pv_output.value
        
        # バックプロパゲーション
        self.stats[state_hash][action_id]["N"] += 1
        self.stats[state_hash][action_id]["W"] += value
        self.stats[state_hash][action_id]["Q"] = (
            self.stats[state_hash][action_id]["W"] / 
            self.stats[state_hash][action_id]["N"]
        )
        
        return value
    
    def _select_action_ucb(self, state_hash: str) -> str:
        """
        UCB (Upper Confidence Bound) 式で行動選択
        
        UCB = Q + c_puct * P * sqrt(N_total) / (1 + N_action)
        
        - Q: 平均価値 (exploitation)
        - P: Prior確率 (Policy誘導)
        - N: 訪問回数 (exploration)
        """
        total_visits = sum(
            self.stats[state_hash][a]["N"]
            for a in self.stats[state_hash]
        )
        
        best_action = None
        best_ucb = -float("inf")
        
        for action_id, stats in self.stats[state_hash].items():
            q_value = stats["Q"]
            prior = stats["P"]
            visits = stats["N"]
            
            ucb = q_value + self.c_puct * prior * math.sqrt(total_visits) / (1 + visits)
            
            if ucb > best_ucb:
                best_ucb = ucb
                best_action = action_id
        
        return best_action
    
    def _hash_state(self, battle_state: BattleState) -> str:
        """状態をハッシュ化 (簡易実装)"""
        # Phase 2: より厳密なハッシュ関数
        return f"turn_{battle_state.turn}"
    
    def _decode_action(self, action_id: str, battle_state: BattleState) -> TurnAction:
        """
        action_id ("move_Moonblast_target2|move_FlareBlitz_target3") を
        TurnAction オブジェクトに変換
        """
        # Phase 2実装
        return TurnAction(
            player_a_actions=[
                Action(type="move", pokemon_slot=0, move_name="Moonblast", target_slot=2)
            ],
            player_b_actions=[
                Action(type="move", pokemon_slot=0, move_name="tackle", target_slot=0)
            ]
        )


class AlphaZeroStrategist:
    """
    AlphaZero-Style Strategist
    
    統合システム:
    - Policy/Value Network (BC事前学習)
    - MCTS (NN誘導探索)
    - Self-Play (データ拡張)
    """
    
    def __init__(
        self,
        policy_value_model_path: Optional[Path] = None,
        mcts_rollouts: int = 100,
        use_bc_pretraining: bool = True,
        mcts_c_puct: float = 1.0
    ):
        """
        Args:
            policy_value_model_path: Policy/Value Networkのパス
            mcts_rollouts: MCTS rollout回数
            use_bc_pretraining: BC事前学習を使用するか
            mcts_c_puct: MCTSの探索係数
        """
        # Policy/Value Network 初期化
        self.policy_value_network = PolicyValueNetwork(
            model_path=policy_value_model_path,
            use_bc_pretraining=use_bc_pretraining
        )
        
        # MCTS 初期化
        self.mcts = AlphaZeroMCTS(
            policy_value_network=self.policy_value_network,
            n_rollouts=mcts_rollouts,
            c_puct=mcts_c_puct
        )
        
        # フォールバック: 純粋MCTS (Phase 1)
        self.fallback_mcts = MonteCarloStrategist(
            n_rollouts=mcts_rollouts,
            max_turns=50
        )
    
    def predict(
        self,
        battle_state: BattleState,
        use_fallback: bool = False
    ) -> Dict[str, Any]:
        """
        勝率予測 + 最適行動選択
        
        Args:
            battle_state: 現在の対戦状態
            use_fallback: Phase 1では純粋MCTSにフォールバック
            
        Returns:
            {
                "p1_win_rate": float,
                "recommended_action": TurnAction,
                "policy_probs": Dict,
                "value_estimate": float,
                "inference_time_ms": float
            }
        """
        start_time = time.perf_counter()
        
        if use_fallback:
            # Phase 1: 純粋MCTSにフォールバック
            result = self.fallback_mcts.predict_win_rate(battle_state)
            return {
                "p1_win_rate": result["player_a_win_rate"],
                "recommended_action": result["optimal_action"],
                "policy_probs": {},
                "value_estimate": result["player_a_win_rate"] * 2 - 1,  # 0~1 → -1~1
                "inference_time_ms": (time.perf_counter() - start_time) * 1000
            }
        
        # Phase 2: AlphaZero-Style Search
        optimal_action, win_rate = self.mcts.search(battle_state)
        pv_output = self.policy_value_network.predict(battle_state)
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        return {
            "p1_win_rate": (win_rate + 1.0) / 2.0,  # -1~1 → 0~1
            "recommended_action": optimal_action,
            "policy_probs": {
                "pokemon1": pv_output.policy_pokemon1,
                "pokemon2": pv_output.policy_pokemon2
            },
            "value_estimate": pv_output.value,
            "inference_time_ms": elapsed_ms
        }
    
    def train_from_expert_logs(
        self,
        expert_log_dir: Path,
        epochs: int = 50
    ):
        """
        上位プレイヤーのログから Behavioral Cloning
        
        Args:
            expert_log_dir: エキスパートログディレクトリ
            epochs: 学習エポック数
        """
        print(f"🎓 Behavioral Cloning 訓練開始: {expert_log_dir}")
        
        # Phase 2実装:
        # 1. expert_log_dir からログファイルを読み込む
        # 2. BattleState + TurnAction のペアに変換
        # 3. policy_value_network.train_behavioral_cloning() を実行
        
        # Phase 1: ダミー
        pass
    
    def self_play(
        self,
        n_games: int = 100,
        save_trajectories: bool = True
    ) -> List[Dict]:
        """
        Self-Play でデータ拡張
        
        学習済みモデル同士を対戦させてデータを生成
        
        Args:
            n_games: 対戦回数
            save_trajectories: 軌跡を保存するか
            
        Returns:
            生成された対戦ログ
        """
        print(f"🎮 Self-Play 開始: {n_games} games")
        
        # Phase 3実装:
        # 1. 2つの AlphaZeroStrategist インスタンスを対戦させる
        # 2. 各ターンの (state, action, outcome) を記録
        # 3. 生成データで再学習
        
        return []
