#!/usr/bin/env python3
"""
PUCT vs Random 性能評価

PUCT MCTSプレイヤーとRandomPlayerを対戦させて勝率を測定。

使用方法:
    python scripts/evaluate_puct.py --games 10
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from poke_env import AccountConfiguration
from poke_env.player import Player, RandomPlayer
from poke_env.ps_client.server_configuration import LocalhostServerConfiguration
from poke_env.battle import DoubleBattle

from predictor.core.puct_mcts import PUCTMCTS


class PUCTPlayer(Player):
    """PUCT MCTS を使用するAIプレイヤー"""
    
    def __init__(
        self,
        n_simulations: int = 50,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.mcts = PUCTMCTS(n_simulations=n_simulations, use_learned_models=True)
        self.wins = 0
        self.losses = 0
        self.total_battles = 0
    
    def choose_move(self, battle: DoubleBattle):
        """PUCT MCTSで行動を選択"""
        try:
            action, info = self.mcts.search(battle)
            # actionからpoke-env形式に変換
            return self._action_to_order(battle, action)
        except Exception as e:
            # フォールバック
            return self.choose_random_doubles_move(battle)
    
    def _action_to_order(self, battle: DoubleBattle, action):
        """JointAction を DoubleBattleOrder に変換"""
        from poke_env.player.battle_order import DoubleBattleOrder
        
        orders = []
        
        # Slot 0
        if action.slot0_action:
            a0 = action.slot0_action
            order0 = self._single_action_to_order(battle, 0, a0)
            if order0:
                orders.append(order0)
        
        # Slot 1
        if action.slot1_action:
            a1 = action.slot1_action
            order1 = self._single_action_to_order(battle, 1, a1)
            if order1:
                orders.append(order1)
        
        if len(orders) == 0:
            return self.choose_random_doubles_move(battle)
        elif len(orders) == 1:
            return DoubleBattleOrder(first_order=orders[0])
        else:
            return DoubleBattleOrder(first_order=orders[0], second_order=orders[1])
    
    def _single_action_to_order(self, battle: DoubleBattle, slot: int, action):
        """単一アクションをOrderに変換"""
        if action.action_type == "move":
            # 技を探す
            if slot < len(battle.available_moves):
                for move in battle.available_moves[slot]:
                    if move.id == action.move_or_pokemon:
                        return self.create_order(move)
            # 見つからなければ最初の技
            if slot < len(battle.available_moves) and battle.available_moves[slot]:
                return self.create_order(battle.available_moves[slot][0])
        
        elif action.action_type == "switch":
            # 交代先を探す
            if slot < len(battle.available_switches):
                for pokemon in battle.available_switches[slot]:
                    if pokemon.species == action.move_or_pokemon:
                        return self.create_order(pokemon)
        
        return None
    
    def teampreview(self, battle: DoubleBattle):
        return "/team 1234"
    
    def _battle_finished_callback(self, battle: DoubleBattle):
        self.total_battles += 1
        if battle.won:
            self.wins += 1
        elif battle.lost:
            self.losses += 1


async def evaluate(n_games: int = 10, n_simulations: int = 50):
    """評価実行"""
    print(f"🎮 PUCT vs Random 評価開始")
    print(f"   試合数: {n_games}")
    print(f"   MCTS シミュレーション: {n_simulations}")
    
    puct_player = PUCTPlayer(
        n_simulations=n_simulations,
        account_configuration=AccountConfiguration("PUCTBot", None),
        server_configuration=LocalhostServerConfiguration,
        battle_format="gen9randomdoublesbattle",
    )
    
    random_player = RandomPlayer(
        account_configuration=AccountConfiguration("RandomBot", None),
        server_configuration=LocalhostServerConfiguration,
        battle_format="gen9randomdoublesbattle",
    )
    
    # 対戦
    await puct_player.battle_against(random_player, n_battles=n_games)
    
    # 結果
    win_rate = puct_player.wins / max(1, puct_player.total_battles)
    
    print(f"\n{'='*40}")
    print(f"📊 評価結果")
    print(f"{'='*40}")
    print(f"  PUCT 勝利: {puct_player.wins}")
    print(f"  PUCT 敗北: {puct_player.losses}")
    print(f"  勝率: {win_rate:.1%}")
    print(f"{'='*40}")
    
    return win_rate


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PUCT vs Random Evaluation")
    parser.add_argument("--games", type=int, default=10, help="Number of games")
    parser.add_argument("--sims", type=int, default=50, help="MCTS simulations per move")
    
    args = parser.parse_args()
    asyncio.run(evaluate(args.games, args.sims))
