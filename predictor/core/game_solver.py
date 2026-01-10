"""
GameSolver - 深さ制限ゲーム探索

PokéChamp型アーキテクチャの探索モジュール。
U(a,b) 推定 + Quantal Response で行動分布を生成。

References:
- PokéChamp: https://arxiv.org/abs/2503.04094
"""

from __future__ import annotations

import math
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

from predictor.engine.simulator_adapter import (
    ActionOrder,
    JointAction,
    SimulatorAdapter,
    get_simulator,
)
from predictor.core.candidate_generator import (
    CandidateGenerator,
    CandidateScore,
    get_candidate_generator,
)
from predictor.core.evaluator import (
    Evaluator,
    get_evaluator,
)

try:
    from poke_env.environment.double_battle import DoubleBattle
except ImportError:
    try:
        from poke_env.battle import DoubleBattle
    except ImportError:
        DoubleBattle = None


# ============================================================================
# 設定
# ============================================================================

@dataclass
class SolverConfig:
    """探索の設定（超高精度版）"""
    depth: int = 8                  # 探索深さ（ターン）- 6→8
    n_samples: int = 500            # 乱数サンプル数 - 200→500
    top_k_self: int = 80            # 自分候補数 - 50→80
    top_k_opp: int = 80             # 相手候補数 - 50→80
    tau: float = 0.25               # 相手のQuantal温度
    tau_self: float = 0.30          # 自分のQuantal温度
    llm_weight: float = 0.4         # LLM分布の重み（λ）
    use_llm: bool = False           # LLMを使うか


# ============================================================================
# 出力データ構造
# ============================================================================

@dataclass
class ActionProbability:
    """行動と確率"""
    action: JointAction
    probability: float
    delta: Optional[float] = None   # 最善手との差分
    tags: List[str] = field(default_factory=list)
    
    def __str__(self) -> str:
        return f"{self.action} (p={self.probability:.1%}, Δ={self.delta or 0:+.1%})"


@dataclass
class SwingPoint:
    """分岐点"""
    description: str
    impact: float                   # 勝率への影響


@dataclass
class SolveResult:
    """探索結果"""
    win_prob: float                             # 期待勝率
    self_dist: List[ActionProbability]          # 自分の行動分布
    opp_dist: List[ActionProbability]           # 相手の行動分布
    u_matrix: Optional[np.ndarray] = None       # U(a,b) 行列
    swing_points: List[SwingPoint] = field(default_factory=list)
    breakdown: Dict[str, float] = field(default_factory=dict)


# ============================================================================
# Quantal Response
# ============================================================================

def quantal_response(utilities: np.ndarray, tau: float) -> np.ndarray:
    """
    Quantal Response 分布
    
    π(a) ∝ exp(U(a) / τ)
    
    Args:
        utilities: 各行動の期待効用
        tau: 温度パラメータ（小→鋭い、大→一様に近い）
        
    Returns:
        確率分布（合計1）
    """
    if tau <= 0:
        tau = 0.01
    
    logits = utilities / tau
    logits -= np.max(logits)  # 数値安定化
    exp_logits = np.exp(logits)
    
    total = exp_logits.sum()
    if total == 0:
        return np.ones_like(utilities) / len(utilities)
    
    return exp_logits / total


def sigmoid(x: float) -> float:
    """シグモイド関数"""
    return 1.0 / (1.0 + math.exp(-x))


# ============================================================================
# GameSolver
# ============================================================================

