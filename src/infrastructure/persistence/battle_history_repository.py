"""
Battle History Repository

観戦AI用のバトル履歴リポジトリ
Supabaseに接続してバトル履歴を保存・取得する
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from src.infrastructure.persistence.supabase_client import get_supabase_client
from src.infrastructure.logging import get_logger

logger = get_logger("battle_history")


class BattleHistoryRepository:
    """
    バトル履歴リポジトリ
    
    観戦AIが観戦したバトルの履歴をSupabaseに保存・取得する
    """
    
    def __init__(self, supabase_client=None):
        """
        リポジトリを初期化
        
        Args:
            supabase_client: Supabaseクライアント（省略時はシングルトンを使用）
        """
        # #region agent log
        import json
        try:
            log_data = {
                "location": "battle_history_repository.py:__init__",
                "message": "BattleHistoryRepository initialization",
                "data": {
                    "supabase_client_provided": supabase_client is not None,
                },
                "timestamp": __import__('time').time(),
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "B"
            }
            with open("/Users/kawashimawataru/Desktop/new_watch_game_system/.cursor/debug.log", "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion
        
        try:
            self.supabase = supabase_client or get_supabase_client()
            # #region agent log
            try:
                log_data = {
                    "location": "battle_history_repository.py:__init__",
                    "message": "Supabase client obtained",
                    "data": {
                        "supabase_enabled": getattr(self.supabase, 'enabled', False),
                        "supabase_connected": self.supabase.is_connected() if hasattr(self.supabase, 'is_connected') else False,
                    },
                    "timestamp": __import__('time').time(),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "B"
                }
                with open("/Users/kawashimawataru/Desktop/new_watch_game_system/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
        except Exception as e:
            # #region agent log
            try:
                log_data = {
                    "location": "battle_history_repository.py:__init__",
                    "message": "Error initializing repository",
                    "data": {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    "timestamp": __import__('time').time(),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "B"
                }
                with open("/Users/kawashimawataru/Desktop/new_watch_game_system/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            raise
    
    async def save_battle_start(
        self,
        battle_id: str,
        battle_tag: str,
        player_name: str,
        opponent_name: str,
        format: str,
        battle_type: str = "double",  # "single" or "double"
        player_team: Optional[List[str]] = None,
        opponent_team: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        バトル開始を記録
        
        Args:
            battle_id: バトルID
            battle_tag: バトルタグ（Showdown形式）
            player_name: 観戦対象プレイヤー名
            opponent_name: 相手プレイヤー名
            format: バトルフォーマット（例: "gen9vgc2025regf"）
            battle_type: バトル形式（"single" or "double"）
            player_team: プレイヤーのチーム（ポケモン名のリスト）
            opponent_team: 相手のチーム（ポケモン名のリスト）
        
        Returns:
            保存されたレコードのID（後で実装）
        """
        battle_data = {
            "battle_id": battle_id,
            "battle_tag": battle_tag,
            "player_name": player_name,
            "opponent_name": opponent_name,
            "format": format,
            "battle_type": battle_type,
            "player_team": player_team or [],
            "opponent_team": opponent_team or [],
            "started_at": datetime.utcnow().isoformat(),
            "status": "in_progress",
        }
        
        try:
            # #region agent log
            import json
            try:
                log_data = {
                    "location": "battle_history_repository.py:save_battle_start",
                    "message": "Calling supabase.insert_battle_history",
                    "data": {
                        "battle_id": battle_id,
                        "supabase_enabled": getattr(self.supabase, 'enabled', False),
                    },
                    "timestamp": __import__('time').time(),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "C"
                }
                with open("/Users/kawashimawataru/Desktop/new_watch_game_system/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            
            record_id = await self.supabase.insert_battle_history(battle_data)
            
            # #region agent log
            try:
                log_data = {
                    "location": "battle_history_repository.py:save_battle_start",
                    "message": "insert_battle_history returned",
                    "data": {
                        "record_id": record_id,
                    },
                    "timestamp": __import__('time').time(),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "C"
                }
                with open("/Users/kawashimawataru/Desktop/new_watch_game_system/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            
            if record_id:
                logger.info(f"Battle start saved: {battle_id}")
            return record_id
        except Exception as e:
            # #region agent log
            try:
                log_data = {
                    "location": "battle_history_repository.py:save_battle_start",
                    "message": "Exception in save_battle_start",
                    "data": {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    "timestamp": __import__('time').time(),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "E"
                }
                with open("/Users/kawashimawataru/Desktop/new_watch_game_system/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            logger.error(f"Failed to save battle start: {e}", exc_info=True)
            return None
    
    async def save_turn_analysis(
        self,
        battle_id: str,
        turn: int,
        win_rate: float,
        board_score: Optional[float] = None,
        candidates: Optional[List[Dict[str, Any]]] = None,
        explanation: Optional[Dict[str, Any]] = None,
        field_conditions: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        ターン分析結果を記録
        
        Args:
            battle_id: バトルID
            turn: ターン数
            win_rate: 勝率（0.0-1.0）
            board_score: 盤面スコア
            candidates: 候補手リスト
            explanation: AI解説
            field_conditions: フィールド状態
        
        Returns:
            成功したかどうか
        """
        turn_data = {
            "battle_id": battle_id,
            "turn": turn,
            "win_rate": win_rate,
            "board_score": board_score,
            "candidates": candidates or [],
            "explanation": explanation or {},
            "field_conditions": field_conditions or {},
            "analyzed_at": datetime.utcnow().isoformat(),
        }
        
        try:
            # #region agent log
            import json
            try:
                log_data = {
                    "location": "battle_history_repository.py:save_turn_analysis",
                    "message": "Calling supabase.insert_turn_analysis",
                    "data": {
                        "battle_id": battle_id,
                        "turn": turn,
                        "supabase_enabled": getattr(self.supabase, 'enabled', False),
                    },
                    "timestamp": __import__('time').time(),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "D"
                }
                with open("/Users/kawashimawataru/Desktop/new_watch_game_system/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            
            record_id = await self.supabase.insert_turn_analysis(turn_data)
            
            # #region agent log
            try:
                log_data = {
                    "location": "battle_history_repository.py:save_turn_analysis",
                    "message": "insert_turn_analysis returned",
                    "data": {
                        "record_id": record_id,
                    },
                    "timestamp": __import__('time').time(),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "D"
                }
                with open("/Users/kawashimawataru/Desktop/new_watch_game_system/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            
            if record_id:
                logger.info(f"Turn analysis saved: battle={battle_id}, turn={turn}, win_rate={win_rate:.2%}")
            else:
                logger.debug(f"Turn analysis recorded (not saved to Supabase): battle={battle_id}, turn={turn}, win_rate={win_rate:.2%}")
            return True
        except Exception as e:
            # #region agent log
            try:
                log_data = {
                    "location": "battle_history_repository.py:save_turn_analysis",
                    "message": "Exception in save_turn_analysis",
                    "data": {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    "timestamp": __import__('time').time(),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "E"
                }
                with open("/Users/kawashimawataru/Desktop/new_watch_game_system/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            logger.error(f"Failed to save turn analysis: {e}", exc_info=True)
            return False
    
    async def save_battle_end(
        self,
        battle_id: str,
        winner: Optional[str] = None,  # "player" or "opponent" or None
        total_turns: int = 0,
        final_win_rate: Optional[float] = None,
    ) -> bool:
        """
        バトル終了を記録
        
        Args:
            battle_id: バトルID
            winner: 勝者（"player" or "opponent"）
            total_turns: 総ターン数
            final_win_rate: 最終勝率
        
        Returns:
            成功したかどうか
        """
        updates = {
            "status": "completed",
            "winner": winner,
            "total_turns": total_turns,
            "final_win_rate": final_win_rate,
            "ended_at": datetime.utcnow().isoformat(),
        }
        
        try:
            success = await self.supabase.update_battle_history(battle_id, updates)
            if success:
                logger.info(f"Battle end saved: {battle_id}, winner={winner}")
            return success
        except Exception as e:
            logger.error(f"Failed to save battle end: {e}", exc_info=True)
            return False
    
    async def get_battle_history(
        self,
        player_name: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        バトル履歴を取得
        
        Args:
            player_name: プレイヤー名でフィルタ
            limit: 取得件数
            offset: オフセット
        
        Returns:
            バトル履歴のリスト
        """
        try:
            history = await self.supabase.get_battle_history(
                player_name=player_name,
                limit=limit,
                offset=offset,
            )
            return history
        except Exception as e:
            logger.error(f"Failed to get battle history: {e}", exc_info=True)
            return []


# シングルトンインスタンス
_battle_history_repository: Optional[BattleHistoryRepository] = None


def get_battle_history_repository() -> BattleHistoryRepository:
    """バトル履歴リポジトリを取得（シングルトン）"""
    global _battle_history_repository
    if _battle_history_repository is None:
        _battle_history_repository = BattleHistoryRepository()
    return _battle_history_repository
