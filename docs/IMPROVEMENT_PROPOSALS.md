# プロジェクト改善提案

**作成日**: 2026-01-12  
**対象**: VGC AI Spectator プロジェクト全体

---

## 📋 目次

1. [ロギングの統一化](#1-ロギングの統一化)
2. [エラーハンドリングの改善](#2-エラーハンドリングの改善)
3. [設定管理の改善](#3-設定管理の改善)
4. [コード品質の向上](#4-コード品質の向上)
5. [パフォーマンス最適化](#5-パフォーマンス最適化)
6. [テストカバレッジの向上](#6-テストカバレッジの向上)
7. [型安全性の向上](#7-型安全性の向上)
8. [ドキュメントの充実](#8-ドキュメントの充実)

---

## 1. ロギングの統一化

### 🔴 優先度: 高

### 現状の問題

- `print()` 文が245箇所以上で使用されている
- ログレベルが統一されていない
- デバッグ情報と本番ログが混在している

### 影響

- 本番環境でのログ管理が困難
- デバッグ時の情報が不足
- パフォーマンスへの影響（printは同期的）

### 提案

#### 1.1 統一ロガーモジュールの作成

```python
# src/infrastructure/logging/logger.py
import logging
import sys
from pathlib import Path
from typing import Optional

class ProjectLogger:
    """プロジェクト統一ロガー"""
    
    _instance: Optional['ProjectLogger'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.logger = logging.getLogger("vgc_ai_spectator")
        self.logger.setLevel(logging.DEBUG)
        
        # コンソールハンドラー
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_format)
        
        # ファイルハンドラー
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "spectator.log")
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        file_handler.setFormatter(file_format)
        
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        self._initialized = True
    
    def get_logger(self, name: str = None) -> logging.Logger:
        if name:
            return self.logger.getChild(name)
        return self.logger

def get_logger(name: str = None) -> logging.Logger:
    """ロガー取得ヘルパー"""
    return ProjectLogger().get_logger(name)
```

#### 1.2 既存コードの置き換え例

**Before** (`src/infrastructure/messaging/broker.py`):
```python
print(f"📡 New spectator connected. Total: {len(self.active_connections)}")
```

**After**:
```python
from src.infrastructure.logging.logger import get_logger

logger = get_logger("broker")
logger.info(f"New spectator connected. Total: {len(self.active_connections)}")
```

#### 1.3 移行計画

1. ロガーモジュール作成
2. 主要ファイルから順次置き換え:
   - `src/infrastructure/messaging/broker.py`
   - `src/interfaces/api/server.py`
   - `src/application/players/spectator.py`
   - `src/application/services/spectator_analyzer.py`
3. デバッグ用printは `logger.debug()` に統一

---

## 2. エラーハンドリングの改善

### 🟡 優先度: 中

### 現状の問題

- `except Exception as e: pass` のような不適切な処理が存在
- エラーメッセージが不十分
- エラー発生時のリカバリー処理が不足

### 提案

#### 2.1 カスタム例外クラスの定義

```python
# src/domain/exceptions.py
class VGCAIError(Exception):
    """ベース例外クラス"""
    pass

class BattleStateError(VGCAIError):
    """バトル状態エラー"""
    pass

class WebSocketError(VGCAIError):
    """WebSocket通信エラー"""
    pass

class AnalysisError(VGCAIError):
    """分析処理エラー"""
    pass
```

#### 2.2 エラーハンドリングの改善例

**Before** (`src/application/players/spectator.py:84`):
```python
except Exception as e:
    print(f"Error searching battles: {e}")
```

**After**:
```python
from src.domain.exceptions import WebSocketError
from src.infrastructure.logging.logger import get_logger

logger = get_logger("spectator")

try:
    # ...
except WebSocketError as e:
    logger.error(f"WebSocket error while searching battles: {e}", exc_info=True)
    # リトライロジックなど
except Exception as e:
    logger.exception(f"Unexpected error in battle search: {e}")
    raise
```

#### 2.3 リトライ機構の追加

```python
# src/infrastructure/utils/retry.py
from functools import wraps
from typing import Callable, TypeVar, Tuple
import time

T = TypeVar('T')

def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    exceptions: Tuple[Exception, ...] = (Exception,)
):
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay * (attempt + 1))
                    continue
            raise last_exception
        return wrapper
    return decorator
```

---

## 3. 設定管理の改善

### 🟡 優先度: 中

### 現状の問題

- 設定値がハードコードされている箇所が多い
- 環境変数の管理が不統一
- 設定ファイルが存在しない

### 提案

#### 3.1 設定管理モジュールの作成

```python
# src/infrastructure/config/settings.py
from dataclasses import dataclass
from typing import Optional
import os
from pathlib import Path

@dataclass
class DatabaseConfig:
    url: str = "sqlite:///data/battles.db"
    echo: bool = False

@dataclass
class WebSocketConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    max_connections: int = 100

@dataclass
class LLMConfig:
    provider: str = "openai"
    api_key: Optional[str] = None
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    timeout: float = 10.0

@dataclass
class SpectatorConfig:
    target_player: str = "VGC_AI"
    battle_search_interval: float = 2.0
    max_watched_battles: int = 10

@dataclass
class AppConfig:
    database: DatabaseConfig = None
    websocket: WebSocketConfig = None
    llm: LLMConfig = None
    spectator: SpectatorConfig = None
    
    def __post_init__(self):
        if self.database is None:
            self.database = DatabaseConfig()
        if self.websocket is None:
            self.websocket = WebSocketConfig()
        if self.llm is None:
            self.llm = LLMConfig(
                api_key=os.getenv("OPENAI_API_KEY")
            )
        if self.spectator is None:
            self.spectator = SpectatorConfig()

def load_config(config_path: Optional[Path] = None) -> AppConfig:
    """設定ファイルから読み込み（将来実装）"""
    # TODO: YAML/TOML から読み込み
    return AppConfig()

# グローバル設定インスタンス
config = load_config()
```

#### 3.2 環境変数の統一管理

```python
# src/infrastructure/config/env.py
import os
from typing import Optional

class Env:
    """環境変数アクセサ"""
    
    @staticmethod
    def get(key: str, default: Optional[str] = None, required: bool = False) -> str:
        value = os.getenv(key, default)
        if required and value is None:
            raise ValueError(f"Required environment variable {key} is not set")
        return value
    
    @staticmethod
    def get_int(key: str, default: Optional[int] = None) -> int:
        value = Env.get(key, default)
        return int(value) if value else default
    
    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        value = Env.get(key, str(default))
        return value.lower() in ("true", "1", "yes", "on")
```

---

## 4. コード品質の向上

### 🟢 優先度: 低

### 4.1 型ヒントの充実

**現状**: 一部の関数で型ヒントが不足

**提案**: すべての公開関数に型ヒントを追加

```python
# Before
def analyze(self, player_active, opponent_active, ...):
    ...

# After
from typing import List, Dict, Any, Optional

def analyze(
    self,
    player_active: List[Dict[str, Any]],
    opponent_active: List[Dict[str, Any]],
    player_bench: Optional[List[Dict[str, Any]]] = None,
    ...
) -> SpectatorAnalysis:
    ...
```

### 4.2 ドキュメント文字列の統一

**現状**: 一部の関数にdocstringが不足

**提案**: Google形式のdocstringを統一

```python
def analyze(
    self,
    player_active: List[Dict[str, Any]],
    ...
) -> SpectatorAnalysis:
    """
    盤面を分析して候補手と解説を生成する。
    
    Args:
        player_active: 自分の場のポケモン情報のリスト
        opponent_active: 相手の場のポケモン情報のリスト
        ...
    
    Returns:
        SpectatorAnalysis: 分析結果
    
    Raises:
        AnalysisError: 分析処理中にエラーが発生した場合
    
    Example:
        >>> analyzer = SpectatorAnalyzer()
        >>> result = analyzer.analyze(
        ...     player_active=[{"name": "Pikachu", "hp": 0.8}],
        ...     opponent_active=[{"name": "Charizard", "hp": 0.6}]
        ... )
        >>> print(result.win_rate)
        0.65
    """
```

### 4.3 コードの重複排除

**発見された重複**:
- ポケモン情報抽出ロジックが複数箇所に存在
- フィールド状態抽出ロジックが重複

**提案**: 共通ユーティリティ関数の作成

```python
# src/domain/utils/pokemon_extractor.py
class PokemonExtractor:
    """ポケモン情報抽出ユーティリティ"""
    
    @staticmethod
    def extract_active_pokemon(battle: Battle, is_player: bool) -> List[Dict[str, Any]]:
        """統一されたアクティブポケモン抽出"""
        # 実装
        pass
    
    @staticmethod
    def extract_bench_pokemon(battle: Battle, is_player: bool) -> List[Dict[str, Any]]:
        """統一された控えポケモン抽出"""
        # 実装
        pass
```

---

## 5. パフォーマンス最適化

### 🟡 優先度: 中

### 5.1 WebSocketブロードキャストの最適化

**現状**: 同期的なブロードキャスト

**提案**: 非同期バッチ処理

```python
# src/infrastructure/messaging/broker.py
import asyncio
from collections import deque

class MessageBroker:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.message_queue: deque = deque()
        self._broadcast_task: Optional[asyncio.Task] = None
    
    async def _broadcast_worker(self):
        """バッチブロードキャストワーカー"""
        while True:
            if self.message_queue:
                messages = []
                while self.message_queue:
                    messages.append(self.message_queue.popleft())
                
                # バッチ送信
                tasks = []
                for connection in self.active_connections:
                    for message in messages:
                        tasks.append(self._send_safe(connection, message))
                
                await asyncio.gather(*tasks, return_exceptions=True)
            
            await asyncio.sleep(0.1)  # 100ms間隔
    
    async def broadcast(self, message: dict):
        """メッセージをキューに追加"""
        self.message_queue.append(message)
        if self._broadcast_task is None:
            self._broadcast_task = asyncio.create_task(self._broadcast_worker())
```

### 5.2 キャッシュ機構の追加

**提案**: よく使われる計算結果をキャッシュ

```python
# src/infrastructure/cache/cache.py
from functools import lru_cache
from typing import Callable, Any
import hashlib
import json

class CacheManager:
    """キャッシュマネージャー"""
    
    def __init__(self, max_size: int = 128):
        self._cache: Dict[str, Any] = {}
        self.max_size = max_size
    
    def cache_key(self, *args, **kwargs) -> str:
        """引数からキャッシュキーを生成"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def cached(self, func: Callable) -> Callable:
        """デコレータ: 関数結果をキャッシュ"""
        def wrapper(*args, **kwargs):
            key = self.cache_key(*args, **kwargs)
            if key in self._cache:
                return self._cache[key]
            
            result = func(*args, **kwargs)
            if len(self._cache) >= self.max_size:
                # LRU: 最初の要素を削除
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = result
            return result
        return wrapper
```

---

## 6. テストカバレッジの向上

### 🟡 優先度: 中

### 現状

- テストファイルは存在するが、カバレッジが不明
- 統合テストが不足している可能性

### 提案

#### 6.1 テストカバレッジの測定

```bash
# pytest-cov の導入
pip install pytest-cov

# カバレッジ測定
pytest --cov=src --cov-report=html --cov-report=term
```

#### 6.2 統合テストの追加

```python
# tests/integration/test_spectator_flow.py
import pytest
from src.application.players.spectator import Spectator
from src.infrastructure.messaging.broker import get_message_broker

@pytest.mark.asyncio
async def test_spectator_broadcast():
    """観戦エージェントのブロードキャストテスト"""
    broker = get_message_broker()
    # テスト実装
    pass
```

#### 6.3 モックの活用

```python
# tests/unit/test_spectator_analyzer.py
from unittest.mock import Mock, patch
from src.application.services.spectator_analyzer import SpectatorAnalyzer

def test_analyze_with_mock():
    """モックを使った分析テスト"""
    analyzer = SpectatorAnalyzer(use_llm=False)
    
    with patch.object(analyzer.candidate_scorer, 'score_candidates') as mock_score:
        mock_score.return_value = []
        # テスト実装
        pass
```

---

## 7. 型安全性の向上

### 🟢 優先度: 低

### 7.1 Pydanticモデルの導入

**提案**: データ検証の強化

```python
# src/domain/models/spectator_models.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional

class ActivePokemon(BaseModel):
    name: str = Field(..., description="ポケモン名")
    hp_fraction: float = Field(..., ge=0.0, le=1.0, description="HP割合")
    types: List[str] = Field(default_factory=list)
    moves: List[dict] = Field(default_factory=list)
    speed: int = Field(default=100, ge=0)
    fainted: bool = False
    
    @validator('name')
    def validate_name(cls, v):
        if not v or v == "Unknown":
            raise ValueError("Invalid pokemon name")
        return v

class SpectatorAnalysisRequest(BaseModel):
    player_active: List[ActivePokemon]
    opponent_active: List[ActivePokemon]
    turn: int = Field(..., ge=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "player_active": [{"name": "Pikachu", "hp_fraction": 0.8}],
                "opponent_active": [{"name": "Charizard", "hp_fraction": 0.6}],
                "turn": 1
            }
        }
```

### 7.2 mypyの導入

```bash
# mypy の導入
pip install mypy

# 型チェック
mypy src/
```

---

## 8. ドキュメントの充実

### 🟢 優先度: 低

### 8.1 APIドキュメントの自動生成

**提案**: FastAPIの自動ドキュメント機能を活用

```python
# src/interfaces/api/server.py
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="VGC AI Spectator API",
    description="VGCバトル観戦AIシステムのAPI",
    version="1.0.0"
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="VGC AI Spectator API",
        version="1.0.0",
        description="...",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

### 8.2 コード例の追加

**提案**: READMEに実行例を追加

```markdown
## 実行例

### 基本的な観戦

```python
from src.application.players.spectator import Spectator

spectator = Spectator(target_player="VGC_AI")
await spectator.run_loop()
```

### カスタム設定

```python
from src.infrastructure.config.settings import config

config.spectator.battle_search_interval = 5.0
config.llm.temperature = 0.5
```
```

---

## 📊 優先度マトリックス

| 改善項目 | 優先度 | 工数 | 影響度 | 実装順序 |
|---------|--------|------|--------|---------|
| ロギング統一化 | 🔴 高 | 中 | 高 | 1 |
| エラーハンドリング | 🟡 中 | 中 | 中 | 2 |
| 設定管理 | 🟡 中 | 低 | 中 | 3 |
| パフォーマンス最適化 | 🟡 中 | 高 | 中 | 4 |
| テストカバレッジ | 🟡 中 | 高 | 高 | 5 |
| 型安全性 | 🟢 低 | 中 | 低 | 6 |
| コード品質 | 🟢 低 | 中 | 低 | 7 |
| ドキュメント | 🟢 低 | 低 | 低 | 8 |

---

## 🚀 実装ロードマップ

### Phase 1: 基盤整備 (1-2週間)
1. ロギングモジュール作成
2. 設定管理モジュール作成
3. カスタム例外クラス定義

### Phase 2: コード改善 (2-3週間)
1. 主要ファイルのロギング置き換え
2. エラーハンドリング改善
3. 設定値の外部化

### Phase 3: 品質向上 (2-3週間)
1. テストカバレッジ向上
2. 型ヒント追加
3. ドキュメント整備

### Phase 4: 最適化 (1-2週間)
1. パフォーマンス最適化
2. キャッシュ機構追加
3. プロファイリングと改善

---

## 📝 まとめ

このプロジェクトは全体的によく設計されていますが、以下の点で改善の余地があります：

1. **ロギング**: print文を統一ロガーに置き換えることで、運用性が大幅に向上
2. **エラーハンドリング**: 適切な例外処理とリカバリー機構の追加
3. **設定管理**: ハードコードされた値を外部化し、環境ごとの設定を可能に
4. **テスト**: カバレッジを測定し、不足している部分を補完

これらの改善により、保守性、拡張性、運用性が向上し、本番環境での安定稼働が可能になります。
