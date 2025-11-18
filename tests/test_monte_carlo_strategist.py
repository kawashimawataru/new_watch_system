"""
Tests for Monte Carlo Strategist

MCTS Engineの動作確認とパフォーマンステスト。

実行方法:
    pytest tests/test_monte_carlo_strategist.py -v
    pytest tests/test_monte_carlo_strategist.py -v -s  # 詳細ログ付き
"""

import pytest
from unittest.mock import Mock, patch

from predictor.player.monte_carlo_strategist import (
    MonteCarloStrategist,
    Action,
    TurnAction
)
from predictor.core.models import (
    BattleState,
    PlayerState,
    PokemonBattleState
)


@pytest.fixture
def sample_battle_state():
    """サンプルのバトル状態を作成"""
    player_a = PlayerState(
        name="Player A",
        active=[
            PokemonBattleState(name="Gholdengo", hp_fraction=1.0, slot=0, moves=["Make It Rain", "Shadow Ball"]),
            PokemonBattleState(name="Rillaboom", hp_fraction=1.0, slot=1, moves=["Grassy Glide", "Fake Out"])
        ],
        reserves=["Incineroar", "Dragonite"]
    )
    
    player_b = PlayerState(
        name="Player B",
        active=[
            PokemonBattleState(name="Dragonite", hp_fraction=1.0, slot=2, moves=["Dragon Claw", "Extreme Speed"]),
            PokemonBattleState(name="Incineroar", hp_fraction=1.0, slot=3, moves=["Fake Out", "Flare Blitz"])
        ],
        reserves=["Rillaboom", "Gholdengo"]
    )
    
    state = BattleState(
        player_a=player_a,
        player_b=player_b,
        turn=1,
        legal_actions={}
    )
    return state


class TestMonteCarloStrategist:
    """MonteCarloStrategist のテスト"""
    
    def test_initialization(self):
        """初期化のテスト"""
        strategist = MonteCarloStrategist(n_rollouts=100)
        
        assert strategist.n_rollouts == 100
        assert strategist.max_turns == 50
        assert strategist.use_heuristic is True
        assert strategist.total_simulations == 0
    
    def test_initialization_with_seed(self):
        """乱数シード指定のテスト"""
        strategist = MonteCarloStrategist(n_rollouts=10, random_seed=42)
        
        assert strategist.n_rollouts == 10
    
    def test_predict_win_rate_basic(self, sample_battle_state):
        """基本的な勝率予測のテスト"""
        strategist = MonteCarloStrategist(n_rollouts=50)
        
        # TODO: モックを使ってシミュレーション結果を制御
        with patch.object(strategist, '_get_legal_actions') as mock_legal_actions:
            # 簡単な合法手を返す
            mock_legal_actions.return_value = [
                TurnAction(
                    player_a_actions=[
                        Action(type="move", pokemon_slot=0, move_name="Make It Rain", target_slot=2)
                    ],
                    player_b_actions=[]
                )
            ]
            
            with patch.object(strategist, '_simulate_battle') as mock_simulate:
                # 常にPlayer Aが勝つようにモック
                mock_simulate.return_value = ("player_a", 5)
                
                result = strategist.predict_win_rate(sample_battle_state)
                
                assert "player_a_win_rate" in result
                assert "player_b_win_rate" in result
                assert "optimal_action" in result
                assert result["player_a_win_rate"] == 1.0  # 全勝
                assert result["player_b_win_rate"] == 0.0
    
    def test_predict_win_rate_multiple_actions(self, sample_battle_state):
        """複数の行動がある場合のテスト"""
        strategist = MonteCarloStrategist(n_rollouts=100, random_seed=42)
        
        actions = [
            TurnAction(player_a_actions=[Action(type="move", pokemon_slot=0, move_name=f"move_{i}")], player_b_actions=[])
            for i in range(5)
        ]
        
        with patch.object(strategist, '_get_legal_actions') as mock_legal_actions:
            mock_legal_actions.return_value = actions
            
            with patch.object(strategist, '_simulate_battle') as mock_simulate:
                # 行動によって勝率を変える
                def simulate_side_effect(state, action):
                    action_idx = actions.index(action)
                    # Action 0は80%勝利、それ以外は50%
                    if action_idx == 0:
                        import random
                        winner = "player_a" if random.random() < 0.8 else "player_b"
                    else:
                        import random
                        winner = "player_a" if random.random() < 0.5 else "player_b"
                    return winner, 5
                
                mock_simulate.side_effect = simulate_side_effect
                
                result = strategist.predict_win_rate(sample_battle_state)
                
                # 最適手はAction 0のはず
                assert result["optimal_action"] == actions[0]
                assert result["optimal_action_win_rate"] >= 0.5
    
    def test_simulate_battle_max_turns(self, sample_battle_state):
        """最大ターン数制限のテスト"""
        strategist = MonteCarloStrategist(n_rollouts=10, max_turns=10)
        
        action = TurnAction(
            player_a_actions=[Action(type="move", pokemon_slot=0, move_name="tackle", target_slot=2)],
            player_b_actions=[]
        )
        
        # バトルが終了しないようにモック
        with patch.object(strategist, '_check_winner') as mock_winner:
            mock_winner.return_value = None  # 常に終了しない
            
            with patch.object(strategist, '_apply_action') as mock_apply:
                mock_apply.return_value = sample_battle_state
                
                with patch.object(strategist, '_get_legal_actions') as mock_legal:
                    mock_legal.return_value = [action]
                    
                    winner, turns = strategist._simulate_battle(sample_battle_state, action)
                    
                    # 最大ターン数に達したはず
                    assert turns == strategist.max_turns
    
    def test_get_legal_actions_returns_list(self, sample_battle_state):
        """合法手の列挙のテスト"""
        strategist = MonteCarloStrategist()
        
        actions = strategist._get_legal_actions(sample_battle_state)
        
        assert isinstance(actions, list)
        assert len(actions) > 0
        assert all(isinstance(a, TurnAction) for a in actions)
    
    def test_check_winner(self, sample_battle_state):
        """勝敗判定のテスト"""
        strategist = MonteCarloStrategist()
        
        # TODO: 実際のバトル状態で勝敗判定
        winner = strategist._check_winner(sample_battle_state)
        
        # Phase 1ではNoneを返すダミー実装
        assert winner is None or winner in ["player_a", "player_b"]
    
    def test_evaluate_terminal_state_player_a_win(self, sample_battle_state):
        """終了状態の評価 (Player A勝利)"""
        strategist = MonteCarloStrategist()
        
        with patch.object(strategist, '_check_winner') as mock_winner:
            mock_winner.return_value = "player_a"
            
            result = strategist._evaluate_terminal_state(sample_battle_state)
            
            assert result["player_a_win_rate"] == 1.0
            assert result["player_b_win_rate"] == 0.0
            assert result["optimal_action"] is None
    
    def test_evaluate_terminal_state_player_b_win(self, sample_battle_state):
        """終了状態の評価 (Player B勝利)"""
        strategist = MonteCarloStrategist()
        
        with patch.object(strategist, '_check_winner') as mock_winner:
            mock_winner.return_value = "player_b"
            
            result = strategist._evaluate_terminal_state(sample_battle_state)
            
            assert result["player_a_win_rate"] == 0.0
            assert result["player_b_win_rate"] == 1.0
    
    def test_get_statistics(self):
        """統計情報の取得テスト"""
        strategist = MonteCarloStrategist()
        
        stats = strategist.get_statistics()
        
        assert "total_simulations" in stats
        assert "cache_hits" in stats
        assert "cache_hit_rate" in stats
        assert stats["total_simulations"] == 0  # まだシミュレーションしていない


