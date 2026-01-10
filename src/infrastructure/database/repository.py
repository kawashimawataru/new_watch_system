"""
試合データベース - Repository

CRUD 操作を提供。
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
import json

from sqlalchemy.orm import Session

from .models import Battle, Turn, PokemonSnapshot
from .session import DatabaseSession, get_session


# ============================================================================
# BattleRepository
# ============================================================================

class BattleRepository:
    """試合の CRUD"""
    
    @staticmethod
    def create(
        battle_id: str,
        format: str,
        opponent_name: str,
        my_team: List[dict],
        opp_team: List[dict],
        game_plan: dict = None,
        session: Session = None
    ) -> str:
        """新しい試合を作成（battle_id を返す）"""
        close_session = False
        if session is None:
            session = get_session()
            close_session = True
        
        battle = Battle(
            id=battle_id,
            format=format,
            started_at=datetime.now(),
            opponent_name=opponent_name,
            my_team_json=json.dumps(my_team, ensure_ascii=False),
            opp_team_json=json.dumps(opp_team, ensure_ascii=False),
            game_plan_json=json.dumps(game_plan or {}, ensure_ascii=False),
        )
        
        session.add(battle)
        session.commit()
        
        if close_session:
            session.close()
        
        return battle_id
    
    @staticmethod
    def get(battle_id: str) -> Optional[Battle]:
        """試合を取得"""
        with DatabaseSession() as session:
            return session.query(Battle).filter(Battle.id == battle_id).first()
    
    @staticmethod
    def update_result(
        battle_id: str,
        result: str,
        total_turns: int,
        my_remaining: int,
        opp_remaining: int
    ):
        """試合結果を更新"""
        with DatabaseSession() as session:
            battle = session.query(Battle).filter(Battle.id == battle_id).first()
            if battle:
                battle.result = result
                battle.ended_at = datetime.now()
                battle.total_turns = total_turns
                battle.final_my_remaining = my_remaining
                battle.final_opp_remaining = opp_remaining
    
    @staticmethod
    def list_all(limit: int = 100) -> List[Battle]:
        """全試合を取得（最新順）"""
        with DatabaseSession() as session:
            return session.query(Battle).order_by(Battle.started_at.desc()).limit(limit).all()
    
    @staticmethod
    def list_by_result(result: str, limit: int = 100) -> List[Battle]:
        """結果別に試合を取得"""
        with DatabaseSession() as session:
            return session.query(Battle).filter(Battle.result == result).order_by(Battle.started_at.desc()).limit(limit).all()


# ============================================================================
# TurnRepository
# ============================================================================

class TurnRepository:
    """ターンの CRUD"""
    
    @staticmethod
    def create(
        battle_id: str,
        turn_number: int,
        my_active: List[dict],
        opp_active: List[dict],
        my_bench: List[dict] = None,
        opp_bench: List[dict] = None,
        predicted_win_prob: float = None,
        predicted_my_action: dict = None,
        predicted_opp_action: dict = None,
        risk_mode: str = None,
        advisor_recommendation: dict = None,
        prediction_time_ms: int = None,
        session: Session = None
    ) -> Turn:
        """新しいターンを作成"""
        close_session = False
        if session is None:
            session = get_session()
            close_session = True
        
        turn = Turn(
            battle_id=battle_id,
            turn_number=turn_number,
            my_active_json=json.dumps(my_active, ensure_ascii=False),
            opp_active_json=json.dumps(opp_active, ensure_ascii=False),
            my_bench_json=json.dumps(my_bench or [], ensure_ascii=False),
            opp_bench_json=json.dumps(opp_bench or [], ensure_ascii=False),
            predicted_win_prob=predicted_win_prob,
            predicted_my_action_json=json.dumps(predicted_my_action or {}, ensure_ascii=False),
            predicted_opp_action_json=json.dumps(predicted_opp_action or {}, ensure_ascii=False),
            risk_mode=risk_mode,
            advisor_recommendation_json=json.dumps(advisor_recommendation or {}, ensure_ascii=False),
            prediction_time_ms=prediction_time_ms,
        )
        
        session.add(turn)
        session.commit()
        
        turn_id = turn.id
        
        if close_session:
            session.close()
        
        return turn
    
    @staticmethod
    def update_actual_actions(
        turn_id: int,
        actual_my_action: dict,
        actual_opp_action: dict,
        ko_happened: bool = False,
        damage_dealt: dict = None,
        damage_received: dict = None
    ):
        """実際の行動を記録"""
        with DatabaseSession() as session:
            turn = session.query(Turn).filter(Turn.id == turn_id).first()
            if turn:
                turn.actual_my_action_json = json.dumps(actual_my_action, ensure_ascii=False)
                turn.actual_opp_action_json = json.dumps(actual_opp_action, ensure_ascii=False)
                turn.ko_happened = ko_happened
                turn.damage_dealt_json = json.dumps(damage_dealt or {}, ensure_ascii=False)
                turn.damage_received_json = json.dumps(damage_received or {}, ensure_ascii=False)
    
    @staticmethod
    def get_by_battle(battle_id: str) -> List[Turn]:
        """試合のターンを取得"""
        with DatabaseSession() as session:
            return session.query(Turn).filter(Turn.battle_id == battle_id).order_by(Turn.turn_number).all()


# ============================================================================
# PokemonSnapshotRepository
# ============================================================================

class PokemonSnapshotRepository:
    """ポケモンスナップショットの CRUD"""
    
    @staticmethod
    def create_batch(
        turn_id: int,
        snapshots: List[dict],
        session: Session = None
    ):
        """複数のスナップショットを一括作成"""
        close_session = False
        if session is None:
            session = get_session()
            close_session = True
        
        for snap in snapshots:
            pokemon = PokemonSnapshot(
                turn_id=turn_id,
                slot=snap.get("slot"),
                species=snap.get("species"),
                hp_current=snap.get("hp_current"),
                hp_max=snap.get("hp_max"),
                hp_percent=snap.get("hp_percent"),
                status=snap.get("status"),
                item=snap.get("item"),
                ability=snap.get("ability"),
                tera_type=snap.get("tera_type"),
                tera_used=snap.get("tera_used"),
                moves_json=json.dumps(snap.get("moves", []), ensure_ascii=False),
                stats_json=json.dumps(snap.get("stats", {}), ensure_ascii=False),
                evs_json=json.dumps(snap.get("evs", {}), ensure_ascii=False),
            )
            session.add(pokemon)
        
        session.commit()
        
        if close_session:
            session.close()
    
    @staticmethod
    def get_by_turn(turn_id: int) -> List[PokemonSnapshot]:
        """ターンのスナップショットを取得"""
        with DatabaseSession() as session:
            return session.query(PokemonSnapshot).filter(PokemonSnapshot.turn_id == turn_id).all()
