"""
カスタム例外クラス

プロジェクト全体で使用する例外クラスを定義します。
"""


class VGCAIError(Exception):
    """ベース例外クラス - すべてのカスタム例外の親"""
    
    def __init__(self, message: str = None, *args, **kwargs):
        self.message = message or self.__class__.__name__
        super().__init__(self.message, *args, **kwargs)


# ============================================================================
# ドメイン層の例外
# ============================================================================

class BattleStateError(VGCAIError):
    """バトル状態関連のエラー"""
    pass


class PokemonNotFoundError(VGCAIError):
    """ポケモンが見つからない"""
    pass


class InvalidMoveError(VGCAIError):
    """無効な技"""
    pass


class InvalidActionError(VGCAIError):
    """無効な行動"""
    pass


class AnalysisError(VGCAIError):
    """分析処理エラー"""
    pass


class EvaluationError(VGCAIError):
    """評価処理エラー"""
    pass


# ============================================================================
# インフラストラクチャ層の例外
# ============================================================================

class WebSocketError(VGCAIError):
    """WebSocket通信エラー"""
    pass


class ConnectionError(VGCAIError):
    """接続エラー"""
    pass


class BroadcastError(VGCAIError):
    """ブロードキャストエラー"""
    pass


class DatabaseError(VGCAIError):
    """データベースエラー"""
    pass


class ConfigurationError(VGCAIError):
    """設定エラー"""
    pass


# ============================================================================
# アプリケーション層の例外
# ============================================================================

class SpectatorError(VGCAIError):
    """観戦エージェントエラー"""
    pass


class LLMError(VGCAIError):
    """LLM呼び出しエラー"""
    pass


class LLMTimeoutError(LLMError):
    """LLMタイムアウト"""
    pass


class LLMRateLimitError(LLMError):
    """LLMレート制限"""
    pass


class StrategyError(VGCAIError):
    """戦略計算エラー"""
    pass


# ============================================================================
# Showdown関連の例外
# ============================================================================

class ShowdownError(VGCAIError):
    """Showdown通信エラー"""
    pass


class ShowdownConnectionError(ShowdownError):
    """Showdown接続エラー"""
    pass


class ShowdownAuthenticationError(ShowdownError):
    """Showdown認証エラー"""
    pass


class ShowdownBattleError(ShowdownError):
    """Showdownバトルエラー"""
    pass
