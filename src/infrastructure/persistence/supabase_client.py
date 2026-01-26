"""
Supabase Client

Supabase接続クライアント（後で接続実装）
"""
from typing import Optional, Dict, Any, List
from src.infrastructure.config import config
from src.infrastructure.logging import get_logger

logger = get_logger("supabase")


class SupabaseClient:
    """
    Supabaseクライアント
    
    後で接続実装を行うため、現在はスケルトン実装
    """
    
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        """
        Supabaseクライアントを初期化
        
        Args:
            url: Supabase URL
            key: Supabase API Key
        """
        # #region agent log
        import json
        import os
        try:
            has_supabase_attr = hasattr(config, 'supabase')
            log_data = {
                "location": "supabase_client.py:__init__",
                "message": "SupabaseClient initialization",
                "data": {
                    "has_supabase_attr": has_supabase_attr,
                    "config_type": str(type(config)),
                    "url_provided": url is not None,
                    "key_provided": key is not None,
                },
                "timestamp": __import__('time').time(),
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "A"
            }
            with open("/Users/kawashimawataru/Desktop/new_watch_game_system/.cursor/debug.log", "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion
        
        try:
            self.url = url or config.supabase.url
            self.key = key or config.supabase.key
            self.enabled = config.supabase.enabled
        except AttributeError as e:
            # #region agent log
            try:
                log_data = {
                    "location": "supabase_client.py:__init__",
                    "message": "AttributeError accessing config.supabase",
                    "data": {
                        "error": str(e),
                        "config_attrs": dir(config),
                    },
                    "timestamp": __import__('time').time(),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A"
                }
                with open("/Users/kawashimawataru/Desktop/new_watch_game_system/.cursor/debug.log", "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            # フォールバック
            self.url = url
            self.key = key
            self.enabled = False
        
        if not self.enabled:
            logger.warning("Supabase is not enabled. Set SUPABASE_URL and SUPABASE_KEY environment variables.")
            self._client = None
        else:
            # TODO: 後でSupabaseクライアントを初期化
            # from supabase import create_client, Client
            # self._client: Client = create_client(self.url, self.key)
            self._client = None
            logger.info(f"Supabase client initialized (URL: {self.url[:20]}...)")
    
    def is_connected(self) -> bool:
        """Supabaseに接続されているか"""
        return self.enabled and self._client is not None
    
    async def insert_battle_history(self, battle_data: Dict[str, Any]) -> Optional[str]:
        """
        バトル履歴を挿入
        
        Args:
            battle_data: バトルデータ
        
        Returns:
            挿入されたレコードのID（後で実装）
        """
        if not self.is_connected():
            logger.debug("Supabase not connected, skipping insert")
            return None
        
        # TODO: 後で実装
        # try:
        #     result = self._client.table("battle_history").insert(battle_data).execute()
        #     return result.data[0]["id"] if result.data else None
        # except Exception as e:
        #     logger.error(f"Failed to insert battle history: {e}", exc_info=True)
        #     return None
        
        logger.debug(f"Would insert battle history: {battle_data.get('battle_id', 'unknown')}")
        return None
    
    async def get_battle_history(
        self,
        player_name: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        バトル履歴を取得
        
        Args:
            player_name: プレイヤー名でフィルタ
            limit: 取得件数
            offset: オフセット
        
        Returns:
            バトル履歴のリスト（後で実装）
        """
        if not self.is_connected():
            logger.debug("Supabase not connected, returning empty list")
            return []
        
        # TODO: 後で実装
        # try:
        #     query = self._client.table("battle_history").select("*")
        #     if player_name:
        #         query = query.eq("player_name", player_name)
        #     query = query.order("created_at", desc=True).limit(limit).offset(offset)
        #     result = query.execute()
        #     return result.data or []
        # except Exception as e:
        #     logger.error(f"Failed to get battle history: {e}", exc_info=True)
        #     return []
        
        logger.debug(f"Would get battle history: player={player_name}, limit={limit}")
        return []
    
    async def update_battle_history(
        self,
        battle_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        バトル履歴を更新
        
        Args:
            battle_id: バトルID
            updates: 更新データ
        
        Returns:
            成功したかどうか（後で実装）
        """
        if not self.is_connected():
            logger.debug("Supabase not connected, skipping update")
            return False
        
        # TODO: 後で実装
        # try:
        #     result = self._client.table("battle_history").update(updates).eq("battle_id", battle_id).execute()
        #     return len(result.data) > 0
        # except Exception as e:
        #     logger.error(f"Failed to update battle history: {e}", exc_info=True)
        #     return False
        
        logger.debug(f"Would update battle history: {battle_id}")
        return False
    
    async def insert_turn_analysis(self, turn_data: Dict[str, Any]) -> Optional[str]:
        """
        ターン分析を挿入
        
        Args:
            turn_data: ターン分析データ
        
        Returns:
            挿入されたレコードのID（後で実装）
        """
        if not self.is_connected():
            logger.debug("Supabase not connected, skipping turn analysis insert")
            return None
        
        # TODO: 後で実装
        # try:
        #     result = self._client.table("turn_analysis").insert(turn_data).execute()
        #     return result.data[0]["id"] if result.data else None
        # except Exception as e:
        #     logger.error(f"Failed to insert turn analysis: {e}", exc_info=True)
        #     return None
        
        logger.debug(f"Would insert turn analysis: battle={turn_data.get('battle_id', 'unknown')}, turn={turn_data.get('turn', 'unknown')}")
        return None


# シングルトンインスタンス
_supabase_client: Optional[SupabaseClient] = None


def get_supabase_client() -> SupabaseClient:
    """Supabaseクライアントを取得（シングルトン）"""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
    return _supabase_client
