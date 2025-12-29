#!/usr/bin/env python3
"""
VGC AI Player 起動スクリプト

Usage:
    python scripts/run_vgc_ai.py [--format FORMAT] [--team TEAM_FILE] [--strategy STRATEGY]

Examples:
    python scripts/run_vgc_ai.py
    python scripts/run_vgc_ai.py --format gen9vgc2026regf
    python scripts/run_vgc_ai.py --team teams/my_team.txt
    python scripts/run_vgc_ai.py --strategy mcts
"""

import argparse
import asyncio
import logging
import os
import sys

# ログ設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# 安定版: frontend から直接インポート
from frontend.vgc_ai_player import VGCAIPlayer

from poke_env.ps_client.server_configuration import LocalhostServerConfiguration
from poke_env.ps_client.account_configuration import AccountConfiguration


# サンプルVGCチーム (Showdown形式) - VGC 2026 Reg F 対応
SAMPLE_VGC_TEAM = """
Tornadus @ Covert Cloak  
Ability: Prankster  
Level: 50  
Tera Type: Steel  
EVs: 212 HP / 204 Def / 36 SpA / 28 SpD / 28 Spe  
Modest Nature  
IVs: 0 Atk  
- Bleakwind Storm  
- Tailwind  
- Rain Dance  
- Taunt  

Urshifu-Rapid-Strike @ Choice Scarf  
Ability: Unseen Fist  
Level: 50  
Tera Type: Water  
EVs: 60 HP / 252 Atk / 4 Def / 12 SpD / 180 Spe  
Adamant Nature  
- Surging Strikes  
- Close Combat  
- Ice Spinner  
- U-turn  

Raging Bolt @ Booster Energy  
Ability: Protosynthesis  
Level: 50  
Tera Type: Electric  
EVs: 196 HP / 68 Def / 180 SpA / 4 SpD / 60 Spe  
Modest Nature  
IVs: 20 Atk  
- Thunderbolt  
- Draco Meteor  
- Thunderclap  
- Protect  

Entei @ Assault Vest  
Ability: Inner Focus  
Level: 50  
Tera Type: Grass  
EVs: 140 HP / 132 Atk / 4 Def / 124 SpD / 108 Spe  
Adamant Nature  
- Sacred Fire  
- Extreme Speed  
- Stomping Tantrum  
- Snarl  

Amoonguss @ Rocky Helmet  
Ability: Regenerator  
Level: 50  
Tera Type: Water  
EVs: 236 HP / 156 Def / 116 SpD  
Relaxed Nature  
IVs: 0 Atk / 0 Spe  
- Sludge Bomb  
- Spore  
- Rage Powder  
- Protect  

Landorus @ Life Orb  
Ability: Sheer Force  
Level: 50  
Tera Type: Water  
EVs: 132 HP / 4 Def / 116 SpA / 4 SpD / 252 Spe  
Modest Nature  
IVs: 0 Atk  
- Earth Power  
- Sludge Bomb  
- Sandsear Storm  
- Protect  
"""


async def main():
    parser = argparse.ArgumentParser(description="Run VGC AI Player")
    parser.add_argument(
        "--format",
        type=str,
        default="gen9vgc2026regfbo3",  # Bo3 = Open Team Sheet有効
        help="Battle format (default: gen9vgc2026regfbo3)"
    )
    parser.add_argument(
        "--team",
        type=str,
        default=None,
        help="Path to team file (optional, uses sample team if not provided)"
    )
    parser.add_argument(
        "--name",
        type=str,
        default="VGC_AI",
        help="Username for the AI player"
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="heuristic",
        choices=["heuristic", "mcts"],
        help="Action selection strategy: 'heuristic' (fast) or 'mcts' (smart)"
    )
    args = parser.parse_args()

    # チーム読み込み
    team = SAMPLE_VGC_TEAM
    if args.team and os.path.exists(args.team):
        with open(args.team, 'r') as f:
            team = f.read()
        print(f"📂 チーム読み込み: {args.team}")
    else:
        print("📂 サンプルチームを使用")

    print(f"\n🎮 VGC AI Player を起動します")
    print(f"   フォーマット: {args.format}")
    print(f"   ユーザー名: {args.name}")
    print(f"   戦略: {args.strategy}")
    print(f"\n🌐 http://localhost:8000 にアクセスして")
    print(f"   '{args.name}' にチャレンジしてください!\n")

    try:
        # アカウント設定 (ユーザー名を指定)
        account_config = AccountConfiguration(username=args.name, password=None)
        
        # AIプレイヤーを作成
        ai_player = VGCAIPlayer(
            account_configuration=account_config,
            battle_format=args.format,
            server_configuration=LocalhostServerConfiguration,
            max_concurrent_battles=1,
            team=team,
            log_level=logging.DEBUG,
            strategy=args.strategy,
        )

        # チャレンジを待機（自動的に受け付ける）
        print("⏳ チャレンジを待機中... (Ctrl+C で終了)")
        print("   ※ チャレンジが来たら自動的に受け付けます")
        print(f"   ※ フォーマット: {args.format}\n")
        
        # accept_challenges でチャレンジを自動受付
        # n_challenges=0 は無限に受け付ける
        await ai_player.accept_challenges(opponent=None, n_challenges=1)
        
        print("\n🏁 バトル終了！")

    except KeyboardInterrupt:
        print("\n🛑 終了します")
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
