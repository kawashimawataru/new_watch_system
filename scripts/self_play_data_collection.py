#!/usr/bin/env python3
"""
Self-Play Data Collection for VGC 2026 Reg F

AI同士を対戦させてトレーニングデータを自動収集。

使用方法:
    python scripts/self_play_data_collection.py --games 100

出力:
    data/battle_logs/*.json (各試合のログ)
    data/training_data.pkl (学習用データセット)
"""

import argparse
import asyncio
import json
import os
import pickle
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.player import Player, RandomPlayer
from poke_env.battle import DoubleBattle


# ============================================================================
# データ収集用プレイヤー
# ============================================================================

class DataCollectorPlayer(Player):
    """
    データ収集用プレイヤー
    
    ヒューリスティックで行動しつつ、ログを記録する。
    """
    
    def __init__(
        self,
        account_configuration: Optional[AccountConfiguration] = None,
        server_configuration: Optional[ServerConfiguration] = None,
        battle_format: str = "gen9vgc2024regf",
        team: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            account_configuration=account_configuration,
            server_configuration=server_configuration,
            battle_format=battle_format,
            team=team,
            **kwargs
        )
        self.battle_logs: Dict[str, List[Dict]] = {}
        self.current_battle_id: Optional[str] = None
        self.winners: Dict[str, str] = {}  # battle_id -> winner
    
    def choose_move(self, battle: DoubleBattle):
        """ヒューリスティックで行動選択 + ログ記録"""
        self.current_battle_id = battle.battle_tag
        
        # ターンログを記録
        turn_log = self._create_turn_log(battle)
        
        if battle.battle_tag not in self.battle_logs:
            self.battle_logs[battle.battle_tag] = []
        self.battle_logs[battle.battle_tag].append(turn_log)
        
        # 行動選択（ヒューリスティック）
        orders = self._choose_heuristic_action(battle)
        
        # 選んだ行動をログに追加
        if orders:
            turn_log["self_action"] = self._action_to_dict(orders)
        
        from poke_env.player.battle_order import DoubleBattleOrder
        return orders if isinstance(orders, DoubleBattleOrder) else self.choose_random_doubles_move(battle)
    
    def _choose_heuristic_action(self, battle: DoubleBattle):
        """簡易ヒューリスティック行動選択"""
        from poke_env.player.battle_order import DoubleBattleOrder, BattleOrder
        
        orders = []
        
        for i, pokemon in enumerate(battle.active_pokemon):
            if pokemon is None or pokemon.fainted:
                continue
            
            # 使える技を取得
            moves = battle.available_moves[i] if i < len(battle.available_moves) else []
            switches = battle.available_switches[i] if i < len(battle.available_switches) else []
            
            # 威力が高い技を優先
            best_move = None
            best_score = -1
            
            for move in moves:
                score = move.base_power or 0
                if move.priority > 0:
                    score += 30
                if score > best_score:
                    best_score = score
                    best_move = move
            
            if best_move:
                # ターゲット決定
                target = None
                if best_move.target in ["normal", "any"]:
                    # 生きてる相手を探す
                    for j, opp in enumerate(battle.opponent_active_pokemon):
                        if opp and not opp.fainted:
                            target = j + 1  # poke-envのターゲット番号
                            break
                    if target is None:
                        target = 1
                
                orders.append(self.create_order(best_move, move_target=target))
            elif switches:
                # 技がなければ交代
                orders.append(self.create_order(switches[0]))
            else:
                # 何もできない
                pass
        
        if len(orders) == 0:
            return None
        elif len(orders) == 1:
            return DoubleBattleOrder(first_order=orders[0])
        else:
            return DoubleBattleOrder(first_order=orders[0], second_order=orders[1])
    
    def _create_turn_log(self, battle: DoubleBattle) -> Dict[str, Any]:
        """ターンログを作成"""
        log = {
            "turn": battle.turn,
            "self_state": {
                "hp": [p.current_hp_fraction if p else 0.0 for p in battle.active_pokemon],
                "status": [p.status.name if p and p.status else None for p in battle.active_pokemon],
                "species": [p.species if p else None for p in battle.active_pokemon],
                "reserves": len(battle.available_switches[0]) if battle.available_switches else 0,
            },
            "opp_state": {
                "hp": [p.current_hp_fraction if p else 0.0 for p in battle.opponent_active_pokemon],
                "status": [p.status.name if p and p.status else None for p in battle.opponent_active_pokemon],
                "species": [p.species if p else None for p in battle.opponent_active_pokemon],
            },
            "weather": battle.weather.name if battle.weather else None,
            "fields": [f.name for f in battle.fields] if battle.fields else [],
        }
        return log
    
    def _action_to_dict(self, order) -> Dict[str, Any]:
        """行動をディクショナリに変換"""
        from poke_env.player.battle_order import DoubleBattleOrder
        
        if not isinstance(order, DoubleBattleOrder):
            return {}
        
        result = {}
        if order.first_order:
            if hasattr(order.first_order, 'order') and order.first_order.order:
                if hasattr(order.first_order.order, 'id'):
                    result["slot0_type"] = "move"
                    result["slot0_move"] = order.first_order.order.id
                else:
                    result["slot0_type"] = "switch"
                    result["slot0_move"] = str(order.first_order.order)
        
        if order.second_order:
            if hasattr(order.second_order, 'order') and order.second_order.order:
                if hasattr(order.second_order.order, 'id'):
                    result["slot1_type"] = "move"
                    result["slot1_move"] = order.second_order.order.id
                else:
                    result["slot1_type"] = "switch"
                    result["slot1_move"] = str(order.second_order.order)
        
        return result
    
    def teampreview(self, battle: DoubleBattle) -> str:
        """チームプレビュー：先頭4匹を選出"""
        return "/team 1234"
    
    def _battle_finished_callback(self, battle: DoubleBattle):
        """バトル終了時のコールバック"""
        if battle.won:
            self.winners[battle.battle_tag] = self.username
        elif battle.lost:
            self.winners[battle.battle_tag] = "opponent"
        else:
            self.winners[battle.battle_tag] = "draw"


