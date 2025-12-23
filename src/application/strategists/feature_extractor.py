"""
特徴量抽出モジュール - Fast-Lane用

リプレイログからLightGBM訓練用の特徴量を抽出する。
Phase 1では基本的な特徴量のみを実装し、10ms以内の推論を実現する。

Usage:
    extractor = FeatureExtractor()
    features = extractor.extract_from_replay(replay_data)
    df = extractor.extract_batch(replay_files)
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class TurnSnapshot:
    """
    ターン毎の対戦状態スナップショット
    
    Attributes:
        turn: ターン番号
        p1_active: P1のアクティブポケモン (最大2体)
        p2_active: P2のアクティブポケモン (最大2体)
        p1_hp: P1のHP状況 {pokemon_name: hp_fraction}
        p2_hp: P2のHP状況
        p1_fainted: P1の倒れたポケモン数
        p2_fainted: P2の倒れたポケモン数
        weather: 天候 (rain, sun, snow, etc.)
        terrain: フィールド (electric, psychic, grassy, misty)
        trick_room: トリックルーム状態
        winner: 勝者 (p1, p2, None)
    """
    turn: int
    p1_active: List[str]
    p2_active: List[str]
    p1_hp: Dict[str, float]
    p2_hp: Dict[str, float]
    p1_fainted: int
    p2_fainted: int
    weather: Optional[str]
    terrain: Optional[str]
    trick_room: bool
    winner: Optional[str]


@dataclass
class BattleFeatures:
    """
    LightGBM訓練用の特徴量
    
    Phase 1では基本的な数値特徴のみ実装:
    - HP合計/差分
    - 倒れたポケモン数
    - 天候・地形・トリックルーム
    
    Phase 2で追加予定:
    - 種族値・タイプ相性
    - 技威力・命中率
    - 持ち物・特性
    """
    # メタ情報
    replay_id: str
    turn: int
    rating: int
    
    # HP特徴量
    p1_total_hp: float
    p2_total_hp: float
    hp_difference: float  # (p1 - p2) / 2.0
    
    # 倒れたポケモン
    p1_fainted: int
    p2_fainted: int
    fainted_difference: int  # (p2 - p1) ... 相手が多く倒れているほど有利
    
    # フィールド状態
    has_weather: int  # 0 or 1
    has_terrain: int
    has_trick_room: int
    
    # アクティブポケモン数
    p1_active_count: int
    p2_active_count: int
    
    # ターゲット (勝率)
    p1_win: int  # 0 or 1


class FeatureExtractor:
    """
    リプレイログから特徴量を抽出するクラス
    
    Phase 1では簡易パースを実装:
    - HP情報の抽出 (|-damage, |-heal, faint)
    - 天候・地形情報 (|-weather, |-terrain)
    - ターン数とアクティブポケモン
    """
    
    def __init__(self):
        # 正規表現パターン (Phase 1では単純なマッチング)
        self.damage_pattern = re.compile(r"\|-damage\|([^|]+)\|(\d+)/(\d+)")
        self.heal_pattern = re.compile(r"\|-heal\|([^|]+)\|(\d+)/(\d+)")
        self.faint_pattern = re.compile(r"\|faint\|([^|]+)")
        self.weather_pattern = re.compile(r"\|-weather\|([^|]+)")
        self.terrain_pattern = re.compile(r"\|-fieldstart\|move: ([^|]+) Terrain")
        self.trick_room_pattern = re.compile(r"\|-fieldstart\|move: Trick Room")
        self.trick_room_end_pattern = re.compile(r"\|-fieldend\|move: Trick Room")
        
    def extract_from_replay(
        self,
        replay_data: Dict[str, Any],
        extract_every_n_turns: int = 1
    ) -> List[BattleFeatures]:
        """
        単一リプレイから特徴量を抽出
        
        Args:
            replay_data: リプレイJSONデータ (id, log, rating, players)
            extract_every_n_turns: N ターン毎に特徴量抽出 (デフォルト: 全ターン)
            
        Returns:
            各ターンの特徴量リスト
        """
        replay_id = replay_data.get("id", "unknown")
        log = replay_data.get("log", "")
        rating = replay_data.get("rating", 1500)
        
        # ログを行ごとに分割
        lines = log.split("\n")
        
        # 勝者を特定
        winner = self._extract_winner(lines)
        
        # ターン毎のスナップショットを構築
        snapshots = self._parse_battle_log(lines, winner)
        
        # 特徴量に変換
        features_list = []
        for i, snapshot in enumerate(snapshots):
            # サンプリング (extract_every_n_turns毎に抽出)
            if i % extract_every_n_turns != 0:
                continue
            
            features = self._snapshot_to_features(
                snapshot,
                replay_id,
                rating
            )
            features_list.append(features)
        
        return features_list
    
    def extract_batch(
        self,
        replay_files: List[Path],
        extract_every_n_turns: int = 2
    ) -> pd.DataFrame:
        """
        複数リプレイファイルからバッチ抽出
        
        Args:
            replay_files: リプレイJSONファイルのパスリスト
            extract_every_n_turns: N ターン毎に抽出 (デフォルト: 2)
            
        Returns:
            特徴量DataFrame (列: replay_id, turn, p1_total_hp, ..., p1_win)
        """
        all_features = []
        
        for file_path in replay_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    replays = json.load(f)
                
                # 単一リプレイまたはリストを処理
                if isinstance(replays, dict):
                    replays = [replays]
                
                for replay in replays:
                    features = self.extract_from_replay(
                        replay,
                        extract_every_n_turns
                    )
                    all_features.extend(features)
                    
            except Exception as e:
                print(f"⚠️  {file_path.name} のパースエラー: {e}")
                continue
        
        # DataFrameに変換
        df = pd.DataFrame([vars(f) for f in all_features])
        return df
    
    def _extract_winner(self, lines: List[str]) -> Optional[str]:
        """
        勝者を特定
        
        Returns:
            "p1", "p2", or None
        """
        for line in lines:
            if line.startswith("|win|"):
                # |win|Player Name の形式
                winner_name = line.split("|")[2]
                # ログの先頭で p1/p2 とプレイヤー名の対応を探す
                for early_line in lines[:50]:
                    if f"|player|p1|" in early_line and winner_name in early_line:
                        return "p1"
                    if f"|player|p2|" in early_line and winner_name in early_line:
                        return "p2"
        return None
    
    def _parse_battle_log(
        self,
        lines: List[str],
        winner: Optional[str]
    ) -> List[TurnSnapshot]:
        """
        バトルログをパースしてターン毎のスナップショットを生成
        
        Args:
            lines: ログの行リスト
            winner: 最終的な勝者
            
        Returns:
            各ターンのスナップショットリスト
        """
        snapshots = []
        
        # 初期状態
        current_turn = 0
        p1_hp: Dict[str, float] = {}
        p2_hp: Dict[str, float] = {}
        p1_active: List[str] = []
        p2_active: List[str] = []
        p1_fainted: int = 0
        p2_fainted: int = 0
        weather: Optional[str] = None
        terrain: Optional[str] = None
        trick_room: bool = False
        
        for line in lines:
            # ターン開始
            if line.startswith("|turn|"):
                current_turn = int(line.split("|")[2])
                
                # 前ターンのスナップショットを保存
                if current_turn > 1:
                    snapshot = TurnSnapshot(
                        turn=current_turn - 1,
                        p1_active=list(p1_active),
                        p2_active=list(p2_active),
                        p1_hp=dict(p1_hp),
                        p2_hp=dict(p2_hp),
                        p1_fainted=p1_fainted,
                        p2_fainted=p2_fainted,
                        weather=weather,
                        terrain=terrain,
                        trick_room=trick_room,
                        winner=winner if current_turn == len([l for l in lines if l.startswith("|turn|")]) + 1 else None
                    )
                    snapshots.append(snapshot)
            
            # ポケモン交代
            if "|switch|" in line:
                parts = line.split("|")
                if len(parts) >= 4:
                    position = parts[2]  # "p1a: Pokemon Name" 形式
                    pokemon_full = parts[3].split(",")[0]  # "Pokemon Name, L50" から名前抽出
                    
                    player = "p1" if position.startswith("p1") else "p2"
                    
                    # アクティブリストを更新
                    if player == "p1":
                        if pokemon_full not in p1_active:
                            p1_active.append(pokemon_full)
                        if len(p1_active) > 2:
                            p1_active = p1_active[-2:]
                        p1_hp[pokemon_full] = 1.0  # 初期HP
                    else:
                        if pokemon_full not in p2_active:
                            p2_active.append(pokemon_full)
                        if len(p2_active) > 2:
                            p2_active = p2_active[-2:]
                        p2_hp[pokemon_full] = 1.0
            
            # ダメージ
            match = self.damage_pattern.search(line)
            if match:
                position = match.group(1)  # "p1a: Pokemon"
                current_hp = int(match.group(2))
                max_hp = int(match.group(3))
                hp_fraction = current_hp / max_hp
                
                # ポケモン名を抽出
                pokemon_name = position.split(": ")[-1] if ": " in position else position
                
                if position.startswith("p1"):
                    p1_hp[pokemon_name] = hp_fraction
                elif position.startswith("p2"):
                    p2_hp[pokemon_name] = hp_fraction
            
            # 回復
            match = self.heal_pattern.search(line)
            if match:
                position = match.group(1)
                current_hp = int(match.group(2))
                max_hp = int(match.group(3))
                hp_fraction = current_hp / max_hp
                
                pokemon_name = position.split(": ")[-1] if ": " in position else position
                
                if position.startswith("p1"):
                    p1_hp[pokemon_name] = hp_fraction
                elif position.startswith("p2"):
                    p2_hp[pokemon_name] = hp_fraction
            
            # フェイント
            match = self.faint_pattern.search(line)
            if match:
                position = match.group(1)
                pokemon_name = position.split(": ")[-1] if ": " in position else position
                
                if position.startswith("p1"):
                    p1_fainted += 1
                    p1_hp[pokemon_name] = 0.0
                    if pokemon_name in p1_active:
                        p1_active.remove(pokemon_name)
                elif position.startswith("p2"):
                    p2_fainted += 1
                    p2_hp[pokemon_name] = 0.0
                    if pokemon_name in p2_active:
                        p2_active.remove(pokemon_name)
            
            # 天候
            match = self.weather_pattern.search(line)
            if match:
                weather_name = match.group(1)
                if weather_name.lower() == "none":
                    weather = None
                else:
                    weather = weather_name
            
            # 地形
            match = self.terrain_pattern.search(line)
            if match:
                terrain = match.group(1)  # "Electric", "Psychic", etc.
            
            # トリックルーム
            if self.trick_room_pattern.search(line):
                trick_room = True
            if self.trick_room_end_pattern.search(line):
                trick_room = False
        
        # 最終ターンを追加
        if current_turn > 0:
            snapshot = TurnSnapshot(
                turn=current_turn,
                p1_active=p1_active,
                p2_active=p2_active,
                p1_hp=p1_hp,
                p2_hp=p2_hp,
                p1_fainted=p1_fainted,
                p2_fainted=p2_fainted,
                weather=weather,
                terrain=terrain,
                trick_room=trick_room,
                winner=winner
            )
            snapshots.append(snapshot)
        
        return snapshots
    
    def _snapshot_to_features(
        self,
        snapshot: TurnSnapshot,
        replay_id: str,
        rating: int
    ) -> BattleFeatures:
        """
        スナップショットを特徴量に変換
        
        Args:
            snapshot: ターンスナップショット
            replay_id: リプレイID
            rating: レーティング
            
        Returns:
            BattleFeatures
        """
        # HP合計を計算
        p1_total_hp = sum(snapshot.p1_hp.values())
        p2_total_hp = sum(snapshot.p2_hp.values())
        hp_difference = (p1_total_hp - p2_total_hp) / 2.0
        
        # 倒れたポケモン差分
        fainted_difference = snapshot.p2_fainted - snapshot.p1_fainted
        
        # フィールド状態
        has_weather = 1 if snapshot.weather else 0
        has_terrain = 1 if snapshot.terrain else 0
        has_trick_room = 1 if snapshot.trick_room else 0
        
        # アクティブポケモン数
        p1_active_count = len(snapshot.p1_active)
        p2_active_count = len(snapshot.p2_active)
        
        # ターゲット (P1の勝利 = 1, それ以外 = 0)
        p1_win = 1 if snapshot.winner == "p1" else 0
        
        return BattleFeatures(
            replay_id=replay_id,
            turn=snapshot.turn,
            rating=rating,
            p1_total_hp=p1_total_hp,
            p2_total_hp=p2_total_hp,
            hp_difference=hp_difference,
            p1_fainted=snapshot.p1_fainted,
            p2_fainted=snapshot.p2_fainted,
            fainted_difference=fainted_difference,
            has_weather=has_weather,
            has_terrain=has_terrain,
            has_trick_room=has_trick_room,
            p1_active_count=p1_active_count,
            p2_active_count=p2_active_count,
            p1_win=p1_win
        )
