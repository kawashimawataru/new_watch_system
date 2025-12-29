"""
Prediction Logic: 予測エンジンコア

SVダブル・Showdown・オープンチームシート（完全情報）前提

研究参照:
- Metamon: Policy/Value学習
- PokéChamp: minimax + LLM
- PokeLLMon: KAG, パニック抑制
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ============================================================================
# データクラス定義
# ============================================================================

@dataclass
class ActionCandidate:
    """1体分の行動候補"""
    slot: int  # 0 or 1
    action_type: str  # "move" or "switch"
    move_or_pokemon: str  # 技ID or ポケモン種族名
    target: Optional[int] = None  # 対象スロット (0,1=自分側, 2,3=相手側)
    priority: int = 0  # 技優先度
    
    def __hash__(self):
        return hash((self.slot, self.action_type, self.move_or_pokemon, self.target))
    
    def __eq__(self, other):
        if not isinstance(other, ActionCandidate):
            return False
        return (self.slot, self.action_type, self.move_or_pokemon, self.target) == \
               (other.slot, other.action_type, other.move_or_pokemon, other.target)


@dataclass
class JointAction:
    """ダブルバトルの1ターン行動（2体同時）"""
    slot0_action: ActionCandidate
    slot1_action: ActionCandidate
    
    def __hash__(self):
        return hash((self.slot0_action, self.slot1_action))
    
    def __eq__(self, other):
        if not isinstance(other, JointAction):
            return False
        return self.slot0_action == other.slot0_action and self.slot1_action == other.slot1_action


@dataclass
class ActionProbability:
    """行動と確率のペア"""
    action: JointAction
    probability: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "slot0": {
                "type": self.action.slot0_action.action_type,
                "move": self.action.slot0_action.move_or_pokemon,
                "target": self.action.slot0_action.target,
            },
            "slot1": {
                "type": self.action.slot1_action.action_type,
                "move": self.action.slot1_action.move_or_pokemon,
                "target": self.action.slot1_action.target,
            },
            "probability": self.probability,
        }


@dataclass
class OrderProbability:
    """行動順と確率"""
    order_description: str  # 例: "Rillaboom → Flutter Mane → Urshifu → Incineroar"
    probability: float


@dataclass
class ActionDelta:
    """代替手による勝率差（実況材料）"""
    action: JointAction
    win_delta: float  # +0.12 = この手なら勝率12%上がる
    rationale: str  # 根拠


@dataclass
class PredictResult:
    """
    予測エンジンの最終出力（毎ターン）
    
    観戦AIが返すべき情報を全て含む。
    """
    # 1. 期待勝率
    win_prob: float
    
    # 2. 自分の行動分布 Top-K（確率付き）
    self_action_dist: List[ActionProbability]
    
    # 3. 相手の行動分布 Top-K（確率付き）
    opp_action_dist: List[ActionProbability]
    
    # 4. 行動順の確率分布
    order_dist: List[OrderProbability]
    
    # 5. 代替手による勝率差（感度分析）
    deltas: List[ActionDelta]
    
    # 6. 根拠アンカー（KAG用）
    rationales: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "winProb": self.win_prob,
            "selfActionDist": [a.to_dict() for a in self.self_action_dist],
            "oppActionDist": [a.to_dict() for a in self.opp_action_dist],
            "orderDist": [{"order": o.order_description, "prob": o.probability} for o in self.order_dist],
            "deltas": [{"action": d.action, "delta": d.win_delta, "rationale": d.rationale} for d in self.deltas],
            "rationales": self.rationales,
        }


# ============================================================================
# Quantal Response (混合戦略)
# ============================================================================

def quantal_response(utilities: np.ndarray, tau: float = 0.5) -> np.ndarray:
    """
    Quantal Response Equilibrium (QRE) の簡易版
    
    相手は "価値が高い手ほど選びやすい" と仮定して確率化。
    
    Args:
        utilities: 各行動の効用値 (1D array)
        tau: 温度パラメータ (小=鋭い、大=散る)
    
    Returns:
        各行動の選択確率 (softmax)
    """
    if tau <= 0:
        tau = 0.01  # 0除算防止
    
    # オーバーフロー防止のため最大値を引く
    max_u = np.max(utilities)
    exp_u = np.exp((utilities - max_u) / tau)
    return exp_u / np.sum(exp_u)


def solve_quantal_game(
    payoff_matrix: np.ndarray,
    tau_self: float = 0.5,
    tau_opp: float = 0.5,
    iterations: int = 20
) -> Tuple[np.ndarray, np.ndarray]:
    """
    同時手番ゲームを Quantal Response で解く
    
    Args:
        payoff_matrix: U[a, b] = 自分がaを選び相手がbを選んだ時の自分の期待勝率
        tau_self: 自分の温度（観戦では無視して良い、対戦AIで使う）
        tau_opp: 相手の温度（プレイスタイルを表現）
        iterations: 収束までの反復回数
    
    Returns:
        (自分の混合戦略, 相手の混合戦略)
    """
    n_self = payoff_matrix.shape[0]
    n_opp = payoff_matrix.shape[1]
    
    # 初期化：一様分布
    p_self = np.ones(n_self) / n_self
    p_opp = np.ones(n_opp) / n_opp
    
    for _ in range(iterations):
        # 相手の応答：各行動の期待効用
        opp_utilities = -payoff_matrix.T @ p_self  # 相手視点は符号反転
        p_opp = quantal_response(opp_utilities, tau_opp)
        
        # 自分の応答
        self_utilities = payoff_matrix @ p_opp
        p_self = quantal_response(self_utilities, tau_self)
    
    return p_self, p_opp


# ============================================================================
# 候補手生成
# ============================================================================

class ActionGenerator:
    """候補手生成器"""
    
    def __init__(
        self,
        top_m_moves: int = 4,  # 各スロットのTop技数
        top_s_switches: int = 2,  # 各スロットのTop交代数
        top_k_joint: int = 30,  # 最終的なJointAction数
    ):
        self.top_m = top_m_moves
        self.top_s = top_s_switches
        self.top_k = top_k_joint
    
    def generate_candidates(
        self,
        available_moves: List[List[Any]],  # [slot0の技リスト, slot1の技リスト]
        available_switches: List[List[str]],  # [slot0の交代先, slot1の交代先]
        active_pokemon: List[Any],  # 場のポケモン
        opponent_pokemon: List[Any],  # 相手の場のポケモン
        value_fn: Optional[callable] = None,  # 行動のスコア関数
    ) -> List[JointAction]:
        """
        候補手を生成
        
        1. 各スロットの単体行動候補を作成
        2. 2体の組み合わせを作成
        3. スコアでTop-Kに絞る
        """
        # スロット0の候補
        slot0_candidates = self._generate_slot_candidates(
            slot=0,
            moves=available_moves[0] if len(available_moves) > 0 else [],
            switches=available_switches[0] if len(available_switches) > 0 else [],
            active=active_pokemon[0] if len(active_pokemon) > 0 else None,
            opponents=opponent_pokemon,
        )
        
        # スロット1の候補
        slot1_candidates = self._generate_slot_candidates(
            slot=1,
            moves=available_moves[1] if len(available_moves) > 1 else [],
            switches=available_switches[1] if len(available_switches) > 1 else [],
            active=active_pokemon[1] if len(active_pokemon) > 1 else None,
            opponents=opponent_pokemon,
        )
        
        # 組み合わせ生成
        joint_actions = []
        for a0 in slot0_candidates:
            for a1 in slot1_candidates:
                # 同じポケモンに交代しようとしていないかチェック
                if a0.action_type == "switch" and a1.action_type == "switch":
                    if a0.move_or_pokemon == a1.move_or_pokemon:
                        continue  # 同じポケモンへの同時交代は不可
                
                joint_actions.append(JointAction(slot0_action=a0, slot1_action=a1))
        
        # スコアでソートしてTop-K
        if value_fn:
            scored = [(ja, value_fn(ja)) for ja in joint_actions]
            scored.sort(key=lambda x: x[1], reverse=True)
            joint_actions = [ja for ja, _ in scored[:self.top_k]]
        else:
            joint_actions = joint_actions[:self.top_k]
        
        return joint_actions
    
    def _generate_slot_candidates(
        self,
        slot: int,
        moves: List[Any],
        switches: List[str],
        active: Any,
        opponents: List[Any],
    ) -> List[ActionCandidate]:
        """1スロット分の候補生成"""
        candidates = []
        
        # 技候補（Top-M）
        move_scores = []
        for move in moves:
            score = self._score_move(move, active, opponents)
            move_scores.append((move, score))
        
        move_scores.sort(key=lambda x: x[1], reverse=True)
        for move, _ in move_scores[:self.top_m]:
            # ターゲット決定
            targets = self._get_targets(move, opponents)
            for target in targets:
                candidates.append(ActionCandidate(
                    slot=slot,
                    action_type="move",
                    move_or_pokemon=move.id if hasattr(move, 'id') else str(move),
                    target=target,
                    priority=move.priority if hasattr(move, 'priority') else 0,
                ))
        
        # 交代候補（Top-S）
        for pokemon in switches[:self.top_s]:
            candidates.append(ActionCandidate(
                slot=slot,
                action_type="switch",
                move_or_pokemon=pokemon,
                target=None,
            ))
        
        return candidates
    
    def _score_move(self, move: Any, active: Any, opponents: List[Any]) -> float:
        """技のスコア（簡易版：威力ベース）"""
        base_power = getattr(move, 'base_power', 0) or 0
        priority = getattr(move, 'priority', 0)
        
        score = base_power
        score += priority * 20  # 先制技ボーナス
        
        # 特殊技のボーナス
        move_id = getattr(move, 'id', str(move)).lower()
        if move_id in ['protect', 'detect']:
            score += 30  # 守るは価値が高い
        if move_id in ['fakeout', 'followme', 'ragepowder']:
            score += 50  # 行動阻害は高価値
        if move_id in ['tailwind', 'trickroom']:
            score += 40  # 速度操作
        
        return score
    
    def _get_targets(self, move: Any, opponents: List[Any]) -> List[int]:
        """技のターゲット候補"""
        target_type = getattr(move, 'target', 'normal')
        
        if target_type in ['allAdjacentFoes', 'allAdjacent']:
            return [None]  # 範囲技はターゲット指定不要
        
        # 単体技：生きてる相手に対して
        targets = []
        for i, opp in enumerate(opponents):
            if opp and not getattr(opp, 'fainted', False):
                targets.append(i + 2)  # 相手は slot 2, 3
        
        return targets if targets else [2]  # デフォルト


# ============================================================================
# 予測エンジン本体
# ============================================================================

class PredictionEngine:
    """
    予測エンジン
    
    完全情報前提のゲーム理論ベース予測。
    
    フロー:
    1. 状態から候補手を生成
    2. 利得行列 U(a,b) を推定
    3. Quantal Response で混合戦略を計算
    4. 行動分布・勝率・根拠を出力
    """
    
    def __init__(
        self,
        tau_opp: float = 0.5,  # 相手の温度（スタイル）
        depth: int = 2,  # 探索深さ
        use_learned_value: bool = True,  # 学習済みValueを使用
    ):
        self.action_generator = ActionGenerator()
        self.tau_opp = tau_opp
        self.depth = depth
        self.use_learned_value = use_learned_value
        
        # Value関数（学習済みモデルがあればそれを使用）
        self._value_model = None
        if use_learned_value:
            try:
                from predictor.core.policy_value_learning import get_value_model
                self._value_model = get_value_model()
            except Exception as e:
                print(f"⚠️ ValueModel load failed: {e}")
        
        self.value_fn = self._learned_value if self._value_model else self._heuristic_value
    
    def predict(self, battle_state: Any) -> PredictResult:
        """
        予測を実行
        
        Args:
            battle_state: 現在のバトル状態（poke-env Battle or BattleState）
        
        Returns:
            PredictResult: 予測結果
        """
        # 1. 候補手生成
        self_actions = self._generate_self_actions(battle_state)
        opp_actions = self._generate_opp_actions(battle_state)
        
        if not self_actions or not opp_actions:
            return self._empty_result()
        
        # 2. 利得行列の構築
        payoff_matrix = self._build_payoff_matrix(battle_state, self_actions, opp_actions)
        
        # 3. 混合戦略を計算
        p_self, p_opp = solve_quantal_game(payoff_matrix, tau_opp=self.tau_opp)
        
        # 4. 期待勝率
        win_prob = float(p_self @ payoff_matrix @ p_opp)
        
        # 5. 行動分布を構築
        self_action_dist = [
            ActionProbability(action=a, probability=float(p))
            for a, p in zip(self_actions, p_self)
            if p > 0.01  # 1%未満は切り捨て
        ]
        self_action_dist.sort(key=lambda x: x.probability, reverse=True)
        
        opp_action_dist = [
            ActionProbability(action=a, probability=float(p))
            for a, p in zip(opp_actions, p_opp)
            if p > 0.01
        ]
        opp_action_dist.sort(key=lambda x: x.probability, reverse=True)
        
        # 6. 行動順分布（簡易版）
        order_dist = self._calculate_order_distribution(battle_state)
        
        # 7. 感度分析（代替手差分）
        deltas = self._calculate_deltas(self_actions, p_self, payoff_matrix, p_opp)
        
        # 8. 根拠アンカー
        rationales = self._generate_rationales(
            battle_state, self_action_dist, opp_action_dist, win_prob
        )
        
        return PredictResult(
            win_prob=win_prob,
            self_action_dist=self_action_dist[:5],  # Top-5
            opp_action_dist=opp_action_dist[:5],
            order_dist=order_dist,
            deltas=deltas[:3],  # Top-3
            rationales=rationales,
        )
    
    def _generate_self_actions(self, battle_state: Any) -> List[JointAction]:
        """自分の候補手生成"""
        # poke-env Battle の場合
        if hasattr(battle_state, 'available_moves'):
            return self.action_generator.generate_candidates(
                available_moves=battle_state.available_moves,
                available_switches=[
                    [p.species for p in battle_state.available_switches[0]] if battle_state.available_switches else [],
                    [p.species for p in battle_state.available_switches[1]] if len(battle_state.available_switches) > 1 else [],
                ] if hasattr(battle_state, 'available_switches') else [[], []],
                active_pokemon=battle_state.active_pokemon if hasattr(battle_state, 'active_pokemon') else [],
                opponent_pokemon=battle_state.opponent_active_pokemon if hasattr(battle_state, 'opponent_active_pokemon') else [],
            )
        return []
    
    def _generate_opp_actions(self, battle_state: Any) -> List[JointAction]:
        """相手の候補手生成（オープンシート前提）"""
        # オープンシートなので相手の技も既知
        if hasattr(battle_state, 'opponent_active_pokemon'):
            opp_moves = []
            opp_switches = []
            for pokemon in battle_state.opponent_active_pokemon:
                if pokemon:
                    moves = list(pokemon.moves.values()) if hasattr(pokemon, 'moves') and pokemon.moves else []
                    opp_moves.append(moves)
                else:
                    opp_moves.append([])
            
            # 控えポケモン
            if hasattr(battle_state, 'opponent_team'):
                for pokemon in battle_state.opponent_team.values():
                    if not pokemon.active:
                        opp_switches.append(pokemon.species)
            
            return self.action_generator.generate_candidates(
                available_moves=opp_moves,
                available_switches=[opp_switches[:2], opp_switches[:2]],  # 両スロット共通
                active_pokemon=battle_state.opponent_active_pokemon,
                opponent_pokemon=battle_state.active_pokemon if hasattr(battle_state, 'active_pokemon') else [],
            )
        return []
    
    def _build_payoff_matrix(
        self,
        battle_state: Any,
        self_actions: List[JointAction],
        opp_actions: List[JointAction],
    ) -> np.ndarray:
        """利得行列を構築"""
        n_self = len(self_actions)
        n_opp = len(opp_actions)
        
        matrix = np.zeros((n_self, n_opp))
        
        for i, a in enumerate(self_actions):
            for j, b in enumerate(opp_actions):
                # U(a, b) = 自分がaを選び相手がbを選んだ時の期待勝率
                matrix[i, j] = self._evaluate_outcome(battle_state, a, b)
        
        return matrix
    
    def _evaluate_outcome(
        self,
        battle_state: Any,
        self_action: JointAction,
        opp_action: JointAction,
    ) -> float:
        """
        (a, b) の組み合わせの期待勝率を評価
        
        Phase 1: ヒューリスティック評価
        Phase 2: Showdownエンジン遷移 + Value関数
        """
        # 現状はヒューリスティック
        return self.value_fn(battle_state, self_action, opp_action)
    
    def _heuristic_value(
        self,
        battle_state: Any,
        self_action: JointAction,
        opp_action: JointAction,
    ) -> float:
        """
        ヒューリスティック評価関数
        
        後でログ学習Valueに置き換える。
        """
        # ベースライン: HP差から勝率推定
        base_value = 0.5
        
        if hasattr(battle_state, 'active_pokemon'):
            self_hp = sum(p.current_hp_fraction for p in battle_state.active_pokemon if p)
            opp_hp = sum(p.current_hp_fraction for p in battle_state.opponent_active_pokemon if p)
            base_value = (self_hp - opp_hp) / 4 + 0.5  # -0.5〜1.5 を 0〜1 に
        
        # 行動による補正
        action_bonus = 0.0
        
        # 守るは相手の集中を避けられる可能性
        if self_action.slot0_action.move_or_pokemon == 'protect':
            action_bonus += 0.02
        if self_action.slot1_action.move_or_pokemon == 'protect':
            action_bonus += 0.02
        
        # 先制技のボーナス
        if self_action.slot0_action.priority > 0:
            action_bonus += 0.01 * self_action.slot0_action.priority
        if self_action.slot1_action.priority > 0:
            action_bonus += 0.01 * self_action.slot1_action.priority
        
        return max(0.0, min(1.0, base_value + action_bonus))
    
    def _learned_value(
        self,
        battle_state: Any,
        self_action: JointAction,
        opp_action: JointAction,
    ) -> float:
        """
        学習済みValueモデルによる評価
        
        StateFeatures に変換してモデルに入力。
        """
        if self._value_model is None:
            return self._heuristic_value(battle_state, self_action, opp_action)
        
        state_features = self._battle_to_state_features(battle_state)
        if state_features is None:
            return self._heuristic_value(battle_state, self_action, opp_action)
        
        # 行動による微調整（学習Valueはベース、行動補正は追加）
        base_value = self._value_model.predict(state_features)
        
        # 行動による補正
        action_bonus = 0.0
        if self_action.slot0_action.move_or_pokemon == 'protect':
            action_bonus += 0.01
        if self_action.slot0_action.priority > 0:
            action_bonus += 0.005 * self_action.slot0_action.priority
        
        return max(0.0, min(1.0, base_value + action_bonus))
    
    def _battle_to_state_features(self, battle_state: Any):
        """
        Battle オブジェクトを StateFeatures に変換
        """
        try:
            from predictor.core.policy_value_learning import StateFeatures
            
            # 自分のアクティブ
            self_hp = []
            self_status = []
            self_boosts = []
            
            if hasattr(battle_state, 'active_pokemon'):
                for p in battle_state.active_pokemon[:2]:
                    if p:
                        self_hp.append(p.current_hp_fraction)
                        self_status.append(self._status_to_code(p.status) if p.status else 0)
                        self_boosts.append(dict(p.boosts) if hasattr(p, 'boosts') else {})
                    else:
                        self_hp.append(0.0)
                        self_status.append(0)
                        self_boosts.append({})
            
            # 足りない場合は埋める
            while len(self_hp) < 2:
                self_hp.append(0.0)
                self_status.append(0)
                self_boosts.append({})
            
            # 相手のアクティブ
            opp_hp = []
            opp_status = []
            opp_boosts = []
            
            if hasattr(battle_state, 'opponent_active_pokemon'):
                for p in battle_state.opponent_active_pokemon[:2]:
                    if p:
                        opp_hp.append(p.current_hp_fraction)
                        opp_status.append(self._status_to_code(p.status) if p.status else 0)
                        opp_boosts.append(dict(p.boosts) if hasattr(p, 'boosts') else {})
                    else:
                        opp_hp.append(0.0)
                        opp_status.append(0)
                        opp_boosts.append({})
            
            while len(opp_hp) < 2:
                opp_hp.append(0.0)
                opp_status.append(0)
                opp_boosts.append({})
            
            # 控え数
            self_reserves = 0
            opp_reserves = 0
            if hasattr(battle_state, 'available_switches'):
                self_reserves = len(battle_state.available_switches[0]) if battle_state.available_switches else 0
            
            # フィールド情報
            weather = 0
            terrain = 0
            trick_room = 0
            tailwind_self = 0
            tailwind_opp = 0
            turn = getattr(battle_state, 'turn', 1)
            
            return StateFeatures(
                self_hp=self_hp,
                self_status=self_status,
                self_boosts=self_boosts,
                opp_hp=opp_hp,
                opp_status=opp_status,
                opp_boosts=opp_boosts,
                self_reserves=self_reserves,
                opp_reserves=opp_reserves,
                weather=weather,
                terrain=terrain,
                trick_room=trick_room,
                tailwind_self=tailwind_self,
                tailwind_opp=tailwind_opp,
                turn=turn,
            )
        except Exception as e:
            print(f"⚠️ _battle_to_state_features error: {e}")
            return None
    
    def _status_to_code(self, status) -> int:
        """状態異常をコードに変換"""
        if status is None:
            return 0
        status_map = {
            'brn': 1,
            'par': 2,
            'slp': 3,
            'frz': 4,
            'psn': 5,
            'tox': 6,
        }
        status_name = status.name.lower() if hasattr(status, 'name') else str(status).lower()
        return status_map.get(status_name, 0)
    
    def _calculate_order_distribution(self, battle_state: Any) -> List[OrderProbability]:
        """行動順分布（簡易版）"""
        # TODO: TurnOrderService.calculate_order_distribution() を呼ぶ
        return [OrderProbability(order_description="順序計算中", probability=1.0)]
    
    def _calculate_deltas(
        self,
        self_actions: List[JointAction],
        p_self: np.ndarray,
        payoff_matrix: np.ndarray,
        p_opp: np.ndarray,
    ) -> List[ActionDelta]:
        """代替手による勝率差"""
        expected_values = payoff_matrix @ p_opp
        best_value = np.max(expected_values)
        
        deltas = []
        for i, action in enumerate(self_actions):
            delta = expected_values[i] - best_value
            if abs(delta) > 0.01:  # 1%以上の差があるもの
                deltas.append(ActionDelta(
                    action=action,
                    win_delta=float(delta),
                    rationale=f"この手なら勝率{delta*100:+.1f}%"
                ))
        
        deltas.sort(key=lambda x: abs(x.win_delta), reverse=True)
        return deltas
    
    def _generate_rationales(
        self,
        battle_state: Any,
        self_action_dist: List[ActionProbability],
        opp_action_dist: List[ActionProbability],
        win_prob: float,
    ) -> List[str]:
        """根拠アンカー生成"""
        rationales = []
        
        # 勝率に関するコメント
        if win_prob > 0.7:
            rationales.append("形勢有利")
        elif win_prob < 0.3:
            rationales.append("形勢不利")
        else:
            rationales.append("形勢互角")
        
        # トップ行動に関するコメント
        if self_action_dist:
            top_action = self_action_dist[0]
            if top_action.probability > 0.5:
                rationales.append(f"最有力: {top_action.action.slot0_action.move_or_pokemon}")
        
        # 相手のトップ行動
        if opp_action_dist:
            top_opp = opp_action_dist[0]
            if top_opp.probability > 0.3:
                rationales.append(f"相手警戒: {top_opp.action.slot0_action.move_or_pokemon}")
        
        return rationales
    
    def _empty_result(self) -> PredictResult:
        """空の結果"""
        return PredictResult(
            win_prob=0.5,
            self_action_dist=[],
            opp_action_dist=[],
            order_dist=[],
            deltas=[],
            rationales=["候補手なし"],
        )


# ============================================================================
# シングルトン
# ============================================================================

_prediction_engine: Optional[PredictionEngine] = None

def get_prediction_engine() -> PredictionEngine:
    """PredictionEngine のシングルトンを取得"""
    global _prediction_engine
    if _prediction_engine is None:
        _prediction_engine = PredictionEngine()
    return _prediction_engine
