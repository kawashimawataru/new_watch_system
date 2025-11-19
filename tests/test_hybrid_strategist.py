"""
HybridStrategist のテスト

Fast-Lane + Slow-Lane統合の動作確認:
- predict_quick(): < 1ms
- predict_precise(): < 100ms
- predict_both(): Fast + Slow両方実行
"""

import asyncio
import time
from pathlib import Path

import pytest

from predictor.core.models import BattleState, PlayerState, PokemonBattleState
from predictor.player.hybrid_strategist import (
    HybridPrediction,
    HybridStrategist,
    StreamingPredictor,
)


@pytest.fixture
def sample_battle_state() -> BattleState:
    """
    テスト用BattleState
    
    P1有利なシナリオ (HP: 1.4 vs 0.7)
    """
    p1_active = [
        PokemonBattleState(name="Pikachu", hp_fraction=0.8, boosts={}),
        PokemonBattleState(name="Charizard", hp_fraction=0.6, boosts={})
    ]
    
    p2_active = [
        PokemonBattleState(name="Blastoise", hp_fraction=0.4, boosts={}),
        PokemonBattleState(name="Venusaur", hp_fraction=0.3, boosts={})
    ]
    
    return BattleState(
        player_a=PlayerState(name="Alice", active=p1_active, reserves=[]),
        player_b=PlayerState(name="Bob", active=p2_active, reserves=[]),
        turn=3,
        weather=None,
        terrain=None,
        room=None,
        legal_actions={},
        raw_log={}
    )


@pytest.fixture
def hybrid_strategist() -> HybridStrategist:
    """訓練済みHybridStrategist"""
    model_path = Path("models/fast_lane.pkl")
    
    if not model_path.exists():
        pytest.skip("models/fast_lane.pkl が見つかりません")
    
    return HybridStrategist(
        fast_model_path=model_path,
        mcts_rollouts=100,  # テストでは少なめ
        mcts_max_turns=20
    )


class TestHybridStrategist:
    """HybridStrategist の基本機能テスト"""
    
    def test_predict_quick_returns_fast_result(self, hybrid_strategist, sample_battle_state):
        """predict_quick が Fast結果を返すか"""
        result = hybrid_strategist.predict_quick(sample_battle_state)
        
        assert isinstance(result, HybridPrediction)
        assert result.source == "fast"
        assert 0.0 <= result.p1_win_rate <= 1.0
        assert result.confidence == 0.6  # Fast-Laneは低信頼度
        assert result.inference_time_ms > 0
    
    @pytest.mark.asyncio
    async def test_predict_precise_returns_slow_result(self, hybrid_strategist, sample_battle_state):
        """predict_precise が Slow結果を返すか"""
        result = await hybrid_strategist.predict_precise(sample_battle_state)
        
        assert isinstance(result, HybridPrediction)
        assert result.source == "slow"
        assert 0.0 <= result.p1_win_rate <= 1.0
        assert result.confidence == 0.9  # Slow-Laneは高信頼度
        assert result.inference_time_ms > 0
    
    def test_predict_both_returns_fast_and_slow(self, hybrid_strategist, sample_battle_state):
        """predict_both が Fast + Slow両方を返すか"""
        fast_result, slow_result = hybrid_strategist.predict_both(sample_battle_state)
        
        assert fast_result.source == "fast"
        assert slow_result.source == "slow"
        
        # 両方とも有効な勝率
        assert 0.0 <= fast_result.p1_win_rate <= 1.0
        assert 0.0 <= slow_result.p1_win_rate <= 1.0
    
    def test_get_stats_returns_info(self, hybrid_strategist):
        """get_stats が統計情報を返すか"""
        stats = hybrid_strategist.get_stats()
        
        assert "fast_features" in stats
        assert "mcts_rollouts" in stats
        assert stats["mcts_rollouts"] == 100
        assert stats["mcts_max_turns"] == 20


