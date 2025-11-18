"""
FeatureExtractor のテスト

Phase 1では基本的な特徴量抽出の動作確認:
- リプレイログからHP情報を抽出できるか
- ターン毎のスナップショットが正しく生成されるか
- DataFrame出力が正しいか
"""

import json
from pathlib import Path

import pytest

from predictor.player.feature_extractor import (
    BattleFeatures,
    FeatureExtractor,
    TurnSnapshot,
)


@pytest.fixture
def sample_replay() -> dict:
    """
    簡易リプレイデータ (3ターンの模擬対戦)
    
    シナリオ:
    - Turn 1: 両者フルHP
    - Turn 2: P1がダメージを受ける
    - Turn 3: P2のポケモンが1体倒れる → P1勝利
    """
    log = """
|player|p1|Alice|avatar1|1600
|player|p2|Bob|avatar2|1550
|start
|switch|p1a: Pikachu|Pikachu, L50|100/100
|switch|p1b: Charizard|Charizard, L50|100/100
|switch|p2a: Blastoise|Blastoise, L50|100/100
|switch|p2b: Venusaur|Venusaur, L50|100/100
|turn|1
|move|p1a: Pikachu|Thunderbolt|p2a: Blastoise
|-damage|p2a: Blastoise|70/100
|turn|2
|move|p2b: Venusaur|Solar Beam|p1a: Pikachu
|-damage|p1a: Pikachu|50/100
|-weather|SunnyDay
|turn|3
|move|p1b: Charizard|Flamethrower|p2b: Venusaur
|-damage|p2b: Venusaur|0/100
|faint|p2b: Venusaur
|win|Alice
"""
    return {
        "id": "test-replay-001",
        "rating": 1600,
        "log": log.strip()
    }


@pytest.fixture
def extractor() -> FeatureExtractor:
    """FeatureExtractor インスタンス"""
    return FeatureExtractor()


class TestFeatureExtractor:
    """FeatureExtractor の基本機能テスト"""
    
    def test_extract_from_replay_returns_list(self, extractor, sample_replay):
        """extract_from_replay が特徴量リストを返すか"""
        features = extractor.extract_from_replay(sample_replay)
        assert isinstance(features, list)
        assert len(features) > 0
        assert all(isinstance(f, BattleFeatures) for f in features)
    
    def test_extract_winner_p1(self, extractor, sample_replay):
        """勝者がP1として正しく認識されるか"""
        lines = sample_replay["log"].split("\n")
        winner = extractor._extract_winner(lines)
        assert winner == "p1"
    
    def test_parse_battle_log_creates_snapshots(self, extractor, sample_replay):
        """ログからスナップショットが生成されるか"""
        lines = sample_replay["log"].split("\n")
        winner = extractor._extract_winner(lines)
        snapshots = extractor._parse_battle_log(lines, winner)
        
        assert len(snapshots) >= 3  # 3ターン分
        assert all(isinstance(s, TurnSnapshot) for s in snapshots)
    
    def test_snapshot_turn_numbers(self, extractor, sample_replay):
        """ターン番号が正しく抽出されるか"""
        lines = sample_replay["log"].split("\n")
        winner = extractor._extract_winner(lines)
        snapshots = extractor._parse_battle_log(lines, winner)
        
        turns = [s.turn for s in snapshots]
        assert turns == [1, 2, 3]
    
    def test_hp_tracking(self, extractor, sample_replay):
        """HP情報が正しく追跡されるか"""
        lines = sample_replay["log"].split("\n")
        winner = extractor._extract_winner(lines)
        snapshots = extractor._parse_battle_log(lines, winner)
        
        # Turn 1: フルHP
        turn1 = snapshots[0]
        assert turn1.p1_hp.get("Pikachu", 0) == 1.0
        assert turn1.p2_hp.get("Blastoise", 0) == 0.7  # 70/100
        
        # Turn 2: Pikachuダメージ
        turn2 = snapshots[1]
        assert turn2.p1_hp.get("Pikachu", 0) == 0.5  # 50/100
    
    def test_fainted_tracking(self, extractor, sample_replay):
        """倒れたポケモンが正しく追跡されるか"""
        lines = sample_replay["log"].split("\n")
        winner = extractor._extract_winner(lines)
        snapshots = extractor._parse_battle_log(lines, winner)
        
        # Turn 3: Venusaur fainted
        turn3 = snapshots[2]
        assert turn3.p2_fainted == 1
        assert turn3.p1_fainted == 0
        assert turn3.p2_hp.get("Venusaur", 1.0) == 0.0
    
    def test_weather_tracking(self, extractor, sample_replay):
        """天候情報が正しく追跡されるか"""
        lines = sample_replay["log"].split("\n")
        winner = extractor._extract_winner(lines)
        snapshots = extractor._parse_battle_log(lines, winner)
        
        # Turn 2: SunnyDay発動
        turn2 = snapshots[1]
        assert turn2.weather == "SunnyDay"
    
    def test_snapshot_to_features(self, extractor):
        """スナップショットが特徴量に変換されるか"""
        snapshot = TurnSnapshot(
            turn=1,
            p1_active=["Pikachu"],
            p2_active=["Blastoise"],
            p1_hp={"Pikachu": 1.0, "Charizard": 1.0},
            p2_hp={"Blastoise": 0.7, "Venusaur": 1.0},
            p1_fainted=0,
            p2_fainted=0,
            weather="SunnyDay",
            terrain=None,
            trick_room=False,
            winner="p1"
        )
        
        features = extractor._snapshot_to_features(snapshot, "test-001", 1600)
        
        assert features.replay_id == "test-001"
        assert features.turn == 1
        assert features.rating == 1600
        assert features.p1_total_hp == 2.0
        assert features.p2_total_hp == 1.7
        assert features.hp_difference > 0  # P1有利
        assert features.has_weather == 1
        assert features.has_terrain == 0
        assert features.p1_win == 1


