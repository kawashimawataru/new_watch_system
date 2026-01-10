"""
BattleRecorder - 試合記録サービス

試合中にリアルタイムでデータベースに情報を記録する。
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any, Optional
import json
import time

# poke-env のインポート
try:
    from poke_env.environment.double_battle import DoubleBattle
    from poke_env.environment.pokemon import Pokemon
except ImportError:
    DoubleBattle = None
    Pokemon = None

from src.infrastructure.database import (
    BattleRepository,
    TurnRepository,
    PokemonSnapshotRepository,
    init_database,
)


class BattleRecorder:
    """
    試合記録サービス
    
    使用例:
    ```python
    recorder = BattleRecorder()
    
    # 試合開始時
    recorder.start_battle(battle, my_team, opp_team, game_plan)
    
    # 各ターン
    recorder.record_turn(battle, turn_number, win_prob, ...)
    
    # 試合終了時
    recorder.end_battle(battle, result)
    ```
    """
    
    def __init__(self):
        # データベース初期化
        init_database()
        
        self._current_battle_id: Optional[str] = None
        self._current_turn_id: Optional[int] = None
        self._turn_start_time: Optional[float] = None
    
    def start_battle(
        self,
        battle: DoubleBattle,
        my_team: List[Dict[str, Any]],
        opp_team: List[Dict[str, Any]],
        game_plan: Dict[str, Any] = None
    ):
        """試合開始を記録"""
        battle_id = battle.battle_tag if battle else f"battle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        format_name = getattr(battle, 'format', 'unknown') if battle else 'unknown'
        opponent_name = battle.opponent_username if battle else 'unknown'
        
        BattleRepository.create(
            battle_id=battle_id,
            format=format_name,
            opponent_name=opponent_name,
            my_team=my_team,
            opp_team=opp_team,
            game_plan=game_plan,
        )
        
        self._current_battle_id = battle_id
        print(f"📝 Battle recording started: {battle_id}")
    
    def record_turn_start(
        self,
        battle: DoubleBattle,
        turn_number: int,
        predicted_win_prob: float = None,
        predicted_my_action: Dict[str, Any] = None,
        predicted_opp_action: Dict[str, Any] = None,
        risk_mode: str = None,
        advisor_recommendation: Dict[str, Any] = None,
    ) -> int:
        """
        ターン開始時の予測を記録
        
        Returns:
            turn_id: 作成されたターンのID
        """
        if not self._current_battle_id:
            print("⚠️ No active battle. Call start_battle first.")
            return None
        
        self._turn_start_time = time.time()
        
        # アクティブポケモンの情報を抽出
        my_active = self._extract_active_pokemon(battle, "self")
        opp_active = self._extract_active_pokemon(battle, "opp")
        my_bench = self._extract_bench_pokemon(battle, "self")
        opp_bench = self._extract_bench_pokemon(battle, "opp")
        
        turn = TurnRepository.create(
            battle_id=self._current_battle_id,
            turn_number=turn_number,
            my_active=my_active,
            opp_active=opp_active,
            my_bench=my_bench,
            opp_bench=opp_bench,
            predicted_win_prob=predicted_win_prob,
            predicted_my_action=predicted_my_action,
            predicted_opp_action=predicted_opp_action,
            risk_mode=risk_mode,
            advisor_recommendation=advisor_recommendation,
        )
        
        self._current_turn_id = turn.id
        
        # ポケモンスナップショットを記録
        snapshots = self._create_pokemon_snapshots(battle)
        if snapshots:
            PokemonSnapshotRepository.create_batch(turn.id, snapshots)
        
        return turn.id
    
    def record_turn_end(
        self,
        actual_my_action: Dict[str, Any],
        actual_opp_action: Dict[str, Any],
        ko_happened: bool = False,
        damage_dealt: Dict[str, Any] = None,
        damage_received: Dict[str, Any] = None,
    ):
        """ターン終了時の実際の行動を記録"""
        if not self._current_turn_id:
            return
        
        # 処理時間を計算
        prediction_time_ms = None
        if self._turn_start_time:
            prediction_time_ms = int((time.time() - self._turn_start_time) * 1000)
        
        TurnRepository.update_actual_actions(
            turn_id=self._current_turn_id,
            actual_my_action=actual_my_action,
            actual_opp_action=actual_opp_action,
            ko_happened=ko_happened,
            damage_dealt=damage_dealt,
            damage_received=damage_received,
        )
        
        self._current_turn_id = None
        self._turn_start_time = None
    
    def end_battle(
        self,
        battle: DoubleBattle,
        result: str,
    ):
        """試合終了を記録"""
        if not self._current_battle_id:
            return
        
        # 残りポケモン数を計算
        my_remaining = sum(1 for p in battle.team.values() if p and not p.fainted) if battle else 0
        opp_remaining = sum(1 for p in battle.opponent_team.values() if p and not p.fainted) if battle else 0
        total_turns = battle.turn if battle else 0
        
        BattleRepository.update_result(
            battle_id=self._current_battle_id,
            result=result,
            total_turns=total_turns,
            my_remaining=my_remaining,
            opp_remaining=opp_remaining,
        )
        
        print(f"📝 Battle recording ended: {self._current_battle_id} ({result})")
        self._current_battle_id = None
    
    def _extract_active_pokemon(self, battle: DoubleBattle, side: str) -> List[Dict]:
        """アクティブポケモンの情報を抽出"""
        if not battle:
            return []
        
        pokemon_list = battle.active_pokemon if side == "self" else battle.opponent_active_pokemon
        result = []
        
        for p in pokemon_list[:2]:
            if p:
                result.append(self._pokemon_to_dict(p))
            else:
                result.append(None)
        
        return result
    
    def _extract_bench_pokemon(self, battle: DoubleBattle, side: str) -> List[Dict]:
        """控えポケモンの情報を抽出"""
        if not battle:
            return []
        
        team = battle.team if side == "self" else battle.opponent_team
        active_ids = set()
        
        active_list = battle.active_pokemon if side == "self" else battle.opponent_active_pokemon
        for p in active_list[:2]:
            if p:
                active_ids.add(p.species)
        
        result = []
        for p in team.values():
            if p and p.species not in active_ids:
                result.append(self._pokemon_to_dict(p))
        
        return result
    
    def _pokemon_to_dict(self, pokemon: Pokemon) -> Dict:
        """ポケモンを辞書に変換"""
        if not pokemon:
            return None
        
        return {
            "species": pokemon.species,
            "hp_current": pokemon.current_hp,
            "hp_max": pokemon.max_hp,
            "hp_percent": pokemon.current_hp_fraction * 100 if pokemon.current_hp_fraction else 0,
            "status": str(pokemon.status) if pokemon.status else None,
            "item": pokemon.item if pokemon.item else None,
            "ability": pokemon.ability if pokemon.ability else None,
            "tera_type": str(pokemon.tera_type) if pokemon.tera_type else None,
            "tera_used": pokemon.terastallized if hasattr(pokemon, 'terastallized') else False,
            "moves": [m.id for m in pokemon.moves.values()] if pokemon.moves else [],
            "stats": pokemon.stats if hasattr(pokemon, 'stats') and pokemon.stats else {},
            "fainted": pokemon.fainted,
        }
    
    def _create_pokemon_snapshots(self, battle: DoubleBattle) -> List[Dict]:
        """全ポケモンのスナップショットを作成"""
        if not battle:
            return []
        
        snapshots = []
        
        # 自分のアクティブ
        for i, p in enumerate(battle.active_pokemon[:2]):
            if p:
                snap = self._pokemon_to_dict(p)
                snap["slot"] = f"my_{i}"
                snapshots.append(snap)
        
        # 相手のアクティブ
        for i, p in enumerate(battle.opponent_active_pokemon[:2]):
            if p:
                snap = self._pokemon_to_dict(p)
                snap["slot"] = f"opp_{i}"
                snapshots.append(snap)
        
        # 自分の控え
        active_species = {p.species for p in battle.active_pokemon[:2] if p}
        bench_idx = 0
        for p in battle.team.values():
            if p and p.species not in active_species:
                snap = self._pokemon_to_dict(p)
                snap["slot"] = f"my_bench_{bench_idx}"
                snapshots.append(snap)
                bench_idx += 1
        
        return snapshots


# シングルトン
_recorder: Optional[BattleRecorder] = None


def get_battle_recorder() -> BattleRecorder:
    """BattleRecorder のシングルトンを取得"""
    global _recorder
    if _recorder is None:
        _recorder = BattleRecorder()
    return _recorder
