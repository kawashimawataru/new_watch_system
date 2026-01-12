"""
統一ロガーモジュール

プロジェクト全体で使用する統一ロガーを提供します。
print文の代わりにこのモジュールを使用してください。
"""
import logging
import sys
from pathlib import Path
from typing import Optional


class ProjectLogger:
    """プロジェクト統一ロガー（シングルトン）"""
    
    _instance: Optional['ProjectLogger'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # ルートロガー設定
        self.logger = logging.getLogger("vgc_ai_spectator")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False  # 親ロガーへの伝播を防止
        
        # 既存のハンドラーをクリア（重複防止）
        self.logger.handlers.clear()
        
        # コンソールハンドラー（INFO以上）
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        
        # ファイルハンドラー（DEBUG以上）
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "spectator.log", encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        
        # エラーファイルハンドラー（ERROR以上）
        error_handler = logging.FileHandler(log_dir / "error.log", encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s\n%(exc_info)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_handler.setFormatter(error_format)
        
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)
        
        self._initialized = True
    
    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """
        ロガーを取得
        
        Args:
            name: 子ロガー名（例: "spectator", "broker"）
        
        Returns:
            logging.Logger: ロガーインスタンス
        """
        if name:
            return self.logger.getChild(name)
        return self.logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    ロガー取得ヘルパー関数
    
    Usage:
        >>> logger = get_logger("spectator")
        >>> logger.info("観戦開始")
        >>> logger.error("エラー発生", exc_info=True)
    
    Args:
        name: 子ロガー名（省略可）
    
    Returns:
        logging.Logger: ロガーインスタンス
    """
    return ProjectLogger().get_logger(name)
