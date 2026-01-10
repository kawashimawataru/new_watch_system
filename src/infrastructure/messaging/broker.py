import asyncio
from typing import List, Any
from fastapi import WebSocket

class MessageBroker:
    """
    WebSocketクライアントへのメッセージブロードキャストを行うブローカー。
    シングルトンパターンで使用することを想定。
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """新しいWebSocket接続を受け入れる"""
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"📡 New spectator connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """WebSocket接続を切断リストから削除"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"🔌 Spectator disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """全接続クライアントにメッセージを送信"""
        if not self.active_connections:
            return

        to_remove = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"⚠️ Broadcast error: {e}")
                to_remove.append(connection)
        
        # エラーが発生した接続を削除
        for conn in to_remove:
            self.disconnect(conn)

# グローバルシングルトンインスタンス
_broker = MessageBroker()

def get_message_broker() -> MessageBroker:
    return _broker
