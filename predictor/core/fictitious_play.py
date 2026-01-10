"""
Fictitious Play - ゲーム理論的均衡解探索

Quantal Response を「解きに行く」ための Fictitious Play 実装。
Restricted Game（候補集合）上で短時間の反復を行い、混合戦略の質を向上させる。

参考: VGC-Bench (Empirical Game-Theoretic Analysis)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import numpy as np


@dataclass
class FictitiousPlayResult:
    """Fictitious Play の結果"""
    
    self_strategy: np.ndarray   # 自分の混合戦略（確率分布）
    opp_strategy: np.ndarray    # 相手の混合戦略（確率分布）
    n_iterations: int           # 実行した反復回数
    converged: bool             # 収束したか
    nash_gap: float             # ナッシュ均衡からのギャップ（小さいほど良い）


def fictitious_play(
    utility_matrix: np.ndarray,
    n_iterations: int = 10,
    convergence_threshold: float = 0.01,
) -> FictitiousPlayResult:
    """
    Fictitious Play を実行して混合戦略を計算
    
    Args:
        utility_matrix: U[i,j] = 自分が行動iを選び、相手が行動jを選んだときの自分の効用
                        shape = (n_self, n_opp)
        n_iterations: 反復回数（推奨: 5〜10）
        convergence_threshold: 収束判定の閾値
    
    Returns:
        FictitiousPlayResult: 混合戦略と収束情報
    """
    n_self, n_opp = utility_matrix.shape
    
    if n_self == 0 or n_opp == 0:
        return FictitiousPlayResult(
            self_strategy=np.array([]),
            opp_strategy=np.array([]),
            n_iterations=0,
            converged=True,
            nash_gap=0.0
        )
    
    # 初期戦略: 一様分布
    self_strategy = np.ones(n_self) / n_self
    opp_strategy = np.ones(n_opp) / n_opp
    
    # 累積カウント（Fictitious Play の核心）
    self_counts = np.zeros(n_self)
    opp_counts = np.zeros(n_opp)
    
    prev_self_strategy = self_strategy.copy()
    converged = False
    
    for iteration in range(n_iterations):
        # ===== 自分の最適応答 =====
        # 相手が opp_strategy を使うとき、各自分行動の期待効用
        expected_utils = utility_matrix @ opp_strategy
        best_self = np.argmax(expected_utils)
        self_counts[best_self] += 1
        
        # ===== 相手の最適応答 =====
        # 自分が self_strategy を使うとき、相手視点の期待効用（負のゲーム）
        opp_expected_utils = -(utility_matrix.T @ self_strategy)
        best_opp = np.argmax(opp_expected_utils)
        opp_counts[best_opp] += 1
        
        # ===== 戦略を更新（平均化） =====
        total_self = self_counts.sum()
        total_opp = opp_counts.sum()
        
        if total_self > 0:
            self_strategy = self_counts / total_self
        if total_opp > 0:
            opp_strategy = opp_counts / total_opp
        
        # ===== 収束判定 =====
        if np.max(np.abs(self_strategy - prev_self_strategy)) < convergence_threshold:
            converged = True
            break
        
        prev_self_strategy = self_strategy.copy()
    
    # ナッシュギャップを計算
    nash_gap = _compute_nash_gap(utility_matrix, self_strategy, opp_strategy)
    
    return FictitiousPlayResult(
        self_strategy=self_strategy,
        opp_strategy=opp_strategy,
        n_iterations=iteration + 1,
        converged=converged,
        nash_gap=nash_gap
    )


def double_oracle(
    utility_matrix: np.ndarray,
    initial_self_indices: List[int] = None,
    initial_opp_indices: List[int] = None,
    n_iterations: int = 5,
) -> FictitiousPlayResult:
    """
    Double Oracle アルゴリズム
    
    互いの最適応答だけを追加してゲームを拡張し、小さなゲームで均衡を解く。
    候補が多い場合に効率的。
    
    Args:
        utility_matrix: 完全な効用行列
        initial_self_indices: 初期の自分候補インデックス
        initial_opp_indices: 初期の相手候補インデックス
        n_iterations: 反復回数
    
    Returns:
        FictitiousPlayResult: 混合戦略
    """
    n_self, n_opp = utility_matrix.shape
    
    # 初期候補（ランダムor上位）
    if initial_self_indices is None:
        initial_self_indices = [np.argmax(utility_matrix.sum(axis=1))]
    if initial_opp_indices is None:
        initial_opp_indices = [np.argmax((-utility_matrix).sum(axis=0))]
    
    active_self = set(initial_self_indices)
    active_opp = set(initial_opp_indices)
    
    for _ in range(n_iterations):
        # 現在のアクティブな候補でサブゲームを構築
        self_list = sorted(active_self)
        opp_list = sorted(active_opp)
        
        sub_matrix = utility_matrix[np.ix_(self_list, opp_list)]
        
        # サブゲームで FP
        sub_result = fictitious_play(sub_matrix, n_iterations=5)
        
        # 完全戦略空間での最適応答を探す
        # 自分: 相手の現戦略に対する最適応答
        sub_opp_strategy = np.zeros(n_opp)
        for i, idx in enumerate(opp_list):
            sub_opp_strategy[idx] = sub_result.opp_strategy[i]
        
        best_self_full = np.argmax(utility_matrix @ sub_opp_strategy)
        active_self.add(best_self_full)
        
        # 相手: 自分の現戦略に対する最適応答
        sub_self_strategy = np.zeros(n_self)
        for i, idx in enumerate(self_list):
            sub_self_strategy[idx] = sub_result.self_strategy[i]
        
        best_opp_full = np.argmax(-(utility_matrix.T @ sub_self_strategy))
        active_opp.add(best_opp_full)
    
    # 最終的な戦略を全空間に拡張
    final_self_strategy = np.zeros(n_self)
    final_opp_strategy = np.zeros(n_opp)
    
    self_list = sorted(active_self)
    opp_list = sorted(active_opp)
    
    final_sub_matrix = utility_matrix[np.ix_(self_list, opp_list)]
    final_result = fictitious_play(final_sub_matrix, n_iterations=10)
    
    for i, idx in enumerate(self_list):
        final_self_strategy[idx] = final_result.self_strategy[i]
    for i, idx in enumerate(opp_list):
        final_opp_strategy[idx] = final_result.opp_strategy[i]
    
    nash_gap = _compute_nash_gap(utility_matrix, final_self_strategy, final_opp_strategy)
    
    return FictitiousPlayResult(
        self_strategy=final_self_strategy,
        opp_strategy=final_opp_strategy,
        n_iterations=n_iterations,
        converged=final_result.converged,
        nash_gap=nash_gap
    )


def _compute_nash_gap(
    utility_matrix: np.ndarray,
    self_strategy: np.ndarray,
    opp_strategy: np.ndarray
) -> float:
    """
    ナッシュ均衡からのギャップを計算
    
    ギャップ = (自分の最適応答効用 - 現戦略効用) + (相手の最適応答効用 - 現戦略効用)
    """
    if len(self_strategy) == 0 or len(opp_strategy) == 0:
        return 0.0
    
    # 現在の期待効用
    current_util = self_strategy @ utility_matrix @ opp_strategy
    
    # 自分の最適応答
    best_self_util = np.max(utility_matrix @ opp_strategy)
    
    # 相手の最適応答（相手視点なので負）
    opp_current_util = -(self_strategy @ utility_matrix @ opp_strategy)
    best_opp_util = np.max(-(utility_matrix.T @ self_strategy))
    
    # ギャップ
    self_gap = max(0, best_self_util - current_util)
    opp_gap = max(0, best_opp_util - opp_current_util)
    
    return self_gap + opp_gap


def blend_with_quantal(
    fp_strategy: np.ndarray,
    quantal_strategy: np.ndarray,
    fp_weight: float = 0.3
) -> np.ndarray:
    """
    Fictitious Play 戦略と Quantal Response 戦略をブレンド
    
    Args:
        fp_strategy: FP で計算した均衡戦略
        quantal_strategy: Quantal Response で計算した戦略
        fp_weight: FP戦略の重み（0〜1）
    
    Returns:
        ブレンドした戦略
    """
    if len(fp_strategy) != len(quantal_strategy):
        return quantal_strategy
    
    blended = fp_weight * fp_strategy + (1 - fp_weight) * quantal_strategy
    
    # 正規化
    total = blended.sum()
    if total > 0:
        blended /= total
    
    return blended
