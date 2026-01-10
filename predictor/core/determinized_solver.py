"""
DeterminizedSolver - 不完全情報対応のMCTS

VGCは隠れ情報（持ち物、努力値、テラス）があるため、
完全情報ゲームとしてのMCTSは前提が崩れる。

Determinization は「仮説をサンプルして完全情報化し、
複数回MCTSして平均」という手法。

概念:
  従来:
    MCTS(battle) → 単一の結果

  Determinization:
    for i in 1..K:
        hypothesis = BeliefState.sample()  # 仮説をサンプル
        result_i = MCTS(battle + hypothesis)  # 仮説を適用してMCTS
    
    final = average(result_1, ..., result_K)  # 結果を平均

References:
  - ISMCTS: Cowling et al., 2012
  - Determinization for Poker: Billings et al., 2002
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
import copy


# ============================================================================
# 出力データ構造
# ============================================================================

@dataclass
class DeterminizedResult:
    """Determinization の結果"""
    
    # 平均勝率
    avg_win_prob: float = 0.5
    
    # 各仮説での勝率
    hypothesis_results: List[Tuple[Dict[str, Any], float]] = field(default_factory=list)
    
    # 平均化された行動分布
    # {action_key: probability}
    action_distribution: Dict[str, float] = field(default_factory=dict)
    
    # 最良行動
    best_action: Optional[Any] = None
    
    # 分散（仮説間のばらつき）
    variance: float = 0.0
    
    def to_summary(self) -> str:
        """デバッグ用サマリー"""
        lines = ["=== Determinization Result ==="]
        lines.append(f"平均勝率: {self.avg_win_prob:.1%}")
        lines.append(f"仮説間分散: {self.variance:.4f}")
        
        lines.append("\n仮説別結果:")
        for i, (hypo, win_prob) in enumerate(self.hypothesis_results):
            lines.append(f"  仮説{i+1}: 勝率{win_prob:.1%}")
            # 仮説の要約
            for pokemon, details in list(hypo.items())[:2]:  # 最初の2体のみ
                item = details.get("item", "?")
                spread = details.get("ev_spread", "?")
                lines.append(f"    - {pokemon}: {item} / {spread}")
        
        return "\n".join(lines)


# ============================================================================
# DeterminizedSolver
# ============================================================================

class DeterminizedSolver:
    """
    Determinization による不完全情報対応
    
    BeliefState から仮説をサンプルし、各仮説でMCTSを回して結果を平均する。
    """
    
    def __init__(
        self,
        base_solver: Any,           # GameSolver
        n_determinizations: int = 10  # 3→10 に増加（論文推奨）
    ):
        """
        Args:
            base_solver: 基本の GameSolver
            n_determinizations: 仮説サンプル数（多いほど不確実性を吸収）
        """
        self.base_solver = base_solver
        self.n_determinizations = n_determinizations
    
    def solve(
        self, 
        battle: Any,                # DoubleBattle
        belief: Any,                # BeliefState
        recommended_moves: Optional[Dict[int, set]] = None
    ) -> DeterminizedResult:
        """
        複数の仮説でMCTSを回し、結果を平均
        
        Args:
            battle: DoubleBattle オブジェクト
            belief: BeliefState オブジェクト
            recommended_moves: TurnAdvisor からの推奨技
        
        Returns:
            DeterminizedResult
        """
        results = []
        hypothesis_results = []
        action_votes = defaultdict(list)
        
        for i in range(self.n_determinizations):
            # 1. 仮説をサンプル
            hypothesis = belief.sample()
            
            # 2. 仮説を適用したバトル状態を作成
            battle_with_hypo = self._apply_hypothesis(battle, hypothesis)
            
            # 3. MCTSを実行
            try:
                result = self.base_solver.solve(battle_with_hypo, recommended_moves)
                results.append(result)
                hypothesis_results.append((hypothesis, result.win_prob))
                
                # 行動分布を集計
                for ap in result.self_dist:
                    action_key = self._action_to_key(ap.action)
                    action_votes[action_key].append(ap.probability)
                    
            except Exception as e:
                print(f"  ⚠️ Determinization {i+1} failed: {e}")
                continue
        
        if not results:
            return DeterminizedResult(avg_win_prob=0.5)
        
        # 4. 結果を平均
        avg_win_prob = sum(r.win_prob for r in results) / len(results)
        
        # 分散を計算
        win_probs = [r.win_prob for r in results]
        mean = avg_win_prob
        variance = sum((p - mean) ** 2 for p in win_probs) / len(win_probs)
        
        # 行動分布を平均
        action_distribution = {}
        for action_key, probs in action_votes.items():
            action_distribution[action_key] = sum(probs) / len(probs)
        
        # 最良行動を決定
        best_action = None
        if action_distribution:
            best_key = max(action_distribution.keys(), key=lambda k: action_distribution[k])
            # 最初の結果から対応するアクションを取得
            if results and results[0].self_dist:
                for ap in results[0].self_dist:
                    if self._action_to_key(ap.action) == best_key:
                        best_action = ap.action
                        break
        
        return DeterminizedResult(
            avg_win_prob=avg_win_prob,
            hypothesis_results=hypothesis_results,
            action_distribution=action_distribution,
            best_action=best_action,
            variance=variance,
        )
    
    def _apply_hypothesis(self, battle: Any, hypothesis: Dict[str, Any]) -> Any:
        """
        仮説を適用したバトル状態を作成
        
        注意: poke-env の DoubleBattle はイミュータブルなので、
        実際には内部のシミュレーション用データ構造に仮説を適用する必要がある。
        
        現在は簡易実装として、仮説をメタデータとして添付する。
        """
        # 仮説をバトルオブジェクトに添付
        # 実際の適用は evaluator や damage_calc で行う
        battle_copy = battle  # shallow copy（poke-envの制限）
        
        # カスタム属性として仮説を添付
        if not hasattr(battle_copy, '_hypothesis'):
            battle_copy._hypothesis = {}
        battle_copy._hypothesis = hypothesis
        
        return battle_copy
    
    def _action_to_key(self, action: Any) -> str:
        """
        アクションを比較可能なキーに変換
        """
        if action is None:
            return "none"
        
        # JointAction の場合
        if hasattr(action, 'slot0') and hasattr(action, 'slot1'):
            slot0_key = self._order_to_key(action.slot0)
            slot1_key = self._order_to_key(action.slot1)
            return f"{slot0_key}|{slot1_key}"
        
        return str(action)
    
    def _order_to_key(self, order: Any) -> str:
        """ActionOrder を文字列キーに変換"""
        if order is None:
            return "pass"
        
        if hasattr(order, 'action_type'):
            action_type = str(order.action_type)
            move_id = getattr(order, 'move_id', '') or ''
            target = getattr(order, 'target', '') or ''
            return f"{action_type}:{move_id}:{target}"
        
        return str(order)


# ============================================================================
# 統合用ヘルパー
# ============================================================================

def create_determinized_solver(
    base_solver: Any,
    n_determinizations: int = 3
) -> DeterminizedSolver:
    """DeterminizedSolver を作成"""
    return DeterminizedSolver(
        base_solver=base_solver,
        n_determinizations=n_determinizations
    )
