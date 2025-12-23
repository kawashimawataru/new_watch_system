"""
Pokemon Showdown との接続を確認するシンプルなテストスクリプト。

使い方:
1. pokemon-showdown サーバーを起動
   cd pokemon-showdown && node pokemon-showdown start

2. このスクリプトを実行
   python scripts/test_showdown_connection.py

注意:
- poke-envはデフォルトで公式Showdownサーバー (play.pokemonshowdown.com) に接続します
- ローカルサーバーを使う場合は、LocalhostServerConfiguration を使用します
"""

import asyncio
from poke_env.player import RandomPlayer
from poke_env.server_configuration import LocalhostServerConfiguration


async def main():
    """ランダムプレイヤー同士で1試合実行して接続確認"""
    
    print("Pokemon Showdown 接続テストを開始します...")
    print("公式サーバー (play.pokemonshowdown.com) に接続します\n")
    print("※ ローカルサーバーを使う場合は、ServerConfiguration を変更してください\n")
    
    # 注意: ローカルサーバーに接続する場合は以下のようにします
    # server_config = LocalhostServerConfiguration
    # player1 = RandomPlayer(battle_format="...", server_configuration=server_config)
    
    try:
        # ランダム行動を取るプレイヤーを2つ作成
        # デフォルトでは公式サーバーに接続
        player1 = RandomPlayer(
            battle_format="gen9randombattle",
            max_concurrent_battles=1,
        )
        player2 = RandomPlayer(
            battle_format="gen9randombattle",
            max_concurrent_battles=1,
        )
        
        print("プレイヤーを作成しました")
        print(f"Player 1: {player1.username}")
        print(f"Player 2: {player2.username}")
        print("\nバトルを開始します...\n")
        
        # 1試合実行
        await player1.battle_against(player2, n_battles=1)
        
        print("\n=== バトル結果 ===")
        print(f"Player 1: {player1.n_won_battles}勝 / {player1.n_finished_battles}戦")
        print(f"Player 2: {player2.n_won_battles}勝 / {player2.n_finished_battles}戦")
        
        if player1.n_finished_battles > 0:
            print("\n✓ 接続成功！Showdown サーバーとの通信が正常に動作しています。")
        else:
            print("\n✗ バトルが完了しませんでした。")
            
    except Exception as e:
        print(f"\n✗ エラーが発生しました: {e}")
        print("\n考えられる原因:")
        print("1. Showdown サーバーが起動していない")
        print("   → cd pokemon-showdown && node pokemon-showdown start")
        print("2. ポート8000が使用中")
        print("   → 他のプロセスを終了するか、ポート番号を変更")
        print("3. ネットワーク接続の問題")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
