"""
FastAPI Server for VGC AI Spectator

WebSocket経由で観戦データを配信するAPIサーバー。
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.infrastructure.messaging.broker import get_message_broker
from src.infrastructure.logging import get_logger
from src.infrastructure.config import config

logger = get_logger("api.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    # Startup
    logger.info("VGC AI Spectator API starting up...")
    logger.info(f"WebSocket endpoint: ws://{config.websocket.host}:{config.websocket.port}/ws/spectator")
    
    yield
    
    # Shutdown
    logger.info("VGC AI Spectator API shutting down...")


app = FastAPI(
    title="VGC AI Spectator API",
    description="VGCバトル観戦AIシステムのAPI",
    version="1.0.0",
    lifespan=lifespan
)

# CORS設定（開発環境用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では制限すること
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

broker = get_message_broker()


@app.websocket("/ws/spectator")
async def websocket_endpoint(websocket: WebSocket):
    """
    観戦用WebSocketエンドポイント
    
    クライアントからの接続を受け付け、観戦データをプッシュ配信します。
    """
    await broker.connect(websocket)
    try:
        while True:
            # クライアントからのメッセージを受信
            # 基本的にはサーバープッシュだが、PingPong用などに待機
            data = await websocket.receive_text()
            logger.debug(f"Received from client: {data[:100] if len(data) > 100 else data}")
    except WebSocketDisconnect:
        broker.disconnect(websocket)
        logger.debug("Client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        broker.disconnect(websocket)


@app.get("/")
def read_root():
    """ヘルスチェック用ルートエンドポイント"""
    return {
        "status": "ok",
        "app": "VGC AI Spectator API",
        "version": "1.0.0",
        "connections": broker.connection_count
    }


@app.get("/health")
def health_check():
    """詳細ヘルスチェック"""
    return {
        "status": "healthy",
        "connections": broker.connection_count,
        "debug_mode": config.debug
    }


# サーバー起動用のヘルパー（直接実行時）
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server in standalone mode...")
    uvicorn.run(
        app,
        host=config.websocket.host,
        port=config.websocket.port,
        log_level="info" if not config.debug else "debug"
    )