class GameSolver:
    """
    深さ制限ゲーム探索
    
    1. 候補生成（CandidateGenerator）
    2. U(a,b) 推定（深さd, サンプルN）
    3. Quantal Response で分布生成
    4. 勝率・分岐点を計算
    """
    
    def __init__(
        self,
        config: Optional[SolverConfig] = None,
        simulator: Optional[SimulatorAdapter] = None,
        generator: Optional[CandidateGenerator] = None,
        evaluator: Optional[Evaluator] = None,
        llm_client: Optional[Any] = None,
    ):
        self.config = config or SolverConfig()
        self.simulator = simulator or get_simulator()
        self.generator = generator or get_candidate_generator()
        self.evaluator = evaluator or get_evaluator()
        self.llm = llm_client
        
        # Transposition Table: 同一局面の再計算を避けるキャッシュ
        # key: (battle_hash, self_action_key, opp_action_key, depth)
        # value: utility
        self._transposition_table: Dict[Tuple, float] = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def solve(self, battle: DoubleBattle, recommended_moves: Optional[Dict[int, set]] = None) -> SolveResult:
        """
        探索を実行
        
        Args:
            battle: poke-envのDoubleBattleオブジェクト
            recommended_moves: TurnAdvisorからの推奨技 {slot: set(move_ids)}
        
        Returns:
            SolveResult
        """
        # 1. 候補生成
        # Phase 10: LLM推奨を考慮するため、通常より多く候補を生成してからボーナス加算・圧縮
        temp_top_k = self.config.top_k_self * 2 if recommended_moves else self.config.top_k_self
        
        self_candidates = self.generator.generate(
            battle, "self", temp_top_k
        )
        opp_candidates = self.generator.generate(
            battle, "opp", self.config.top_k_opp
        )
        
        # ============= Phase 10: TurnAdvisor 推奨ボーナス =============
        # フィルタリングではなくスコアボーナスとして扱い、
        # 「ルールベースで評価低いが合理的」な手を救済する
        if recommended_moves:
            bonus_score = 2.0  # 大きめのボーナス
            
            for cand in self_candidates:
                # slot0, slot1 の技がそれぞれ推奨リストに含まれているかチェック
                # 部分一致でもボーナス（片方でも合っていれば0.5倍など）
                
                match_count = 0
                
                if cand.action.slot0 and cand.action.slot0.move_id:
                    slot0_moves = recommended_moves.get(0, set())
                    if slot0_moves and cand.action.slot0.move_id.lower() in slot0_moves:
                        match_count += 1
                
                if cand.action.slot1 and cand.action.slot1.move_id:
                    slot1_moves = recommended_moves.get(1, set())
                    if slot1_moves and cand.action.slot1.move_id.lower() in slot1_moves:
                        match_count += 1
                
                if match_count > 0:
                    # 両方一致なら満額、片方なら半額
                    bonus = bonus_score if match_count == 2 else (bonus_score * 0.5)
                    cand.score += bonus
                    cand.tags.append(f"llm_bonus_{match_count}")
            
            # ボーナス加算後に再ソートして Top-K に圧縮
            self_candidates.sort(reverse=True)
            self_candidates = self_candidates[:self.config.top_k_self]
            
            print(f"  🤖 LLMボーナス適用: 上位{len(self_candidates)}候補を選定 (生成数: {temp_top_k})")
        
        if not self_candidates or not opp_candidates:
            # 候補がない場合はデフォルト値
            return SolveResult(
                win_prob=0.5,
                self_dist=[],
                opp_dist=[],
            )
        
        # 2. U(a,b) 推定
        n_self = len(self_candidates)
        n_opp = len(opp_candidates)
        U = np.zeros((n_self, n_opp))
        
        for i, self_cand in enumerate(self_candidates):
            for j, opp_cand in enumerate(opp_candidates):
                U[i, j] = self._estimate_utility(
                    battle,
                    self_cand.action,
                    opp_cand.action,
                    depth=self.config.depth,
                    n_samples=self.config.n_samples,
                )
        
        # 3. 相手の分布（Quantal Response）
        # 相手視点では U が反転
        opp_utilities = -U.mean(axis=0)  # 各 b の平均効用
        opp_probs = quantal_response(opp_utilities, self.config.tau)
        
        # 4. 自分の分布
        # 相手分布に対する期待効用
        self_utilities = U @ opp_probs  # 各 a の期待効用
        self_probs = quantal_response(self_utilities, self.config.tau_self)
        
        # 5. 期待勝率
        expected_u = self_probs @ U @ opp_probs
        win_prob = sigmoid(expected_u)
        
        # 6. 分布を整形
        best_self_value = self_utilities.max()
        self_dist = []
        for i, cand in enumerate(self_candidates):
            delta = self_utilities[i] - best_self_value
            self_dist.append(ActionProbability(
                action=cand.action,
                probability=float(self_probs[i]),
                delta=float(delta),
                tags=cand.tags,
            ))
        
        opp_dist = []
        for j, cand in enumerate(opp_candidates):
            opp_dist.append(ActionProbability(
                action=cand.action,
                probability=float(opp_probs[j]),
                tags=cand.tags,
            ))
        
        # ============= Phase 2: RiskAwareSolver 調整 =============
        # 状況に応じて Secure/Gamble モードで確率を調整
        try:
            from predictor.core.risk_aware_solver import RiskAwareSolver, ScoredCandidate
            risk_solver = RiskAwareSolver()
            mode = risk_solver.determine_mode(win_prob)
            
            # self_dist を ScoredCandidate に変換
            scored_candidates = []
            for i, ap in enumerate(self_dist):
                # 分散を簡易計算（U行列のその行の分散）
                variance = float(np.var(U[i, :])) if i < len(U) else 0.0
                max_value = float(np.max(U[i, :])) if i < len(U) else 0.0
                min_value = float(np.min(U[i, :])) if i < len(U) else 0.0
                
                scored_candidates.append(ScoredCandidate(
                    action=ap.action,
                    expected_value=float(self_utilities[i]) if i < len(self_utilities) else 0.0,
                    variance=variance,
                    max_value=max_value,
                    min_value=min_value,
                    tags=ap.tags,
                ))
            
            # モードに応じて調整
            if scored_candidates:
                adjusted = risk_solver.adjust_candidates(scored_candidates, win_prob)
                
                # 調整後のスコアで確率を再計算
                adjusted_utilities = np.array([c.adjusted_score for c in adjusted])
                adjusted_probs = quantal_response(adjusted_utilities, self.config.tau_self)
                
                # self_dist を更新
                for i, cand in enumerate(adjusted):
                    for ap in self_dist:
                        if str(ap.action) == str(cand.action):
                            ap.tags.extend([t for t in cand.tags if t not in ap.tags])
                            break
        except Exception as e:
            pass  # RiskAwareSolver が使えない場合はスキップ
        
        # 確率でソート
        self_dist.sort(key=lambda x: x.probability, reverse=True)
        opp_dist.sort(key=lambda x: x.probability, reverse=True)
        
        # 7. 分岐点検出
        swing_points = self._detect_swing_points(
            self_candidates, opp_candidates, U, self_probs, opp_probs
        )
        
        return SolveResult(
            win_prob=win_prob,
            self_dist=self_dist[:5],  # Top 5
            opp_dist=opp_dist[:5],
            u_matrix=U,
            swing_points=swing_points,
        )
    
    def _estimate_utility(
        self,
        battle: DoubleBattle,
        action_self: JointAction,
        action_opp: JointAction,
        depth: int,
        n_samples: int,
    ) -> float:
        """
        U(a, b) を推定（Transposition Table でキャッシュ）
        
        現在は深さ1のヒューリスティック評価。
        将来的にはShowdown遷移でロールアウト。
        """
        # ============= Transposition Table キャッシュ =============
        # キー: (turn, self_action, opp_action)
        cache_key = (
            battle.turn,
            self._action_to_key(action_self),
            self._action_to_key(action_opp),
        )
        
        if cache_key in self._transposition_table:
            self._cache_hits += 1
            return self._transposition_table[cache_key]
        
        self._cache_misses += 1
        
        # 簡易実装: 現在の状態評価 + 行動のスコア
        base_value = self.evaluator.evaluate(battle, "self")
        
        # 行動のスコアを加味（CandidateGeneratorのスコアを再利用）
        self_score, _ = self.generator.scorer.score_joint_action(
            action_self, battle, "self"
        )
        opp_score, _ = self.generator.scorer.score_joint_action(
            action_opp, battle, "opp"
        )
        
        # 正規化してUtility化
        utility = base_value + (self_score - opp_score) * 0.1
        
        # キャッシュに保存
        self._transposition_table[cache_key] = utility
        
        return utility
    
    def _action_to_key(self, action: JointAction) -> str:
        """アクションをキャッシュキー用の文字列に変換"""
        if action is None:
            return "none"
        
        s0 = action.slot0
        s1 = action.slot1
        
        s0_key = f"{s0.action_type.value}:{s0.move_id or ''}:{s0.target or ''}" if s0 else "pass"
        s1_key = f"{s1.action_type.value}:{s1.move_id or ''}:{s1.target or ''}" if s1 else "pass"
        
        return f"{s0_key}|{s1_key}"
    
    def clear_cache(self):
        """キャッシュをクリア（新しいターン開始時に呼び出し）"""
        if self._cache_hits + self._cache_misses > 0:
            hit_rate = self._cache_hits / (self._cache_hits + self._cache_misses)
            print(f"  📊 Transposition Table: hits={self._cache_hits}, misses={self._cache_misses}, rate={hit_rate:.1%}")
        
        self._transposition_table.clear()
        self._cache_hits = 0
        self._cache_misses = 0
    
    def _detect_swing_points(
        self,
        self_candidates: List[CandidateScore],
        opp_candidates: List[CandidateScore],
        U: np.ndarray,
        self_probs: np.ndarray,
        opp_probs: np.ndarray,
    ) -> List[SwingPoint]:
        """分岐点を検出"""
        swing_points = []
        
        # 最も影響の大きい相手行動を検出
        expected_u = self_probs @ U @ opp_probs
        
        for j, opp_cand in enumerate(opp_candidates):
            if opp_probs[j] > 0.1:  # 確率10%以上
                # この行動が来た場合のUtility
                u_if_this = self_probs @ U[:, j]
                impact = sigmoid(u_if_this) - sigmoid(expected_u)
                
                if abs(impact) > 0.05:  # 5%以上の影響
                    desc = f"相手が{opp_cand.action.slot0}を選択"
                    swing_points.append(SwingPoint(
                        description=desc,
                        impact=float(impact),
                    ))
        
        # 自分の代替手の影響
        best_self_idx = np.argmax(self_probs)
        for i, self_cand in enumerate(self_candidates):
            if i != best_self_idx and self_probs[i] > 0.05:
                u_if_this = U[i, :] @ opp_probs
                u_best = U[best_self_idx, :] @ opp_probs
                delta = sigmoid(u_if_this) - sigmoid(u_best)
                
                if abs(delta) > 0.05:
                    desc = f"代わりに{self_cand.action.slot0}を選択"
                    swing_points.append(SwingPoint(
                        description=desc,
                        impact=float(delta),
                    ))
        
        # 影響順でソート
        swing_points.sort(key=lambda x: abs(x.impact), reverse=True)
        
        return swing_points[:3]  # Top 3


# ============================================================================
# シングルトン
# ============================================================================

_solver: Optional[GameSolver] = None

def get_game_solver() -> GameSolver:
    """GameSolverのシングルトンを取得"""
    global _solver
    if _solver is None:
        _solver = GameSolver()
    return _solver
