"""
環境変数アクセサモジュール

環境変数への統一的なアクセスを提供します。
"""
import os
from typing import Optional


class Env:
    """環境変数アクセサクラス"""
    
    @staticmethod
    def get(key: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
        """
        環境変数を取得
        
        Args:
            key: 環境変数名
            default: デフォルト値
            required: 必須かどうか
        
        Returns:
            環境変数の値
        
        Raises:
            ValueError: requiredがTrueで値がない場合
        """
        value = os.getenv(key, default)
        if required and value is None:
            raise ValueError(f"Required environment variable '{key}' is not set")
        return value
    
    @staticmethod
    def get_int(key: str, default: Optional[int] = None) -> Optional[int]:
        """
        環境変数を整数として取得
        
        Args:
            key: 環境変数名
            default: デフォルト値
        
        Returns:
            整数値またはNone
        """
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default
    
    @staticmethod
    def get_float(key: str, default: Optional[float] = None) -> Optional[float]:
        """
        環境変数を浮動小数点として取得
        
        Args:
            key: 環境変数名
            default: デフォルト値
        
        Returns:
            浮動小数点値またはNone
        """
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            return default
    
    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        """
        環境変数をboolとして取得
        
        Args:
            key: 環境変数名
            default: デフォルト値
        
        Returns:
            bool値
        """
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")
    
    @staticmethod
    def get_list(key: str, separator: str = ",", default: Optional[list] = None) -> list:
        """
        環境変数をリストとして取得
        
        Args:
            key: 環境変数名
            separator: 区切り文字
            default: デフォルト値
        
        Returns:
            文字列のリスト
        """
        value = os.getenv(key)
        if value is None:
            return default or []
        return [item.strip() for item in value.split(separator) if item.strip()]
