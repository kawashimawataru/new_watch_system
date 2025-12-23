#!/usr/bin/env python3
"""
Run Spectator Agent

Usage:
    python scripts/run_spectator.py --target [username]
"""

import argparse
import asyncio
import logging
import os
import sys

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from frontend.spectator import Spectator
from poke_env.ps_client.server_configuration import LocalhostServerConfiguration

async def main():
    parser = argparse.ArgumentParser(description="Run AI Spectator")
    parser.add_argument("--target", type=str, required=True, help="Target player username to watch")
    parser.add_argument("--battle", type=str, default=None, help="Battle ID to join directly (e.g., battle-gen9randombattle-1)")
    args = parser.parse_args()

    print(f"🚀 AI観戦エージェント起動")
    print(f"🎯 ターゲット: {args.target}")
    if args.battle:
        print(f"📍 バトルID: {args.battle}")
    print("Showdownサーバーに接続中...")

    try:
        spectator = Spectator(
            target_player=args.target,
            battle_id=args.battle,
            server_configuration=LocalhostServerConfiguration,
            log_level=10,
        )
        
        # エージェント実行
        # poke-envのPlayerは通常 battle_against などで動くが、
        # 観戦者は常駐する必要がある。
        # _search_and_join_battles は __init__ ではなくここで呼ぶべきか、
        # あるいは Spectator 内でタスクとして起動するか。
        # Spectator.run_loop() を作ったのでそれを呼ぶ。
        
        # ただし、poke-envの接続維持のために何かが必要。
        # player.listen() みたいなものがあればよいが...
        # 実は player.start_listening=True ならスレッド/タスクが走る。
        
        # メインループ
        await spectator.run_loop()
        
    except KeyboardInterrupt:
        print("\n🛑 終了します")
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
