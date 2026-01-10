from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from src.infrastructure.messaging.broker import get_message_broker
import asyncio

app = FastAPI(title="VGC AI Spectator API")

# CORS設定（Next.jsからのアクセスを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 開発環境のため全許可
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

broker = get_message_broker()

@app.websocket("/ws/spectator")
async def websocket_endpoint(websocket: WebSocket):
    await broker.connect(websocket)
    try:
        while True:
            # クライアントからのメッセージを受信（基本的にはサーバーPushだが、PingPong用などに待機）
            data = await websocket.receive_text()
            # 必要であれば処理
    except WebSocketDisconnect:
        broker.disconnect(websocket)
    except Exception as e:
        print(f"⚠️ WebSocket Error: {e}")
        broker.disconnect(websocket)

@app.get("/")
def read_root():
    return {"status": "ok", "app": "VGC AI Spectator API"}

# サーバー起動用のヘルパー（直接実行時）
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
