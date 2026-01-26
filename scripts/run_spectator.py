import argparse
import asyncio
import logging
import os
import sys
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# インポートパス修正
from src.application.players.spectator import Spectator
from poke_env.ps_client.server_configuration import LocalhostServerConfiguration
from src.interfaces.api.server import app

async def main():
    parser = argparse.ArgumentParser(description="Run AI Spectator")
    parser.add_argument("--target", type=str, required=True, help="Target player username to watch")
    parser.add_argument("--battle", type=str, default=None, help="Battle ID to join directly (e.g., battle-gen9randombattle-1)")
    parser.add_argument("--port", type=int, default=8000, help="API Server port")
    args = parser.parse_args()

    print(f"🚀 AI観戦エージェント起動")
    print(f"🎯 ターゲット: {args.target}")
    if args.battle:
        print(f"📍 バトルID: {args.battle}")
    print(f"🌍 API Server: http://localhost:{args.port}/ws/spectator")
    
    # Spectator 初期化
    print("Showdownサーバーに接続中...")
    # server_configuration=None を渡すと、spectator.py内で自動的にconfig.showdownの設定を使用
    spectator = Spectator(
        target_player=args.target,
        battle_id=args.battle,
        server_configuration=None,  # 自動的にconfig.showdownのポート設定を使用
        log_level=10,
    )
    
    # API Server 設定
    config = uvicorn.Config(app, host="0.0.0.0", port=args.port, log_level="info")
    server = uvicorn.Server(config)
    
    # 並列実行
    print("running...")
    print(f"✅ API Server starting on http://0.0.0.0:{args.port}")
    print(f"✅ WebSocket endpoint: ws://localhost:{args.port}/ws/spectator")
    try:
        # 両方のタスクを並列実行
        # エラーが発生しても片方が停止しないように個別にエラーハンドリング
        async def run_spectator_safe():
            try:
                await spectator.run_loop()
            except Exception as e:
                print(f"\n❌ 観戦エージェントエラー: {e}")
                import traceback
                traceback.print_exc()
        
        async def run_server_safe():
            try:
                await server.serve()
            except Exception as e:
                print(f"\n❌ APIサーバーエラー: {e}")
                import traceback
                traceback.print_exc()
        
        await asyncio.gather(
            run_spectator_safe(),
            run_server_safe(),
            return_exceptions=True
        )
    except KeyboardInterrupt:
        print("\n🛑 終了します")
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