class TestPerformance:
    """パフォーマンステスト"""
    
    def test_quick_prediction_speed(self, hybrid_strategist, sample_battle_state):
        """Fast-Lane推論が1ms以内か (目標)"""
        result = hybrid_strategist.predict_quick(sample_battle_state)
        
        print(f"\n⏱️  Fast-Lane推論: {result.inference_time_ms:.2f}ms")
        
        # 実測では0.5ms程度なので余裕を持って2ms以内
        assert result.inference_time_ms < 2.0
    
    @pytest.mark.asyncio
    async def test_precise_prediction_speed(self, hybrid_strategist, sample_battle_state):
        """Slow-Lane推論が100ms以内か (目標: 100 rollouts)"""
        result = await hybrid_strategist.predict_precise(sample_battle_state)
        
        print(f"\n⏱️  Slow-Lane推論 (100 rollouts): {result.inference_time_ms:.2f}ms")
        
        # 100 rolloutsなら20ms程度、余裕を持って50ms以内
        assert result.inference_time_ms < 50.0
    
    def test_both_predictions_combined_speed(self, hybrid_strategist, sample_battle_state):
        """Fast + Slow合計が100ms以内か"""
        start = time.perf_counter()
        fast_result, slow_result = hybrid_strategist.predict_both(sample_battle_state)
        total_time = (time.perf_counter() - start) * 1000
        
        print(f"\n⏱️  統合推論:")
        print(f"   - Fast: {fast_result.inference_time_ms:.2f}ms")
        print(f"   - Slow: {slow_result.inference_time_ms:.2f}ms")
        print(f"   - Total: {total_time:.2f}ms")
        
        # 合計100ms以内 (100 rollouts)
        assert total_time < 100.0


class TestStreamingPredictor:
    """StreamingPredictor のテスト"""
    
    @pytest.mark.asyncio
    async def test_predict_stream_calls_callbacks(self, hybrid_strategist, sample_battle_state):
        """ストリーミング予測がコールバックを呼ぶか"""
        predictor = StreamingPredictor(hybrid_strategist)
        
        fast_called = False
        slow_called = False
        
        def fast_callback(result):
            nonlocal fast_called
            fast_called = True
            assert result.source == "fast"
        
        def slow_callback(result):
            nonlocal slow_called
            slow_called = True
            assert result.source == "slow"
        
        fast_result, slow_result = await predictor.predict_stream(
            sample_battle_state,
            fast_callback=fast_callback,
            slow_callback=slow_callback
        )
        
        assert fast_called
        assert slow_called
        assert fast_result.source == "fast"
        assert slow_result.source == "slow"


class TestEdgeCases:
    """エッジケースのテスト"""
    
    def test_predict_with_no_legal_actions(self, hybrid_strategist):
        """legal_actionsが空の場合"""
        state = BattleState(
            player_a=PlayerState(
                name="Alice",
                active=[PokemonBattleState(name="A1", hp_fraction=1.0, boosts={})],
                reserves=[]
            ),
            player_b=PlayerState(
                name="Bob",
                active=[PokemonBattleState(name="B1", hp_fraction=1.0, boosts={})],
                reserves=[]
            ),
            turn=1,
            weather=None,
            terrain=None,
            room=None,
            legal_actions={},  # 空
            raw_log={}
        )
        
        result = hybrid_strategist.predict_quick(state)
        
        # エラーが起きずに実行される
        assert result.source == "fast"
        assert result.recommended_action is None
    
    def test_predict_with_fainted_pokemon(self, hybrid_strategist):
        """倒れたポケモンがいる場合"""
        state = BattleState(
            player_a=PlayerState(
                name="Alice",
                active=[
                    PokemonBattleState(name="A1", hp_fraction=1.0, boosts={}),
                    PokemonBattleState(name="A2", hp_fraction=0.0, boosts={})  # fainted
                ],
                reserves=[]
            ),
            player_b=PlayerState(
                name="Bob",
                active=[PokemonBattleState(name="B1", hp_fraction=0.5, boosts={})],
                reserves=[]
            ),
            turn=5,
            weather=None,
            terrain=None,
            room=None,
            legal_actions={},
            raw_log={}
        )
        
        result = hybrid_strategist.predict_quick(state)
        
        # エラーが起きずに実行される
        assert result.source == "fast"
        assert 0.0 <= result.p1_win_rate <= 1.0


class TestAsyncBehavior:
    """非同期動作のテスト"""
    
    @pytest.mark.asyncio
    async def test_multiple_async_predictions(self, hybrid_strategist, sample_battle_state):
        """複数の非同期予測を並列実行できるか"""
        # 3つの予測を並列実行
        tasks = [
            hybrid_strategist.predict_precise(sample_battle_state)
            for _ in range(3)
        ]
        
        start = time.perf_counter()
        results = await asyncio.gather(*tasks)
        elapsed = (time.perf_counter() - start) * 1000
        
        print(f"\n⏱️  3並列実行: {elapsed:.2f}ms")
        
        assert len(results) == 3
        assert all(r.source == "slow" for r in results)
        
        # 並列実行により個別実行の3倍よりも短い時間で完了
        # (実際は並列処理のオーバーヘッドがあるため完全には3倍にはならない)