class TestPerformance:
    """パフォーマンステスト"""
    
    @pytest.mark.slow
    def test_1000_rollouts_performance(self, sample_battle_state):
        """1000 rollouts のパフォーマンステスト"""
        import time
        
        strategist = MonteCarloStrategist(n_rollouts=1000)
        
        with patch.object(strategist, '_get_legal_actions') as mock_legal_actions:
            mock_legal_actions.return_value = [
                TurnAction(player_a_actions=[Action(type="move", pokemon_slot=0, move_name="tackle")], player_b_actions=[])
            ]
            
            with patch.object(strategist, '_simulate_battle') as mock_simulate:
                mock_simulate.return_value = ("player_a", 5)
                
                start_time = time.time()
                result = strategist.predict_win_rate(sample_battle_state)
                elapsed = time.time() - start_time
                
                print(f"\n⏱️  1000 rollouts completed in {elapsed:.2f}s")
                print(f"📊 Average: {elapsed / 1000 * 1000:.2f}ms per rollout")
                
                # 目標: 2-5秒以内に完了
                assert elapsed < 10.0, f"Too slow: {elapsed:.2f}s (target: < 10s)"
                assert result["total_rollouts"] == 1000
    
    @pytest.mark.slow
    def test_memory_usage(self, sample_battle_state):
        """メモリ使用量のテスト"""
        import tracemalloc
        
        tracemalloc.start()
        
        strategist = MonteCarloStrategist(n_rollouts=100)
        
        with patch.object(strategist, '_get_legal_actions') as mock_legal_actions:
            mock_legal_actions.return_value = [
                TurnAction(player_a_actions=[Action(type="move", pokemon_slot=0, move_name="tackle")], player_b_actions=[])
            ]
            
            with patch.object(strategist, '_simulate_battle') as mock_simulate:
                mock_simulate.return_value = ("player_a", 5)
                
                result = strategist.predict_win_rate(sample_battle_state)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"\n💾 Memory usage: {current / 1024 / 1024:.2f} MB (peak: {peak / 1024 / 1024:.2f} MB)")
        
        # 目標: 100MB以内
        assert peak < 100 * 1024 * 1024, f"Too much memory: {peak / 1024 / 1024:.2f} MB"


