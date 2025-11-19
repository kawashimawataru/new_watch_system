"""
HybridStrategist - Fast-Lane + Slow-Lane統合

2層処理アーキテクチャ:
1. Fast-Lane (LightGBM): 0.41ms即時応答
2. Slow-Lane (MCTS): バックグラウンドで精密計算

Usage:
    hybrid = HybridStrategist(
        fast_model_path="models/fast_lane.pkl",
        mcts_rollouts=1000
    )
    
    # 即時応答 (Fast-Lane)
    quick_result = hybrid.predict_quick(battle_state)
    
    # 精密計算 (Slow-Lane, 非同期)
    precise_result = await hybrid.predict_precise(battle_state)
"""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from predictor.core.models import ActionCandidate, BattleState
from predictor.player.fast_strategist import FastPrediction, FastStrategist
from predictor.player.monte_carlo_strategist import MonteCarloStrategist


@dataclass
class HybridPrediction:
    """
    Hybrid予測結果
    
    Attributes:
        p1_win_rate: P1の勝率 (0.0 ~ 1.0)
        recommended_action: 推奨行動
        confidence: 信頼度 (fast=低, slow=高)
        inference_time_ms: 推論時間
        source: 予測ソース ("fast" or "slow")
    """
    p1_win_rate: float
    recommended_action: Optional[ActionCandidate]
    confidence: float
    inference_time_ms: float
    source: str  # "fast" or "slow"


class HybridStrategist:
    """
    Fast-Lane + Slow-Lane統合戦略エンジン
    
    アーキテクチャ:
    - Fast-Lane: LightGBM勝率推定 (0.41ms)
    - Slow-Lane: MCTS精密計算 (10~100ms)
    
    フロー:
    1. predict_quick(): Fast-Laneで即座に応答
    2. predict_precise(): Slow-Laneで精密計算 (非同期)
    3. UI: Fast結果を即座に表示 → Slow結果で更新
    """
    
    def __init__(
        self,
        fast_model_path: Path | str,
        mcts_rollouts: int = 1000,
        mcts_max_turns: int = 50
    ):
        """
        Args:
            fast_model_path: Fast-Laneモデルパス
            mcts_rollouts: MCTS rollout回数 (デフォルト: 1000)
            mcts_max_turns: MCTS最大ターン数 (デフォルト: 50)
        """
        # Fast-Lane初期化
        self.fast_strategist = FastStrategist.load(Path(fast_model_path))
        
        # Slow-Lane初期化
        self.mcts_strategist = MonteCarloStrategist(
            n_rollouts=mcts_rollouts,
            max_turns=mcts_max_turns
        )
        
        self.mcts_rollouts = mcts_rollouts
        self.mcts_max_turns = mcts_max_turns
    
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
            source="slow"
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
            source="slow"
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
        
        # P1 (player_a) の勝率を返す
        p1_win_rate = result.get("player_a_win_rate", 0.0)
        optimal_action = result.get("optimal_action")
        
        return {
            "win_rate": p1_win_rate,
            "action": optimal_action
        }
    
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
        return {
            "fast_features": len(self.fast_strategist.feature_names),
            "mcts_rollouts": self.mcts_rollouts,
            "mcts_max_turns": self.mcts_max_turns,
            "fast_confidence": 0.6,
            "slow_confidence": 0.9,
        }


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
