"""
HybridStrategist - Fast-Lane + Slow-Lane統合

3層処理アーキテクチャ:
1. Fast-Lane (LightGBM): 0.41ms即時応答
2. Slow-Lane (MCTS): バックグラウンドで精密計算
3. AlphaZero-Lane (Policy/Value NN + MCTS): 最高精度探索

Usage:
    hybrid = HybridStrategist(
        fast_model_path="models/fast_lane.pkl",
        mcts_rollouts=1000,
        use_alphazero=True,  # AlphaZero統合
        alphazero_model_path="models/policy_value.pt"
    )
    
    # 即時応答 (Fast-Lane)
    quick_result = hybrid.predict_quick(battle_state)
    
    # 精密計算 (Slow-Lane, 非同期)
    precise_result = await hybrid.predict_precise(battle_state)
    
    # 最高精度 (AlphaZero-Lane)
    ultimate_result = await hybrid.predict_ultimate(battle_state)
"""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from predictor.core.models import ActionCandidate, BattleState
from predictor.player.fast_strategist import FastPrediction, FastStrategist
from predictor.player.monte_carlo_strategist import MonteCarloStrategist

# Phase 2: AlphaZero統合 (オプショナル)
try:
    from predictor.player.alphazero_strategist import AlphaZeroStrategist
    ALPHAZERO_AVAILABLE = True
except ImportError:
    ALPHAZERO_AVAILABLE = False
    AlphaZeroStrategist = None


@dataclass
class HybridPrediction:
    """
    Hybrid予測結果
    
    Attributes:
        p1_win_rate: P1の勝率 (0.0 ~ 1.0)
        recommended_action: 推奨行動
        confidence: 信頼度 (fast=低, slow=中, alphazero=高)
        inference_time_ms: 推論時間
        source: 予測ソース ("fast" | "slow" | "alphazero")
        policy_probs: Policy確率分布 (AlphaZeroのみ)
        value_estimate: Value評価値 (AlphaZeroのみ)
    """
    p1_win_rate: float
    recommended_action: Optional[ActionCandidate]
    confidence: float
    inference_time_ms: float
    source: str  # "fast" | "slow" | "alphazero"
    policy_probs: Optional[Dict] = None
    value_estimate: Optional[float] = None
    explanation: Optional[str] = None
    alternatives: Optional[List[Dict[str, Any]]] = None


