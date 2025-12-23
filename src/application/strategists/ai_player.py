"""
AI プレイヤー：Pokemon Showdown サーバーと対戦する

使い方:
    python -m predictor.player.ai_player
"""

import asyncio
from typing import Optional

try:
    from poke_env.player import Player, RandomPlayer
    # avoid importing internal submodules that may move between versions
    from poke_env.ps_client.server_configuration import (
        ServerConfiguration,
        LocalhostServerConfiguration,
    )
    from poke_env.ps_client.account_configuration import AccountConfiguration
    POKE_ENV_AVAILABLE = True
except Exception as e:  # be explicit: any import problem handled here
    # Print helpful, specific error for debugging (don't claim missing package generically)
    print(f"poke-env import error: {e}")
    POKE_ENV_AVAILABLE = False
    Player = object
    RandomPlayer = None
    ServerConfiguration = None
    LocalhostServerConfiguration = None
    AccountConfiguration = None


# カスタムサーバー設定：完全にオフライン（認証なし）
if POKE_ENV_AVAILABLE:
    LocalServerConfigurationNoAuth = ServerConfiguration(
        "ws://localhost:8000/showdown/websocket",
        "http://localhost:8000/action.php?",  # ローカルの存在しないエンドポイント（使われない）
    )
else:
    LocalServerConfigurationNoAuth = None


class AIPlayer(Player):
    """
    Showdown サーバーと対戦する AI プレイヤー
    
    evaluate_position を使って最適な行動を選択します。
    """
    
    def __init__(self, *args, **kwargs):
        if not POKE_ENV_AVAILABLE:
            raise ImportError("poke-env import failed. Check virtualenv and package installation")
        
        super().__init__(*args, **kwargs)
        self.battles_played = 0
    
    def choose_move(self, battle):
        """
        各ターンで呼ばれる：最適な行動を選択
        """
        # 利用可能な行動を取得
        available_moves = battle.available_moves
        available_switches = battle.available_switches
        
        # 強制交代の場合
        if battle.force_switch:
            if available_switches:
                # とりあえず最初のポケモンに交代
                return self.create_order(available_switches[0])
            else:
                return self.choose_random_move(battle)
        
        # 技が使える場合
        if available_moves:
            # TODO: evaluate_position を使って最適な技を選択
            # 現状は最も威力の高い技を選択
            best_move = max(
                available_moves,
                key=lambda m: m.base_power if m.base_power else 0
            )
            return self.create_order(best_move)
        
        # 交代するしかない場合
        if available_switches:
            return self.create_order(available_switches[0])
        
        # 何もできない場合（まれ）
        return self.choose_random_move(battle)
    
    def _battle_finished_callback(self, battle):
        """バトル終了時のコールバック"""
        self.battles_played += 1
        result = "勝利" if battle.won else "敗北"
        print(f"\nバトル {self.battles_played} 終了: {result}")
        print(f"  対戦相手: {battle.opponent_username}")
        print(f"  ターン数: {battle.turn}")


async def main():
    """メイン: AI vs ランダムプレイヤーで対戦"""
    
    print("=" * 60)
    print("Pokemon Showdown AI Player")
    print("=" * 60)
    print()
    
    # サーバー設定: ローカルで対戦するなら LocalServerConfigurationNoAuth を使う
    use_local = True
    if use_local:
        server_config = LocalServerConfigurationNoAuth
        print("ローカル Showdown サーバー (localhost:8000) に接続します...")
        print("認証なしモードで接続")
    else:
        server_config = ServerConfiguration(
            "wss://sim3.psim.us/showdown/websocket",
            "https://play.pokemonshowdown.com/action.php?",
        )
        print("公式 Showdown サーバーに接続します...")
    print()
    
    # パスワードなしのアカウント設定（ローカルサーバー用）
    # NOTE: account_configurationにNoneを渡すと自動的にゲストアカウントが生成される
    account_config = None
    
    # AIプレイヤーを作成
    ai_player = AIPlayer(
        account_configuration=account_config,
        battle_format="gen9randombattle",
        max_concurrent_battles=1,
        server_configuration=server_config,
    )
    
    # 対戦相手（ランダムプレイヤー）を作成
    opponent = RandomPlayer(
        account_configuration=account_config,
        battle_format="gen9randombattle",
        max_concurrent_battles=1,
        server_configuration=server_config,
    )
    
    print(f"AIプレイヤー: {ai_player.username}")
    print(f"対戦相手: {opponent.username}")
    print()
    print("対戦を開始します...\n")
    
    # 1試合のみ対戦（チャレンジの連続送信を避けるため）
    n_battles = 1
    await ai_player.battle_against(opponent, n_battles=n_battles)
    
    # 結果を表示
    print("\n" + "=" * 60)
    print("対戦結果")
    print("=" * 60)
    print(f"総試合数: {n_battles}")
    print(f"勝利数: {ai_player.n_won_battles}")
    print(f"敗北数: {n_battles - ai_player.n_won_battles}")
    print(f"勝率: {ai_player.n_won_battles / n_battles * 100:.1f}%")
    print("=" * 60)


if __name__ == "__main__":
    if not POKE_ENV_AVAILABLE:
        print("Error: poke-env がインストールされていません")
        print("インストール: pip install poke-env")
        exit(1)
    
    asyncio.run(main())