class TestBatchExtraction:
    """バッチ抽出機能のテスト"""
    
    def test_extract_batch_with_real_replay(self, extractor):
        """実際のリプレイファイルからバッチ抽出できるか"""
        # 実データを探す
        replay_dir = Path("data/replays")
        if not replay_dir.exists():
            pytest.skip("data/replays が存在しません")
        
        replay_files = list(replay_dir.glob("vgc_replays_*.json"))
        if not replay_files:
            pytest.skip("リプレイファイルが見つかりません")
        
        # 1ファイルのみテスト
        df = extractor.extract_batch([replay_files[0]], extract_every_n_turns=3)
        
        assert len(df) > 0
        assert "replay_id" in df.columns
        assert "p1_win" in df.columns
        assert "hp_difference" in df.columns
        
        # 数値型の確認
        assert df["p1_total_hp"].dtype in ["float64", "float32"]
        assert df["p1_win"].dtype in ["int64", "int32"]
    
    def test_extract_every_n_turns(self, extractor, sample_replay):
        """N ターン毎のサンプリングが機能するか"""
        # 全ターン抽出
        all_features = extractor.extract_from_replay(
            sample_replay,
            extract_every_n_turns=1
        )
        
        # 2ターン毎に抽出
        sampled_features = extractor.extract_from_replay(
            sample_replay,
            extract_every_n_turns=2
        )
        
        assert len(all_features) >= 3
        assert len(sampled_features) < len(all_features)


class TestEdgeCases:
    """エッジケースのテスト"""
    
    def test_empty_log(self, extractor):
        """空ログの処理"""
        replay = {"id": "empty", "rating": 1500, "log": ""}
        features = extractor.extract_from_replay(replay)
        assert features == []
    
    def test_no_winner(self, extractor):
        """勝者不明のリプレイ"""
        log = "|start\n|turn|1\n|turn|2"
        replay = {"id": "no-win", "rating": 1500, "log": log}
        features = extractor.extract_from_replay(replay)
        
        # 特徴量は生成されるが、p1_win = 0
        if features:
            assert all(f.p1_win == 0 for f in features)
    
    def test_malformed_hp_line(self, extractor):
        """不正な形式のHP情報"""
        log = """
|start
|switch|p1a: Pikachu|Pikachu, L50|100/100
|turn|1
|-damage|invalid_format
|turn|2
"""
        replay = {"id": "malformed", "rating": 1500, "log": log.strip()}
        
        # エラーが起きずに処理される
        features = extractor.extract_from_replay(replay)
        assert len(features) >= 1


class TestPerformance:
    """パフォーマンステスト"""
    
    def test_extraction_speed_single_replay(self, extractor):
        """単一リプレイの抽出速度 (目標: < 50ms)"""
        import time
        
        replay_dir = Path("data/replays")
        if not replay_dir.exists():
            pytest.skip("data/replays が存在しません")
        
        replay_files = list(replay_dir.glob("vgc_replays_*.json"))
        if not replay_files:
            pytest.skip("リプレイファイルが見つかりません")
        
        # 最初のリプレイを読み込み
        with open(replay_files[0], "r", encoding="utf-8") as f:
            replays = json.load(f)
        
        if isinstance(replays, list) and len(replays) > 0:
            replay = replays[0]
        else:
            replay = replays
        
        start = time.perf_counter()
        features = extractor.extract_from_replay(replay, extract_every_n_turns=2)
        elapsed = time.perf_counter() - start
        
        print(f"\n⏱️  単一リプレイ抽出: {elapsed*1000:.2f}ms ({len(features)}ターン)")
        assert elapsed < 0.05  # 50ms以内
