"""
インフラストラクチャ層のユニットテスト

- ロギング
- 設定管理
- 例外クラス
- メッセージブローカー
"""
import pytest
import asyncio
import logging
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock


class TestLogger:
    """ロギングモジュールのテスト"""
    
    def test_get_logger_returns_logger(self):
        """ロガーが正しく取得できること"""
        from src.infrastructure.logging import get_logger
        
        logger = get_logger("test")
        assert logger is not None
        assert isinstance(logger, logging.Logger)
    
    def test_get_logger_with_name(self):
        """名前付きロガーが取得できること"""
        from src.infrastructure.logging import get_logger
        
        logger = get_logger("test_module")
        assert "test_module" in logger.name
    
    def test_get_logger_without_name(self):
        """名前なしでルートロガーが取得できること"""
        from src.infrastructure.logging import get_logger
        
        logger = get_logger()
        assert logger is not None
    
    def test_logger_singleton(self):
        """ロガーがシングルトンとして動作すること"""
        from src.infrastructure.logging.logger import ProjectLogger
        
        logger1 = ProjectLogger()
        logger2 = ProjectLogger()
        assert logger1 is logger2
    
    def test_logger_can_log(self):
        """ログ出力ができること"""
        from src.infrastructure.logging import get_logger
        
        logger = get_logger("test_logging")
        # ログ出力がエラーなく完了すること
        logger.info("Test info message")
        logger.debug("Test debug message")
        logger.warning("Test warning message")


class TestEnv:
    """環境変数アクセサのテスト"""
    
    def test_get_existing_env(self):
        """既存の環境変数が取得できること"""
        from src.infrastructure.config.env import Env
        
        os.environ["TEST_VAR"] = "test_value"
        assert Env.get("TEST_VAR") == "test_value"
        del os.environ["TEST_VAR"]
    
    def test_get_with_default(self):
        """デフォルト値が使用されること"""
        from src.infrastructure.config.env import Env
        
        result = Env.get("NON_EXISTENT_VAR", "default")
        assert result == "default"
    
    def test_get_required_raises(self):
        """required=Trueで値がない場合にエラー"""
        from src.infrastructure.config.env import Env
        
        with pytest.raises(ValueError):
            Env.get("NON_EXISTENT_REQUIRED_VAR", required=True)
    
    def test_get_int(self):
        """整数値が取得できること"""
        from src.infrastructure.config.env import Env
        
        os.environ["TEST_INT"] = "42"
        assert Env.get_int("TEST_INT") == 42
        del os.environ["TEST_INT"]
    
    def test_get_int_default(self):
        """整数のデフォルト値が使用されること"""
        from src.infrastructure.config.env import Env
        
        assert Env.get_int("NON_EXISTENT_INT", 100) == 100
    
    def test_get_bool_true(self):
        """bool値trueが取得できること"""
        from src.infrastructure.config.env import Env
        
        for value in ["true", "1", "yes", "on"]:
            os.environ["TEST_BOOL"] = value
            assert Env.get_bool("TEST_BOOL") is True
            del os.environ["TEST_BOOL"]
    
    def test_get_bool_false(self):
        """bool値falseが取得できること"""
        from src.infrastructure.config.env import Env
        
        os.environ["TEST_BOOL"] = "false"
        assert Env.get_bool("TEST_BOOL") is False
        del os.environ["TEST_BOOL"]
    
    def test_get_list(self):
        """リストが取得できること"""
        from src.infrastructure.config.env import Env
        
        os.environ["TEST_LIST"] = "a,b,c"
        result = Env.get_list("TEST_LIST")
        assert result == ["a", "b", "c"]
        del os.environ["TEST_LIST"]


class TestAppConfig:
    """アプリケーション設定のテスト"""
    
    def test_config_has_defaults(self):
        """デフォルト設定が存在すること"""
        from src.infrastructure.config import config
        
        assert config is not None
        assert config.database is not None
        assert config.websocket is not None
        assert config.llm is not None
        assert config.spectator is not None
    
    def test_websocket_defaults(self):
        """WebSocket設定のデフォルト値"""
        from src.infrastructure.config.settings import WebSocketConfig
        
        ws_config = WebSocketConfig()
        assert ws_config.host == "0.0.0.0"
        assert ws_config.port == 8000
    
    def test_spectator_defaults(self):
        """観戦設定のデフォルト値"""
        from src.infrastructure.config.settings import SpectatorConfig
        
        spec_config = SpectatorConfig()
        assert spec_config.target_player == "VGC_AI"
        assert spec_config.mcts_rollouts == 500
    
    def test_load_config(self):
        """設定のロードができること"""
        from src.infrastructure.config.settings import load_config
        
        config = load_config()
        assert config is not None