class TestAction:
    """Action クラスのテスト"""
    
    def test_action_creation_move(self):
        """技を使う行動の作成"""
        action = Action(
            type="move",
            pokemon_slot=0,
            move_name="Make It Rain",
            target_slot=2
        )
        
        assert action.type == "move"
        assert action.pokemon_slot == 0
        assert action.move_name == "Make It Rain"
        assert action.target_slot == 2
    
    def test_action_creation_switch(self):
        """交代の行動の作成"""
        action = Action(
            type="switch",
            pokemon_slot=0,
            switch_to="Rillaboom"
        )
        
        assert action.type == "switch"
        assert action.switch_to == "Rillaboom"
    
    def test_turn_action_creation(self):
        """TurnActionの作成"""
        turn_action = TurnAction(
            player_a_actions=[
                Action(type="move", pokemon_slot=0, move_name="tackle", target_slot=2),
                Action(type="move", pokemon_slot=1, move_name="protect", target_slot=1)
            ],
            player_b_actions=[
                Action(type="move", pokemon_slot=2, move_name="tackle", target_slot=0),
                Action(type="move", pokemon_slot=3, move_name="tackle", target_slot=1)
            ]
        )
        
        assert len(turn_action.player_a_actions) == 2
        assert len(turn_action.player_b_actions) == 2


class TestIntegration:
    """統合テスト: 実際のBattleStateを使った動作確認"""
    
    def test_full_prediction_with_real_state(self, sample_battle_state):
        """実際のBattleStateで勝率予測"""
        strategist = MonteCarloStrategist(n_rollouts=50, random_seed=42)
        
        result = strategist.predict_win_rate(sample_battle_state, verbose=False)
        
        assert "player_a_win_rate" in result
        assert "player_b_win_rate" in result
        assert "optimal_action" in result
        assert 0.0 <= result["player_a_win_rate"] <= 1.0
        assert 0.0 <= result["player_b_win_rate"] <= 1.0
        assert abs(result["player_a_win_rate"] + result["player_b_win_rate"] - 1.0) < 0.01
    
    def test_simulate_battle_completes(self, sample_battle_state):
        """バトルシミュレーションが完了する"""
        strategist = MonteCarloStrategist(n_rollouts=10, max_turns=20)
        
        actions = strategist._get_legal_actions(sample_battle_state)
        assert len(actions) > 0
        
        winner, turns = strategist._simulate_battle(sample_battle_state, actions[0])
        
        assert winner in ["player_a", "player_b"]
        assert 1 <= turns <= 20
    
    def test_check_winner_detects_victory(self, sample_battle_state):
        """勝敗判定の動作確認"""
        strategist = MonteCarloStrategist()
        
        # 初期状態は継続中
        winner = strategist._check_winner(sample_battle_state)
        assert winner is None
        
        # Player Bを全滅させる
        for pokemon in sample_battle_state.player_b.active:
            pokemon.hp_fraction = 0.0
        sample_battle_state.player_b.reserves = []
        
        winner = strategist._check_winner(sample_battle_state)
        assert winner == "player_a"
    
    def test_apply_damage_reduces_hp(self, sample_battle_state):
        """ダメージ適用でHPが減る"""
        strategist = MonteCarloStrategist()
        
        initial_hp = sample_battle_state.player_b.active[0].hp_fraction
        strategist._apply_damage(sample_battle_state, 2, 0.3)
        
        assert sample_battle_state.player_b.active[0].hp_fraction < initial_hp
        assert sample_battle_state.player_b.active[0].hp_fraction == initial_hp - 0.3
    
    def test_remove_fainted_removes_zero_hp(self, sample_battle_state):
        """倒れたポケモンが除外される"""
        strategist = MonteCarloStrategist()
        
        # Player Aの1体目を倒す
        sample_battle_state.player_a.active[0].hp_fraction = 0.0
        
        strategist._remove_fainted(sample_battle_state)
        
        assert len(sample_battle_state.player_a.active) == 1
        assert sample_battle_state.player_a.active[0].name == "Rillaboom"
    
    def test_evaluate_heuristic_returns_score(self, sample_battle_state):
        """ヒューリスティック評価がスコアを返す"""
        strategist = MonteCarloStrategist()
        
        score = strategist._evaluate_heuristic(sample_battle_state)
        
        assert isinstance(score, float)
        # 互角な盤面なので、スコアは0に近いはず
        assert -5.0 <= score <= 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
