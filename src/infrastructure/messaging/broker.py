"""
WebSocket Message Broker

WebSocketクライアントへのメッセージブロードキャストを行うブローカー。
シングルトンパターンで使用。
"""
import asyncio
from typing import List, Any, Optional
from fastapi import WebSocket
from src.infrastructure.logging import get_logger
from src.domain.exceptions import BroadcastError

logger = get_logger("broker")


class MessageBroker:
    """
    WebSocketクライアントへのメッセージブロードキャストを行うブローカー。
    シングルトンパターンで使用することを想定。
    """
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()
        logger.debug("MessageBroker initialized")

    async def connect(self, websocket: WebSocket) -> None:
        """
        新しいWebSocket接続を受け入れる
        
        Args:
            websocket: WebSocket接続
        """
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"New spectator connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """
        WebSocket接続を切断リストから削除
        
        Args:
            websocket: WebSocket接続
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Spectator disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict) -> int:
        """
        全接続クライアントにメッセージを送信
        
        Args:
            message: 送信するメッセージ
        
        Returns:
            成功した送信数
        """
        if not self.active_connections:
            logger.debug("No active connections to broadcast")
            return 0

        to_remove: List[WebSocket] = []
        success_count = 0
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
                success_count += 1
            except Exception as e:
                logger.warning(f"Broadcast error: {e}")
                to_remove.append(connection)
        
        # エラーが発生した接続を削除
        for conn in to_remove:
            self.disconnect(conn)
        
        if to_remove:
            logger.debug(f"Removed {len(to_remove)} failed connections")
        
        return success_count
    
    async def send_to(self, websocket: WebSocket, message: dict) -> bool:
        """
        特定のクライアントにメッセージを送信
        
        Args:
            websocket: 送信先WebSocket
            message: 送信するメッセージ
        
        Returns:
            成功したかどうか
        """
        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"Send error: {e}")
            self.disconnect(websocket)
            return False

    @property
    def connection_count(self) -> int:
        """現在の接続数を取得"""
        return len(self.active_connections)


# グローバルシングルトンインスタンス
_broker: Optional[MessageBroker] = None


def get_message_broker() -> MessageBroker:
    """
    MessageBrokerのシングルトンインスタンスを取得
    
    Returns:
        MessageBroker: ブローカーインスタンス
    """
    global _broker
    if _broker is None:
        _broker = MessageBroker()
    return _broker