# ============================================================================
# Self-Play マネージャー
# ============================================================================

class SelfPlayManager:
    """
    Self-Play データ収集マネージャー
    """
    
    def __init__(
        self,
        output_dir: str = "data/battle_logs",
        format: str = "gen9vgc2024regf",
        team_file: Optional[str] = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.format = format
        self.team = self._load_team(team_file) if team_file else None
        
        self.all_logs: List[Dict] = []
    
    def _load_team(self, filepath: str) -> Optional[str]:
        """チームファイルを読み込み"""
        try:
            with open(filepath, 'r') as f:
                return f.read()
        except Exception as e:
            print(f"⚠️ Failed to load team: {e}")
            return None
    
    async def run_games(self, n_games: int = 10, concurrent: int = 1):
        """
        Self-Playを実行
        
        Args:
            n_games: 対戦回数
            concurrent: 同時実行数
        """
        print(f"🎮 Self-Play 開始: {n_games} 試合")
        print(f"   フォーマット: {self.format}")
        
        completed = 0
        
        for batch_start in range(0, n_games, concurrent):
            batch_size = min(concurrent, n_games - batch_start)
            tasks = []
            
            for i in range(batch_size):
                game_id = batch_start + i
                tasks.append(self._run_single_game(game_id))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    print(f"⚠️ Game error: {result}")
                else:
                    completed += 1
                    print(f"✅ Game {completed}/{n_games} completed")
        
        print(f"📊 完了: {completed}/{n_games} 試合")
        return completed
    
    async def _run_single_game(self, game_id: int) -> Dict:
        """1試合を実行"""
        # 2つのプレイヤーを作成
        player1 = DataCollectorPlayer(
            account_configuration=AccountConfiguration(f"SelfPlay1_{game_id}", None),
            server_configuration=ServerConfiguration("localhost:8000", None),
            battle_format=self.format,
            team=self.team,
            max_concurrent_battles=1,
        )
        
        player2 = DataCollectorPlayer(
            account_configuration=AccountConfiguration(f"SelfPlay2_{game_id}", None),
            server_configuration=ServerConfiguration("localhost:8000", None),
            battle_format=self.format,
            team=self.team,
            max_concurrent_battles=1,
        )
        
        try:
            # 対戦実行
            await player1.battle_against(player2, n_battles=1)
            
            # ログを収集
            for battle_id, logs in player1.battle_logs.items():
                winner = player1.winners.get(battle_id, "unknown")
                battle_data = {
                    "battle_id": battle_id,
                    "game_id": game_id,
                    "format": self.format,
                    "winner": winner,
                    "turns": logs,
                    "timestamp": datetime.now().isoformat(),
                }
                self.all_logs.append(battle_data)
                
                # 個別ファイルに保存
                log_file = self.output_dir / f"game_{game_id}.json"
                with open(log_file, 'w') as f:
                    json.dump(battle_data, f, indent=2, ensure_ascii=False)
            
            return {"game_id": game_id, "status": "success"}
        
        except Exception as e:
            return {"game_id": game_id, "status": "error", "error": str(e)}
    
    def save_training_data(self, output_path: str = "data/training_data.pkl"):
        """学習用データを保存"""
        from predictor.core.policy_value_learning import (
            TrainingExample, StateFeatures, ActionLabel, BattleLogCollector
        )
        
        collector = BattleLogCollector()
        examples = []
        
        for battle_data in self.all_logs:
            winner = battle_data.get("winner", "unknown")
            
            for turn_log in battle_data.get("turns", []):
                # StateFeatures を作成
                self_state = turn_log.get("self_state", {})
                opp_state = turn_log.get("opp_state", {})
                
                state = StateFeatures(
                    self_hp=self_state.get("hp", [1.0, 1.0]),
                    self_status=[0, 0],  # 簡易版
                    self_boosts=[{}, {}],
                    opp_hp=opp_state.get("hp", [1.0, 1.0]),
                    opp_status=[0, 0],
                    opp_boosts=[{}, {}],
                    self_reserves=self_state.get("reserves", 2),
                    opp_reserves=2,
                    weather=0,
                    terrain=0,
                    trick_room=0,
                    tailwind_self=0,
                    tailwind_opp=0,
                    turn=turn_log.get("turn", 1),
                )
                
                # ActionLabel を作成
                action = turn_log.get("self_action", {})
                slot0_key = f"{action.get('slot0_type', 'move')}:{action.get('slot0_move', 'tackle')}"
                slot1_key = f"{action.get('slot1_type', 'move')}:{action.get('slot1_move', 'tackle')}"
                
                action_label = ActionLabel(
                    slot0_action_id=collector.register_action(slot0_key),
                    slot1_action_id=collector.register_action(slot1_key),
                )
                
                # 勝敗
                outcome = 1.0 if winner == "SelfPlay1" else 0.0
                
                examples.append(TrainingExample(
                    state=state,
                    action=action_label,
                    outcome=outcome,
                    side="p1",
                ))
        
        # 保存
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            pickle.dump({
                'examples': examples,
                'action_vocab': collector.action_vocab,
            }, f)
        
        print(f"✅ トレーニングデータ保存: {output_path}")
        print(f"   サンプル数: {len(examples)}")
        print(f"   行動語彙数: {len(collector.action_vocab)}")
        
        return examples


# ============================================================================
# メイン
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Self-Play Data Collection")
    parser.add_argument("--games", type=int, default=10, help="Number of games to play")
    parser.add_argument("--concurrent", type=int, default=1, help="Concurrent games")
    parser.add_argument("--format", type=str, default="gen9vgc2024regf", help="Battle format")
    parser.add_argument("--team", type=str, default=None, help="Team file path")
    parser.add_argument("--output", type=str, default="data/battle_logs", help="Output directory")
    
    args = parser.parse_args()
    
    manager = SelfPlayManager(
        output_dir=args.output,
        format=args.format,
        team_file=args.team,
    )
    
    # Self-Play 実行
    completed = await manager.run_games(n_games=args.games, concurrent=args.concurrent)
    
    if completed > 0:
        # 学習データ保存
        manager.save_training_data("data/training_data.pkl")


if __name__ == "__main__":
    asyncio.run(main())
