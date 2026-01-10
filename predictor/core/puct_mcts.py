"""
AlphaZero-style PUCT MCTS Implementation

AlphaZero式のMCTS探索（PUCT選択式）を実装。
学習済みPolicy/Valueモデルを活用して効率的に探索。

参考:
- AlphaZero: https://arxiv.org/abs/1712.01815
- Metamon: https://arxiv.org/abs/2504.04395
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from predictor.core.prediction_engine import (
    ActionCandidate,
    JointAction,
    ActionGenerator,
    PredictResult,
)
from predictor.core.policy_value_learning import (
    get_policy_model,
    get_value_model,
    StateFeatures,
)


# ============================================================================
# MCTSノード
# ============================================================================

@dataclass
class MCTSNode:
    """
    MCTSの探索ノード
    
    AlphaZero式では、各ノードは状態を表し、
    子ノードへのエッジが行動を表す。
    """
    state: Any  # バトル状態
    parent: Optional['MCTSNode'] = None
    action: Optional[JointAction] = None  # 親からこのノードへの行動
    
    # 統計情報
    visit_count: int = 0
    value_sum: float = 0.0
    prior: float = 0.0  # Policyによる事前確率
    
    # 子ノード
    children: Dict[JointAction, 'MCTSNode'] = field(default_factory=dict)
    is_expanded: bool = False
    is_terminal: bool = False
    
    def q_value(self) -> float:
        """平均価値 Q(s, a)"""
        if self.visit_count == 0:
            return 0.0
        return self.value_sum / self.visit_count
    
    def ucb_score(self, c_puct: float = 1.5) -> float:
        """
        PUCT スコア
        
        UCB(s, a) = Q(s, a) + c_puct * P(s, a) * sqrt(N(s)) / (1 + N(s, a))
        """
        if self.parent is None:
            return 0.0
        
        parent_visits = self.parent.visit_count
        exploration = c_puct * self.prior * math.sqrt(parent_visits) / (1 + self.visit_count)
        return self.q_value() + exploration
    
    def best_child(self, c_puct: float = 1.5) -> Optional['MCTSNode']:
        """PUCTスコアが最も高い子ノードを選択"""
        if not self.children:
            return None
        return max(self.children.values(), key=lambda c: c.ucb_score(c_puct))
    
    def most_visited_child(self) -> Optional['MCTSNode']:
        """最も訪問回数が多い子ノードを選択（推論時）"""
        if not self.children:
            return None
        return max(self.children.values(), key=lambda c: c.visit_count)


# ============================================================================
# PUCT MCTS
# ============================================================================

class PUCTMCTS:
    """
    AlphaZero式 PUCT MCTS
    
    特徴:
    - Policy ネットワークで候補手の事前確率を設定
    - Value ネットワークで葉ノードを評価（ロールアウト不要）
    - PUCT式で探索と活用をバランス
    """
    
    def __init__(
        self,
        c_puct: float = 1.5,
        n_simulations: int = 100,
        temperature: float = 1.0,
        use_learned_models: bool = True,
    ):
        self.c_puct = c_puct
        self.n_simulations = n_simulations
        self.temperature = temperature
        self.use_learned_models = use_learned_models
        
        # モデル
        self.action_generator = ActionGenerator()
        self._policy_model = None
        self._value_model = None
        
        if use_learned_models:
            try:
                self._policy_model = get_policy_model()
                self._value_model = get_value_model()
            except Exception as e:
                print(f"⚠️ Model load failed: {e}")
    
    def search(self, battle_state: Any) -> Tuple[JointAction, Dict[str, Any]]:
        """
        MCTS探索を実行
        
        Returns:
            (best_action, info): 最善手と探索情報
        """
        # ルートノード作成
        root = MCTSNode(state=battle_state)
        
        # シミュレーション実行
        for _ in range(self.n_simulations):
            node = root
            path = [node]
            
            # 1. 選択（Select）: 葉ノードまで移動
            while node.is_expanded and not node.is_terminal:
                child = node.best_child(self.c_puct)
                if child is None:
                    break
                node = child
                path.append(node)
            
            # 2. 展開（Expand）: 未展開なら展開
            if not node.is_expanded and not node.is_terminal:
                self._expand(node)
            
            # 3. 評価（Evaluate）: 葉ノードの価値を評価
            value = self._evaluate(node)
            
            # 4. バックアップ（Backup）: パスを逆にたどって統計更新
            self._backup(path, value)
        
        # 最善手を選択
        best_child = root.most_visited_child()
        if best_child is None:
            # 子がない場合はデフォルト行動
            actions = self._generate_actions(battle_state)
            if actions:
                return actions[0], {"visits": 0, "q_value": 0.5}
            else:
                return self._default_action(), {"visits": 0, "q_value": 0.5}
        
        # 探索情報
        info = {
            "visits": root.visit_count,
            "q_value": best_child.q_value(),
            "action_visits": {
                str(action): child.visit_count
                for action, child in root.children.items()
            },
        }
        
        return best_child.action, info
    
    def get_action_probs(self, battle_state: Any) -> List[Tuple[JointAction, float]]:
        """
        探索後の行動確率分布を取得（学習用）
        
        Returns:
            [(action, probability), ...]
        """
        root = MCTSNode(state=battle_state)
        
        for _ in range(self.n_simulations):
            node = root
            path = [node]
            
            while node.is_expanded and not node.is_terminal:
                child = node.best_child(self.c_puct)
                if child is None:
                    break
                node = child
                path.append(node)
            
            if not node.is_expanded and not node.is_terminal:
                self._expand(node)
            
            value = self._evaluate(node)
            self._backup(path, value)
        
        # 訪問回数から確率を計算
        if not root.children:
            return []
        
        visits = np.array([child.visit_count for child in root.children.values()])
        
        if self.temperature == 0:
            # Greedy
            probs = np.zeros_like(visits, dtype=float)
            probs[np.argmax(visits)] = 1.0
        else:
            # Softmax with temperature
            visits_temp = visits ** (1 / self.temperature)
            probs = visits_temp / visits_temp.sum()
        
        return [
            (action, float(prob))
            for action, prob in zip(root.children.keys(), probs)
        ]
    
    def _expand(self, node: MCTSNode):
        """ノードを展開"""
        actions = self._generate_actions(node.state)
        priors = self._get_policy_priors(node.state, actions)
        
        for action, prior in zip(actions, priors):
            # 子ノードを作成（状態遷移は簡略化）
            child = MCTSNode(
                state=node.state,  # 本来は遷移後の状態
                parent=node,
                action=action,
                prior=prior,
            )
            node.children[action] = child
        
        node.is_expanded = True
    
    def _evaluate(self, node: MCTSNode) -> float:
        """葉ノードを評価"""
        if node.is_terminal:
            # 終端状態の場合は勝敗を返す
            return self._get_terminal_value(node.state)
        
        if self._value_model is not None and self._value_model.model is not None:
            state_features = self._state_to_features(node.state)
            if state_features is not None:
                return self._value_model.predict(state_features)
        
        # フォールバック: ヒューリスティック評価
        return self._heuristic_value(node.state)
    
    def _backup(self, path: List[MCTSNode], value: float):
        """パスを逆にたどって統計更新"""
        for node in reversed(path):
            node.visit_count += 1
            node.value_sum += value
            value = 1 - value  # 相手視点に反転
    
    def _generate_actions(self, state: Any) -> List[JointAction]:
        """行動候補を生成"""
        if hasattr(state, 'available_moves'):
            return self.action_generator.generate_candidates(
                available_moves=state.available_moves,
                available_switches=[
                    [p.species for p in state.available_switches[0]] if state.available_switches else [],
                    [p.species for p in state.available_switches[1]] if len(state.available_switches) > 1 else [],
                ] if hasattr(state, 'available_switches') else [[], []],
                active_pokemon=state.active_pokemon if hasattr(state, 'active_pokemon') else [],
                opponent_pokemon=state.opponent_active_pokemon if hasattr(state, 'opponent_active_pokemon') else [],
            )
        return []
    
    def _get_policy_priors(self, state: Any, actions: List[JointAction]) -> List[float]:
        """Policyモデルから事前確率を取得"""
        if not actions:
            return []
        
        # 一様分布でフォールバック
        uniform = 1.0 / len(actions)
        
        if self._policy_model is None or self._policy_model.model_slot0 is None:
            return [uniform] * len(actions)
        
        # 本来はPolicyモデルから確率を取得
        # 現在は一様分布
        return [uniform] * len(actions)
    
    def _state_to_features(self, state: Any) -> Optional[StateFeatures]:
        """状態を特徴量に変換"""
        try:
            self_hp = []
            self_status = []
            
            if hasattr(state, 'active_pokemon'):
                for p in state.active_pokemon[:2]:
                    if p:
                        self_hp.append(p.current_hp_fraction)
                        self_status.append(0)  # 簡略化
                    else:
                        self_hp.append(0.0)
                        self_status.append(0)
            
            while len(self_hp) < 2:
                self_hp.append(0.0)
                self_status.append(0)
            
            opp_hp = []
            opp_status = []
            
            if hasattr(state, 'opponent_active_pokemon'):
                for p in state.opponent_active_pokemon[:2]:
                    if p:
                        opp_hp.append(p.current_hp_fraction)
                        opp_status.append(0)
                    else:
                        opp_hp.append(0.0)
                        opp_status.append(0)
            
            while len(opp_hp) < 2:
                opp_hp.append(0.0)
                opp_status.append(0)
            
            return StateFeatures(
                self_hp=self_hp,
                self_status=self_status,
                self_boosts=[{}, {}],
                opp_hp=opp_hp,
                opp_status=opp_status,
                opp_boosts=[{}, {}],
                self_reserves=0,
                opp_reserves=0,
                weather=0,
                terrain=0,
                trick_room=0,
                tailwind_self=0,
                tailwind_opp=0,
                turn=getattr(state, 'turn', 1),
            )
        except Exception:
            return None
    
    def _heuristic_value(self, state: Any) -> float:
        """ヒューリスティック評価"""
        if hasattr(state, 'active_pokemon'):
            self_hp = sum(p.current_hp_fraction for p in state.active_pokemon if p)
            opp_hp = sum(p.current_hp_fraction for p in state.opponent_active_pokemon if p)
            return (self_hp - opp_hp) / 4 + 0.5
        return 0.5
    
    def _get_terminal_value(self, state: Any) -> float:
        """終端状態の価値"""
        if hasattr(state, 'won'):
            return 1.0 if state.won else 0.0
        return 0.5
    
    def _default_action(self) -> JointAction:
        """デフォルト行動"""
        return JointAction(
            slot0_action=ActionCandidate(slot=0, action_type="move", move_or_pokemon="tackle"),
            slot1_action=ActionCandidate(slot=1, action_type="move", move_or_pokemon="tackle"),
        )


# ============================================================================
# シングルトン
# ============================================================================

_puct_mcts: Optional[PUCTMCTS] = None

def get_puct_mcts(n_simulations: int = 100) -> PUCTMCTS:
    """PUCT MCTS のシングルトンを取得"""
    global _puct_mcts
    if _puct_mcts is None:
        _puct_mcts = PUCTMCTS(n_simulations=n_simulations)
    return _puct_mcts
