"""
データベースセッション管理

SQLite データベースへの接続とセッション管理。
"""

from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base


# データベースファイルのパス
DATABASE_PATH = Path(__file__).resolve().parents[3] / "data" / "battles.db"

# エンジンとセッション
_engine = None
_SessionLocal = None


def get_engine():
    """データベースエンジンを取得（シングルトン）"""
    global _engine
    if _engine is None:
        # data ディレクトリを作成
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # SQLite エンジンを作成
        _engine = create_engine(
            f"sqlite:///{DATABASE_PATH}",
            echo=False,  # SQLログを出力しない
            connect_args={"check_same_thread": False}  # マルチスレッド対応
        )
        
        # テーブルを作成
        Base.metadata.create_all(_engine)
        
    return _engine


def get_session() -> Session:
    """新しいセッションを取得"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            expire_on_commit=False  # コミット後も属性にアクセス可能
        )
    return _SessionLocal()


class DatabaseSession:
    """
    コンテキストマネージャー版セッション
    
    使用例:
    ```python
    with DatabaseSession() as session:
        battle = Battle(id="xxx", ...)
        session.add(battle)
    ```
    """
    
    def __init__(self):
        self.session = None
    
    def __enter__(self) -> Session:
        self.session = get_session()
        return self.session
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.session.rollback()
        else:
            self.session.commit()
        self.session.close()


def init_database():
    """データベースを初期化（テーブル作成）"""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print(f"✅ Database initialized at: {DATABASE_PATH}")
    return DATABASE_PATH
