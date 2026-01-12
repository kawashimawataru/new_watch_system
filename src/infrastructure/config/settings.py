"""
アプリケーション設定モジュール

プロジェクト全体の設定を管理します。
"""
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import os


@dataclass
class DatabaseConfig:
    """データベース設定"""
    url: str = "sqlite:///data/battles.db"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


@dataclass
class WebSocketConfig:
    """WebSocket設定"""
    host: str = "0.0.0.0"
    port: int = 8000
    max_connections: int = 100
    ping_interval: float = 30.0
    ping_timeout: float = 10.0


@dataclass
class LLMConfig:
    """LLM設定"""
    provider: str = "openai"
    api_key: Optional[str] = None
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 1024
    timeout: float = 10.0
    
    def __post_init__(self):
        # 環境変数からAPIキーを取得
        if self.api_key is None:
            self.api_key = os.getenv("OPENAI_API_KEY")


@dataclass
class SpectatorConfig:
    """観戦エージェント設定"""
    target_player: str = "VGC_AI"
    battle_search_interval: float = 2.0
    max_watched_battles: int = 10
    mcts_rollouts: int = 500
    mcts_max_turns: int = 20
    fast_model_path: str = "models/fast_lane.pkl"


@dataclass
class ShowdownConfig:
    """Pokemon Showdown設定"""
    host: str = "localhost"
    port: int = 8000
    use_ssl: bool = False
    authentication_url: Optional[str] = None


@dataclass 
class LoggingConfig:
    """ロギング設定"""
    level: str = "INFO"
    log_dir: str = "logs"
    file_log_level: str = "DEBUG"
    console_log_level: str = "INFO"
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


@dataclass
class AppConfig:
    """アプリケーション全体設定"""
    debug: bool = False
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    spectator: SpectatorConfig = field(default_factory=SpectatorConfig)
    showdown: ShowdownConfig = field(default_factory=ShowdownConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    def __post_init__(self):
        # 環境変数からデバッグモードを取得
        self.debug = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    """
    設定をロード
    
    Args:
        config_path: 設定ファイルパス（将来の拡張用）
    
    Returns:
        AppConfig: アプリケーション設定
    """
    # 現在は環境変数からのみ読み込み
    # 将来的にはYAML/TOMLファイルからも読み込み可能に
    
    config = AppConfig(
        debug=os.getenv("DEBUG", "false").lower() in ("true", "1", "yes"),
        database=DatabaseConfig(
            url=os.getenv("DATABASE_URL", "sqlite:///data/battles.db"),
            echo=os.getenv("DATABASE_ECHO", "false").lower() in ("true", "1"),
        ),
        websocket=WebSocketConfig(
            host=os.getenv("WEBSOCKET_HOST", "0.0.0.0"),
            port=int(os.getenv("WEBSOCKET_PORT", "8000")),
        ),
        llm=LLMConfig(
            provider=os.getenv("LLM_PROVIDER", "openai"),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
        ),
        spectator=SpectatorConfig(
            target_player=os.getenv("SPECTATOR_TARGET", "VGC_AI"),
            battle_search_interval=float(os.getenv("SPECTATOR_INTERVAL", "2.0")),
        ),
        showdown=ShowdownConfig(
            host=os.getenv("SHOWDOWN_HOST", "localhost"),
            port=int(os.getenv("SHOWDOWN_PORT", "8000")),
        ),
        logging=LoggingConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            log_dir=os.getenv("LOG_DIR", "logs"),
        ),
    )
    
    return config


# グローバル設定インスタンス
config = load_config()
