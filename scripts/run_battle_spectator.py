#!/usr/bin/env python3
"""
VGC対戦観戦スクリプト

人間 vs AI の対戦をリアルタイムで観戦し、
各ターンの勝率と予想行動を表示する。

Usage:
    python scripts/run_battle_spectator.py --battle <battle_id>
    python scripts/run_battle_spectator.py --target VGC_AI

Examples:
    # 特定のバトルを観戦
    python scripts/run_battle_spectator.py --battle battle-gen9vgc2026regf-123

    # VGC_AIの対戦を自動検出して観戦
    python scripts/run_battle_spectator.py --target VGC_AI
"""

import argparse
import asyncio
import logging
import os
import sys

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.application.players.spectator import Spectator
from poke_env.ps_client.server_configuration import LocalhostServerConfiguration
from poke_env.ps_client.account_configuration import AccountConfiguration


async def main():
    parser = argparse.ArgumentParser(description="Spectate VGC Battle")
    parser.add_argument(
        "--target",
        type=str,
        default="VGC_AI",
        help="Target player to spectate"
    )
    parser.add_argument(
        "--battle",
        type=str,
        default=None,
        help="Specific battle ID to join (e.g., battle-gen9vgc2026regf-123)"
    )
    args = parser.parse_args()

    print(f"\n👀 観戦システム起動")
    print(f"   ターゲット: {args.target}")
    if args.battle:
        print(f"   バトルID: {args.battle}")
    print(f"\n💡 VGC AI を別ターミナルで起動してから")
    print(f"   人間がチャレンジすると自動で観戦します\n")

    try:
        # アカウント設定
        account_config = AccountConfiguration(
            username=f"Spectator_{args.target[:5]}",
            password=None
        )
        
        # 観戦エージェント作成
        spectator = Spectator(
            target_player=args.target,
            battle_id=args.battle,
            account_configuration=account_config,
            server_configuration=LocalhostServerConfiguration,
            log_level=logging.INFO,
        )

        # バトル検索と参加
        await spectator._search_and_join_battles()

    except KeyboardInterrupt:
        print("\n🛑 終了します")
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