class TestExceptions:
    """カスタム例外クラスのテスト"""
    
    def test_vgcai_error_is_exception(self):
        """VGCAIErrorがExceptionのサブクラス"""
        from src.domain.exceptions import VGCAIError
        
        assert issubclass(VGCAIError, Exception)
    
    def test_spectator_error_hierarchy(self):
        """SpectatorErrorの継承関係"""
        from src.domain.exceptions import SpectatorError, VGCAIError
        
        assert issubclass(SpectatorError, VGCAIError)
    
    def test_websocket_error_hierarchy(self):
        """WebSocketErrorの継承関係"""
        from src.domain.exceptions import WebSocketError, VGCAIError
        
        assert issubclass(WebSocketError, VGCAIError)
    
    def test_exception_message(self):
        """例外メッセージが設定されること"""
        from src.domain.exceptions import BattleStateError
        
        error = BattleStateError("Test error message")
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
    
    def test_exception_can_be_raised(self):
        """例外がraiseできること"""
        from src.domain.exceptions import AnalysisError
        
        with pytest.raises(AnalysisError):
            raise AnalysisError("Test")


class TestMessageBroker:
    """メッセージブローカーのテスト"""
    
    def test_get_broker_singleton(self):
        """ブローカーがシングルトンとして動作すること"""
        from src.infrastructure.messaging.broker import get_message_broker
        
        broker1 = get_message_broker()
        broker2 = get_message_broker()
        assert broker1 is broker2
    
    def test_broker_initial_state(self):
        """初期状態で接続がないこと"""
        from src.infrastructure.messaging.broker import MessageBroker
        
        broker = MessageBroker()
        assert len(broker.active_connections) == 0
        assert broker.connection_count == 0
    
    @pytest.mark.asyncio
    async def test_broker_connect(self):
        """WebSocket接続が追加されること"""
        from src.infrastructure.messaging.broker import MessageBroker
        
        broker = MessageBroker()
        
        # WebSocketのモック
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        
        await broker.connect(mock_ws)
        
        assert broker.connection_count == 1
        mock_ws.accept.assert_called_once()
    
    def test_broker_disconnect(self):
        """WebSocket接続が削除されること"""
        from src.infrastructure.messaging.broker import MessageBroker
        
        broker = MessageBroker()
        mock_ws = Mock()
        broker.active_connections.append(mock_ws)
        
        broker.disconnect(mock_ws)
        
        assert broker.connection_count == 0
    
    @pytest.mark.asyncio
    async def test_broker_broadcast(self):
        """ブロードキャストが機能すること"""
        from src.infrastructure.messaging.broker import MessageBroker
        
        broker = MessageBroker()
        
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock()
        broker.active_connections.append(mock_ws)
        
        message = {"type": "test", "data": "hello"}
        count = await broker.broadcast(message)
        
        assert count == 1
        mock_ws.send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_broker_broadcast_removes_failed(self):
        """ブロードキャスト失敗時に接続が削除されること"""
        from src.infrastructure.messaging.broker import MessageBroker
        
        broker = MessageBroker()
        
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock(side_effect=Exception("Connection closed"))
        broker.active_connections.append(mock_ws)
        
        message = {"type": "test"}
        count = await broker.broadcast(message)
        
        assert count == 0
        assert broker.connection_count == 0
    
    @pytest.mark.asyncio
    async def test_broker_send_to(self):
        """特定クライアントへの送信が機能すること"""
        from src.infrastructure.messaging.broker import MessageBroker
        
        broker = MessageBroker()
        
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock()
        broker.active_connections.append(mock_ws)
        
        message = {"type": "test"}
        result = await broker.send_to(mock_ws, message)
        
        assert result is True
        mock_ws.send_json.assert_called_once_with(message)


class TestAPIServer:
    """APIサーバーのテスト"""
    
    def test_app_exists(self):
        """FastAPIアプリが存在すること"""
        from src.interfaces.api.server import app
        
        assert app is not None
        assert app.title == "VGC AI Spectator API"
    
    def test_root_endpoint(self):
        """ルートエンドポイントが機能すること"""
        from src.interfaces.api.server import read_root
        
        result = read_root()
        assert result["status"] == "ok"
        assert "app" in result
    
    def test_health_endpoint(self):
        """ヘルスチェックエンドポイントが機能すること"""
        from src.interfaces.api.server import health_check
        
        result = health_check()
        assert result["status"] == "healthy"
        assert "connections" in result
