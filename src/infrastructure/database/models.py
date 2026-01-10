"""
試合データベース - SQLAlchemy モデル定義

試合情報、ターン情報、ポケモン詳細を保存するためのモデル。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
import json

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey,
    create_engine
)
from sqlalchemy.orm import declarative_base, relationship, Session

Base = declarative_base()


# ============================================================================
# Battle（試合）
# ============================================================================

class Battle(Base):
    """試合情報"""
    __tablename__ = "battles"
    
    id = Column(String, primary_key=True)  # battle_tag
    format = Column(String)                 # gen9vgc2026regfbo3
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    result = Column(String)                 # win / lose / tie
    opponent_name = Column(String)
    
    # 自分のチーム（JSON）
    my_team_json = Column(Text)
    
    # 相手のチーム（JSON）
    opp_team_json = Column(Text)
    
    # ゲームプラン（JSON）
    game_plan_json = Column(Text)
    
    # 統計
    total_turns = Column(Integer)
    final_my_remaining = Column(Integer)    # 残りポケモン数
    final_opp_remaining = Column(Integer)
    
    # リレーション
    turns = relationship("Turn", back_populates="battle", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Battle {self.id} vs {self.opponent_name} ({self.result})>"
    
    @property
    def my_team(self) -> List[dict]:
        """自分のチームをパース"""
        return json.loads(self.my_team_json) if self.my_team_json else []
    
    @my_team.setter
    def my_team(self, value: List[dict]):
        self.my_team_json = json.dumps(value, ensure_ascii=False)
    
    @property
    def opp_team(self) -> List[dict]:
        """相手のチームをパース"""
        return json.loads(self.opp_team_json) if self.opp_team_json else []
    
    @opp_team.setter
    def opp_team(self, value: List[dict]):
        self.opp_team_json = json.dumps(value, ensure_ascii=False)
    
    @property
    def game_plan(self) -> dict:
        """ゲームプランをパース"""
        return json.loads(self.game_plan_json) if self.game_plan_json else {}
    
    @game_plan.setter
    def game_plan(self, value: dict):
        self.game_plan_json = json.dumps(value, ensure_ascii=False)


# ============================================================================
# Turn（ターン）
# ============================================================================

class Turn(Base):
    """ターン情報"""
    __tablename__ = "turns"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    battle_id = Column(String, ForeignKey("battles.id"), nullable=False)
    turn_number = Column(Integer)
    
    # 盤面状態（JSON）
    my_active_json = Column(Text)           # アクティブ2体
    opp_active_json = Column(Text)
    my_bench_json = Column(Text)            # 控え4体
    opp_bench_json = Column(Text)
    
    # 予測
    predicted_win_prob = Column(Float)      # 勝率予測
    predicted_my_action_json = Column(Text) # 予測した自分の行動
    predicted_opp_action_json = Column(Text)# 予測した相手の行動
    risk_mode = Column(String)              # secure / neutral / gamble
    
    # TurnAdvisor 推奨（JSON）
    advisor_recommendation_json = Column(Text)
    
    # 実際の動き（JSON）
    actual_my_action_json = Column(Text)
    actual_opp_action_json = Column(Text)
    
    # 結果
    ko_happened = Column(Boolean)           # KOが発生したか
    damage_dealt_json = Column(Text)        # 与えたダメージ
    damage_received_json = Column(Text)     # 受けたダメージ
    
    # 処理時間
    prediction_time_ms = Column(Integer)
    
    # リレーション
    battle = relationship("Battle", back_populates="turns")
    pokemon_snapshots = relationship("PokemonSnapshot", back_populates="turn", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Turn {self.battle_id} T{self.turn_number} WinProb={self.predicted_win_prob:.1%}>"
    
    @property
    def my_active(self) -> List[dict]:
        return json.loads(self.my_active_json) if self.my_active_json else []
    
    @my_active.setter
    def my_active(self, value: List[dict]):
        self.my_active_json = json.dumps(value, ensure_ascii=False)
    
    @property
    def opp_active(self) -> List[dict]:
        return json.loads(self.opp_active_json) if self.opp_active_json else []
    
    @opp_active.setter
    def opp_active(self, value: List[dict]):
        self.opp_active_json = json.dumps(value, ensure_ascii=False)
    
    @property
    def predicted_my_action(self) -> dict:
        return json.loads(self.predicted_my_action_json) if self.predicted_my_action_json else {}
    
    @predicted_my_action.setter
    def predicted_my_action(self, value: dict):
        self.predicted_my_action_json = json.dumps(value, ensure_ascii=False)
    
    @property
    def predicted_opp_action(self) -> dict:
        return json.loads(self.predicted_opp_action_json) if self.predicted_opp_action_json else {}
    
    @predicted_opp_action.setter
    def predicted_opp_action(self, value: dict):
        self.predicted_opp_action_json = json.dumps(value, ensure_ascii=False)
    
    @property
    def advisor_recommendation(self) -> dict:
        return json.loads(self.advisor_recommendation_json) if self.advisor_recommendation_json else {}
    
    @advisor_recommendation.setter
    def advisor_recommendation(self, value: dict):
        self.advisor_recommendation_json = json.dumps(value, ensure_ascii=False)
    
    @property
    def actual_my_action(self) -> dict:
        return json.loads(self.actual_my_action_json) if self.actual_my_action_json else {}
    
    @actual_my_action.setter
    def actual_my_action(self, value: dict):
        self.actual_my_action_json = json.dumps(value, ensure_ascii=False)
    
    @property
    def actual_opp_action(self) -> dict:
        return json.loads(self.actual_opp_action_json) if self.actual_opp_action_json else {}
    
    @actual_opp_action.setter
    def actual_opp_action(self, value: dict):
        self.actual_opp_action_json = json.dumps(value, ensure_ascii=False)


# ============================================================================
# PokemonSnapshot（ポケモン詳細）
# ============================================================================

class PokemonSnapshot(Base):
    """ポケモンのスナップショット"""
    __tablename__ = "pokemon_snapshots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    turn_id = Column(Integer, ForeignKey("turns.id"), nullable=False)
    slot = Column(String)                   # my_0, my_1, opp_0, opp_1, bench_0, etc
    
    species = Column(String)
    hp_current = Column(Integer)
    hp_max = Column(Integer)
    hp_percent = Column(Float)
    
    status = Column(String)                 # brn, par, slp, etc
    item = Column(String)
    ability = Column(String)
    tera_type = Column(String)
    tera_used = Column(Boolean)
    
    # 技（JSON）
    moves_json = Column(Text)
    
    # 実数値（JSON）
    stats_json = Column(Text)
    
    # 努力値（JSON、推定含む）
    evs_json = Column(Text)
    
    # リレーション
    turn = relationship("Turn", back_populates="pokemon_snapshots")
    
    def __repr__(self):
        return f"<PokemonSnapshot {self.species} {self.slot} HP={self.hp_percent:.0f}%>"
    
    @property
    def moves(self) -> List[str]:
        return json.loads(self.moves_json) if self.moves_json else []
    
    @moves.setter
    def moves(self, value: List[str]):
        self.moves_json = json.dumps(value, ensure_ascii=False)
    
    @property
    def stats(self) -> dict:
        return json.loads(self.stats_json) if self.stats_json else {}
    
    @stats.setter
    def stats(self, value: dict):
        self.stats_json = json.dumps(value, ensure_ascii=False)
    
    @property
    def evs(self) -> dict:
        return json.loads(self.evs_json) if self.evs_json else {}
    
    @evs.setter
    def evs(self, value: dict):
        self.evs_json = json.dumps(value, ensure_ascii=False)