class HybridStrategist:
    """
    Fast-Lane + Slow-Lane + AlphaZero統合戦略エンジン
    
    アーキテクチャ:
    - Fast-Lane: LightGBM勝率推定 (0.41ms) - 即時フィードバック
    - Slow-Lane: Pure MCTS精密計算 (10~100ms) - 中精度探索
    - AlphaZero-Lane: Policy/Value NN + MCTS (50~200ms) - 最高精度探索
    
    フロー:
    1. predict_quick(): Fast-Laneで即座に応答
    2. predict_precise(): Slow-Laneで中精度計算 (非同期)
    3. predict_ultimate(): AlphaZero-Laneで最高精度計算 (非同期)
    4. UI: Fast → Slow → AlphaZero の順に結果を更新
    """
    
    def __init__(
        self,
        fast_model_path: Path | str,
        mcts_rollouts: int = 1000,
        mcts_max_turns: int = 50,
        use_alphazero: bool = False,
        alphazero_model_path: Optional[Path | str] = None,
        alphazero_rollouts: int = 100
    ):
        """
        Args:
            fast_model_path: Fast-Laneモデルパス
            mcts_rollouts: Pure MCTS rollout回数 (デフォルト: 1000)
            mcts_max_turns: MCTS最大ターン数 (デフォルト: 50)
            use_alphazero: AlphaZero統合を有効化するか
            alphazero_model_path: AlphaZero Policy/Valueモデルパス
            alphazero_rollouts: AlphaZero MCTS rollout回数 (デフォルト: 100)
        """
        # Fast-Lane初期化
        self.fast_strategist = FastStrategist.load(Path(fast_model_path))
        
        # Slow-Lane初期化 (Pure MCTS)
        self.mcts_strategist = MonteCarloStrategist(
            n_rollouts=mcts_rollouts,
            max_turns=mcts_max_turns
        )
        
        # AlphaZero-Lane初期化 (オプション)
        self.use_alphazero = use_alphazero and ALPHAZERO_AVAILABLE
        self.alphazero_strategist = None
        
        if self.use_alphazero:
            if not ALPHAZERO_AVAILABLE:
                print("⚠️  AlphaZeroStrategist not available, falling back to Pure MCTS")
                self.use_alphazero = False
            else:
                try:
                    self.alphazero_strategist = AlphaZeroStrategist(
                        policy_value_model_path=Path(alphazero_model_path) if alphazero_model_path else None,
                        mcts_rollouts=alphazero_rollouts,
                        use_bc_pretraining=True
                    )
                    print("✅ AlphaZeroStrategist initialized")
                except Exception as e:
                    print(f"⚠️  AlphaZero initialization failed: {e}, using Pure MCTS")
                    self.use_alphazero = False
        
        self.mcts_rollouts = mcts_rollouts
        self.mcts_max_turns = mcts_max_turns
        self.alphazero_rollouts = alphazero_rollouts
    
    def predict_quick(
        self,
        battle_state: BattleState
    ) -> HybridPrediction:
        """
        Fast-Laneで即時応答 (目標: < 1ms)
        
        Args:
            battle_state: 現在の対戦状態
            
        Returns:
            HybridPrediction (source="fast")
        """
        start_time = time.perf_counter()
        
        # Fast-Lane推論
        fast_result = self.fast_strategist.predict(battle_state)
        
        # 推奨行動の選択 (Phase 1では簡易実装)
        recommended_action = self._select_quick_action(
            battle_state,
            fast_result.p1_win_rate
        )
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        return HybridPrediction(
            p1_win_rate=fast_result.p1_win_rate,
            recommended_action=recommended_action,
            confidence=0.6,  # Fast-Laneは低信頼度
            inference_time_ms=elapsed_ms,
            source="fast"
        )
    
    async def predict_precise(
        self,
        battle_state: BattleState
    ) -> HybridPrediction:
        """
        Slow-Laneで精密計算 (非同期, 目標: < 100ms)
        
        Args:
            battle_state: 現在の対戦状態
            
        Returns:
            HybridPrediction (source="slow")
        """
        start_time = time.perf_counter()
        
        # MCTS計算 (asyncio.to_threadでブロッキング処理を非同期化)
        loop = asyncio.get_event_loop()
        mcts_result = await loop.run_in_executor(
            None,
            self._run_mcts,
            battle_state
        )
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        return HybridPrediction(
            p1_win_rate=mcts_result["win_rate"],
            recommended_action=mcts_result["action"],
            confidence=0.9,  # Slow-Laneは高信頼度
            inference_time_ms=elapsed_ms,
            source="slow",
            explanation=mcts_result.get("explanation"),
            alternatives=mcts_result.get("alternatives")
        )
    
    async def predict_ultimate(
        self,
        battle_state: BattleState
    ) -> HybridPrediction:
        """
        AlphaZero-Laneで最高精度計算 (非同期, 目標: < 200ms)
        
        Policy/Value Network + MCTS の組み合わせで、
        Pure MCTSよりも少ないrollouts数で高精度を実現。
        
        Args:
            battle_state: 現在の対戦状態
            
        Returns:
            HybridPrediction (source="alphazero")
        """
        if not self.use_alphazero:
            # AlphaZero無効時はSlow-Laneにフォールバック
            result = await self.predict_precise(battle_state)
            result.source = "slow(fallback)"
            return result
        
        start_time = time.perf_counter()
        
        # AlphaZero計算 (asyncio.to_threadで非同期化)
        loop = asyncio.get_event_loop()
        az_result = await loop.run_in_executor(
            None,
            self._run_alphazero,
            battle_state
        )
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        return HybridPrediction(
            p1_win_rate=az_result["p1_win_rate"],
            recommended_action=az_result["recommended_action"],
            confidence=0.95,  # AlphaZero-Laneは最高信頼度
            inference_time_ms=elapsed_ms,
            source="alphazero",
            policy_probs=az_result.get("policy_probs"),
            value_estimate=az_result.get("value_estimate")
        )
    
    def predict_both(
        self,
        battle_state: BattleState
    ) -> Tuple[HybridPrediction, HybridPrediction]:
        """
        Fast-Lane + Slow-Laneの両方を実行 (同期版)
        
        テスト用途。本番UIでは predict_quick() → predict_precise() を使用。
        
        Args:
            battle_state: 現在の対戦状態
            
        Returns:
            (fast_result, slow_result)
        """
        # Fast-Lane
        fast_result = self.predict_quick(battle_state)
        
        # Slow-Lane (同期実行)
        start_time = time.perf_counter()
        mcts_result = self._run_mcts(battle_state)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        slow_result = HybridPrediction(
            p1_win_rate=mcts_result["win_rate"],
            recommended_action=mcts_result["action"],
            confidence=0.9,
            inference_time_ms=elapsed_ms,
            source="slow",
            explanation=mcts_result.get("explanation"),
            alternatives=mcts_result.get("alternatives")
        )
        
        return fast_result, slow_result
    
    def _run_mcts(self, battle_state: BattleState) -> Dict:
        """
        MCTS計算を実行 (ブロッキング)
        
        Args:
            battle_state: 対戦状態
            
        Returns:
            {"win_rate": float, "action": ActionCandidate}
        """
        result = self.mcts_strategist.predict_win_rate(battle_state)
        
        p1_win_rate = result.get("player_a_win_rate", 0.0)
        optimal_action = result.get("optimal_action")
        action_win_rates = result.get("action_win_rates", {})
        legal_actions = result.get("legal_actions", [])
        
        # 説明文と代替案を生成
        explanation = f"Win rate: {p1_win_rate:.1%}"
        alternatives = []
        
        # アクションごとの勝率をリスト化
        for action_idx, rate in action_win_rates.items():
            description = f"Action {action_idx}"
            if 0 <= action_idx < len(legal_actions):
                action = legal_actions[action_idx]
                # TurnAction の内容を文字列化
                acts_str = []
                # player_a_actions は list[Action]
                # Action は dataclass だが、辞書ではなくオブジェクトとして返ってくる可能性がある
                # MonteCarloStrategist は同じプロセス内ならオブジェクト
                for act in action.player_a_actions:
                    if act.type == "move":
                        acts_str.append(f"{act.move_name} (slot {act.pokemon_slot}->{act.target_slot})")
                    elif act.type == "switch":
                        acts_str.append(f"Switch to {act.switch_to}")
                    elif act.type == "terastallize":
                        acts_str.append(f"Tera {act.tera_type}")
                description = ", ".join(acts_str)

            alternatives.append({
                "action_idx": action_idx,
                "win_rate": rate,
                "description": description
            })
            
        # ソート
        alternatives.sort(key=lambda x: x["win_rate"], reverse=True)
        
        if optimal_action:
             # TurnAction の内容を文字列で説明
             acts_str = []
             for act in optimal_action.player_a_actions:
                 if act.type == "move":
                     acts_str.append(f"{act.move_name} (slot {act.pokemon_slot}->{act.target_slot})")
                 elif act.type == "switch":
                     acts_str.append(f"Switch to {act.switch_to}")
             
             explanation = f"Selected: {', '.join(acts_str)}. Win rate: {p1_win_rate:.1%}."
        
        return {
            "win_rate": p1_win_rate,
            "action": optimal_action,
            "explanation": explanation,
            "alternatives": alternatives
        }
    
    def _run_alphazero(self, battle_state: BattleState) -> Dict:
        """
        AlphaZero計算を実行 (ブロッキング)
        
        Args:
            battle_state: 対戦状態
            
        Returns:
            {
                "p1_win_rate": float,
                "recommended_action": ActionCandidate,
                "policy_probs": Dict,
                "value_estimate": float
            }
        """
        if not self.alphazero_strategist:
            # フォールバック: Pure MCTS
            return self._run_mcts(battle_state)
        
        # Phase 1: フォールバックモードで実行
        result = self.alphazero_strategist.predict(
            battle_state,
            use_fallback=True  # Phase 1ではPure MCTSを使用
        )
        
        return result
    
    def _select_quick_action(
        self,
        battle_state: BattleState,
        win_rate: float
    ) -> Optional[ActionCandidate]:
        """
        Fast-Laneの勝率に基づいて簡易的に行動選択
        
        Phase 1実装: legal_actionsの先頭を返す
        Phase 2実装: 勝率を考慮した探索
        
        Args:
            battle_state: 対戦状態
            win_rate: Fast-Laneの予測勝率
            
        Returns:
            推奨行動 (またはNone)
        """
        # Phase 1: 簡易実装
        legal_actions = battle_state.legal_actions.get("A", [])
        
        if not legal_actions:
            return None
        
        # 最初の行動を返す (Phase 2で改善予定)
        return legal_actions[0]
    
    def get_stats(self) -> Dict:
        """
        Strategistの統計情報
        
        Returns:
            {"fast_features": int, "mcts_rollouts": int, ...}
        """
        stats = {
            "fast_features": len(self.fast_strategist.feature_names),
            "mcts_rollouts": self.mcts_rollouts,
            "mcts_max_turns": self.mcts_max_turns,
            "fast_confidence": 0.6,
            "slow_confidence": 0.9,
            "use_alphazero": self.use_alphazero,
        }
        
        if self.use_alphazero:
            stats["alphazero_rollouts"] = self.alphazero_rollouts
            stats["alphazero_confidence"] = 0.95
        
        return stats


class StreamingPredictor:
    """
    ストリーミング予測 (UI連携用)
    
    Fast結果を即座に返し、Slow結果をコールバックで通知。
    """
    
    def __init__(self, hybrid: HybridStrategist):
        self.hybrid = hybrid
    
    async def predict_stream(
        self,
        battle_state: BattleState,
        fast_callback=None,
        slow_callback=None
    ):
        """
        ストリーミング予測
        
        Args:
            battle_state: 対戦状態
            fast_callback: Fast結果のコールバック
            slow_callback: Slow結果のコールバック
        """
        # Fast-Lane (即座に実行)
        fast_result = self.hybrid.predict_quick(battle_state)
        if fast_callback:
            fast_callback(fast_result)
        
        # Slow-Lane (非同期で実行)
        slow_result = await self.hybrid.predict_precise(battle_state)
        if slow_callback:
            slow_callback(slow_result)
        
        return fast_result, slow_result
