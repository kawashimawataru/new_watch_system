"""
Phase 1: 開発環境の基盤構築テスト

目的: poke-envを使ってローカルShowdownサーバーに接続し、
     ランダムBot同士を戦わせて対戦ログが取得できることを確認する。

実行方法:
    python scripts/phase1_test_connection.py
"""

import asyncio
from poke_env.player import RandomPlayer
from poke_env.player.player import Player


# ローカルサーバー設定
LOCAL_SERVER_CONFIG = {
    "websocket_url": "ws://localhost:8000/showdown/websocket",
    "authentication_url": "http://localhost:8000/action.php",
}


class SimpleObserverPlayer(RandomPlayer):
    """
    対戦ログを観察するシンプルなプレイヤー
    ランダムに行動しながら、各ターンの情報を出力する
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.turn_count = 0
    
    def choose_move(self, battle):
        """各ターンで呼ばれる"""
        self.turn_count += 1
        
        # 盤面情報を出力
        print(f"\n{'='*60}")
        print(f"[{self.username}] Turn {battle.turn}")
        print(f"{'='*60}")
        
        # 自分のアクティブポケモン
        if battle.active_pokemon:
            active = battle.active_pokemon
            print(f"自分: {active.species} (HP: {active.current_hp}/{active.max_hp})")
        
        # 相手のアクティブポケモン
        if battle.opponent_active_pokemon:
            opp = battle.opponent_active_pokemon
            hp_info = f"{opp.current_hp}/{opp.max_hp}" if opp.current_hp else "不明"
            print(f"相手: {opp.species} (HP: {hp_info})")
        
        # フィールド状況
        if battle.weather:
            print(f"天候: {battle.weather}")
        if battle.fields:
            print(f"フィールド: {', '.join(str(f) for f in battle.fields)}")
        
        # ランダムに行動
        return super().choose_move(battle)


async def main():
    """メイン処理"""
    
    print("=" * 70)
    print("Phase 1: Pokemon Showdown 接続テスト")
    print("=" * 70)
    print()
    print("ローカルサーバー (localhost:8000) に接続します...")
    print("ランダムBot同士を1試合戦わせます。")
    print()
    
    # 2体のランダムプレイヤーを作成
    try:
        player1 = SimpleObserverPlayer(
            battle_format="gen9randombattle",
            max_concurrent_battles=1,
        )
        
        player2 = SimpleObserverPlayer(
            battle_format="gen9randombattle",
            max_concurrent_battles=1,
        )
        
        print(f"Player 1: {player1.username}")
        print(f"Player 2: {player2.username}")
        print()
        print("対戦開始...")
        print()
        
        # 1試合実行
        await player1.battle_against(player2, n_battles=1)
        
        # 結果表示
        print()
        print("=" * 70)
        print("対戦結果")
        print("=" * 70)
        print(f"{player1.username}: {player1.n_won_battles}勝")
        print(f"{player2.username}: {player2.n_won_battles}勝")
        print()
        print("✅ Phase 1 完了: poke-envからShowdownサーバーへの接続成功！")
        print()
        
    except Exception as e:
        print()
        print("❌ エラーが発生しました:")
        print(f"   {type(e).__name__}: {e}")
        print()
        print("【トラブルシューティング】")
        print("1. Showdownサーバーが起動しているか確認:")
        print("   cd pokemon-showdown && node pokemon-showdown start")
        print()
        print("2. ポート8000が使用中か確認:")
        print("   lsof -i :8000")
        print()
        raise


if __name__ == "__main__":
    asyncio.run(main())
