"""
Spectator - 観戦エージェント

Pokemon Showdownのバトルを観戦し、AIによる分析結果をWebSocket経由で配信します。
"""
import asyncio
import json
import random
import string
from typing import Optional, Dict, List, Any

from poke_env.player import Player
from poke_env.battle import Battle
from poke_env.ps_client.server_configuration import LocalhostServerConfiguration

from predictor.player.hybrid_strategist import HybridStrategist
from predictor.core.models import (
    BattleState,
    PlayerState,
    PokemonBattleState,
    ActionCandidate
)
from src.infrastructure.logging import get_logger
from src.infrastructure.config import config
from src.domain.exceptions import SpectatorError, AnalysisError

logger = get_logger("spectator")


class Spectator(Player):
    """
    観戦エージェント
    
    ターゲットプレイヤーのバトルを自動検出して観戦し、
    各ターンの勝率予測と候補手をWebSocket経由で配信します。
    """
    
    def __init__(
        self,
        target_player: str,
        battle_id: Optional[str] = None,
        account_configuration=None,
        *,
        avatar: Optional[str] = None,
        log_level: Optional[int] = None,
        server_configuration=None,
        start_listening: bool = True,
    ):
        """
        観戦エージェントを初期化
        
        Args:
            target_player: 観戦対象のプレイヤー名
            battle_id: 手動でバトルIDを指定する場合
            account_configuration: アカウント設定
            avatar: アバター
            log_level: ログレベル
            server_configuration: サーバー設定
            start_listening: 接続を開始するか
        """
        super().__init__(
            account_configuration=account_configuration,
            avatar=avatar,
            log_level=log_level,
            server_configuration=server_configuration,
            start_listening=start_listening,
        )
        self.target_player = target_player
        self.manual_battle_id = battle_id
        self.watched_battles: set = set()
        self._win_rate_history: List[Dict] = []
        
        # 名前重複回避のためにランダムサフィックスを追加
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        self._custom_username = f"Spectator {suffix}"
        
        # HybridStrategistの初期化
        self.strategist = HybridStrategist(
            fast_model_path=config.spectator.fast_model_path,
            mcts_rollouts=config.spectator.mcts_rollouts,
            mcts_max_turns=config.spectator.mcts_max_turns
        )
        
        logger.info(f"観戦エージェント起動: ターゲット = {self.target_player} (As: {self._custom_username})")
        if self.manual_battle_id:
            logger.info(f"手動指定バトルID: {self.manual_battle_id}")

    async def _search_and_join_battles(self) -> None:
        """
        定期的にターゲットプレイヤーのバトルを検索して参加する
        """
        # 名前変更を試みる
        await self.ps_client.send_message("", f"/nick {self._custom_username}")
        await asyncio.sleep(1)
        
        # 手動でバトルIDが指定されている場合、直接参加
        if self.manual_battle_id:
            logger.info(f"バトルに参加中: {self.manual_battle_id}")
            await self.ps_client.send_message("", f"/join {self.manual_battle_id}")
            self.watched_battles.add(self.manual_battle_id)
            return
        
        # ロビーに参加
        await self.ps_client.send_message("", "/join lobby")
        
        query_idx = 100
        search_interval = config.spectator.battle_search_interval
        
        while True:
            try:
                await self.ps_client.send_message("", f"|/cmd roomlist {query_idx}")
                await self.ps_client.send_message("", f"|/cmd userdetails {self.target_player}")
                query_idx += 1
            except Exception as e:
                logger.warning(f"バトル検索中にエラー: {e}")
            
            await asyncio.sleep(search_interval)

    def _handle_message(self, message: str) -> None:
        """
        グローバルメッセージを含む全メッセージを処理
        
        Args:
            message: 受信メッセージ
        """
        # デバッグ: クエリレスポンスをログ
        if message.startswith("|queryresponse|"):
            logger.debug(f"Query response: {message[:100]}...")

        # roomlistのレスポンス解析
        if message.startswith("|queryresponse|roomlist|"):
            self._handle_roomlist_response(message)
            return

        # userdetailsのレスポンス解析
        if message.startswith("|queryresponse|userdetails|"):
            self._handle_userdetails_response(message)
            return

        # 親クラスの処理
        super()._handle_message(message)

    def _handle_roomlist_response(self, message: str) -> None:
        """roomlistレスポンスを処理"""
        try:
            parts = message.split("|")
            if len(parts) > 3:
                data_str = "|".join(parts[3:])
                data = json.loads(data_str)
                
                if "rooms" in data:
                    for room_id, room_data in data["rooms"].items():
                        self._check_and_join_battle(room_id, room_data)
        except json.JSONDecodeError as e:
            logger.warning(f"roomlist JSONパースエラー: {e}")
        except Exception as e:
            logger.error(f"roomlist処理エラー: {e}", exc_info=True)

    def _handle_userdetails_response(self, message: str) -> None:
        """userdetailsレスポンスを処理"""
        try:
            parts = message.split("|")
            if len(parts) > 3:
                data_str = "|".join(parts[3:])
                data = json.loads(data_str)
                
                if "rooms" in data and isinstance(data["rooms"], dict):
                    for room_id in data["rooms"].keys():
                        if room_id.startswith("battle-") and room_id not in self.watched_battles:
                            logger.info(f"バトル発見: {room_id}")
                            asyncio.create_task(self.ps_client.send_message("", f"/join {room_id}"))
                            self.watched_battles.add(room_id)
        except json.JSONDecodeError as e:
            logger.warning(f"userdetails JSONパースエラー: {e}")
        except Exception as e:
            logger.error(f"userdetails処理エラー: {e}", exc_info=True)

    def _check_and_join_battle(self, room_id: str, room_data: dict) -> None:
        """バトルルームをチェックして参加"""
        p1 = room_data.get("p1", "")
        p2 = room_data.get("p2", "")
        
        target_id = self.target_player.lower().replace(" ", "")
        p1_id = p1.lower().replace(" ", "")
        p2_id = p2.lower().replace(" ", "")
        
        if target_id == p1_id or target_id == p2_id:
            if room_id.startswith("battle-") and room_id not in self.watched_battles:
                logger.info(f"バトル発見 (roomlist): {room_id}")
                asyncio.create_task(self.ps_client.send_message("", f"/join {room_id}"))
                self.watched_battles.add(room_id)

    def _handle_battle_message(self, message: str) -> None:
        """バトルメッセージを処理"""
        super()._handle_battle_message(message)

    def choose_move(self, battle: Battle):
        """観戦者は行動を選択しない（Playerクラス要件）"""
        return "/choose default"

    async def on_battle_start(self, battle: Battle) -> None:
        """バトル開始時の処理"""
        logger.info("=" * 60)
        logger.info(f"観戦開始: {battle.battle_tag}")
        logger.info(f"Players: {battle.player_username} vs {battle.opponent_username}")
        logger.info("=" * 60)

    async def on_battle_end(self, battle: Battle) -> None:
        """バトル終了時の処理"""
        logger.info("=" * 60)
        logger.info(f"バトル終了: {battle.battle_tag}")
        logger.info(f"Winner: {battle.won}")
        logger.info("=" * 60)

    def _process_battle_message(self, message: str, battle: Battle) -> None:
        """バトルメッセージを処理"""
        # #region agent log
        import json
        import os
        try:
            log_data = {
                "location": "spectator.py:_process_battle_message",
                "message": "Battle message received",
                "data": {
                    "message_preview": message[:100],
                    "battle_tag": getattr(battle, 'battle_tag', 'unknown'),
                    "turn": getattr(battle, 'turn', 0),
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
        
        super()._process_battle_message(message, battle)
        
        # ターン更新を検知
        parts = message.split("|")
        if len(parts) > 1 and parts[1] == "turn":
            self._analyze_turn(battle)

    def _analyze_turn(self, battle: Battle) -> None:
        """現在のターンを分析"""
        logger.info(f"--- Turn {battle.turn} ---")
        
        try:
            battle_state = self._convert_battle_to_state(battle)
            _, slow_result = self.strategist.predict_both(battle_state)
            self._print_commentary(battle, slow_result)
        except Exception as e:
            logger.error(f"分析エラー: {e}", exc_info=True)

    def _convert_battle_to_state(self, battle: Battle) -> BattleState:
        """Battle -> BattleState 変換"""
        # #region agent log
        import json
        import os
        try:
            active_count = len(getattr(battle, 'active_pokemon', []))
            log_data = {
                "location": "spectator.py:_convert_battle_to_state",
                "message": "Converting battle to state",
                "data": {
                    "battle_tag": getattr(battle, 'battle_tag', 'unknown'),
                    "turn": getattr(battle, 'turn', 0),
                    "active_pokemon_count": active_count,
                    "has_active_pokemon": hasattr(battle, 'active_pokemon'),
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
        
        player_a_name = self.target_player
        player_b_name = "Opponent"
        
        # 実際のアクティブポケモンを抽出
        player_a_active = []
        try:
            active_list = getattr(battle, 'active_pokemon', [])
            for poke in active_list:
                if poke:
                    player_a_active.append(PokemonBattleState(
                        name=getattr(poke, 'species', 'Unknown'),
                        hp_fraction=getattr(poke, 'current_hp_fraction', 1.0),
                        species=getattr(poke, 'species', 'Unknown'),
                    ))
        except Exception as e:
            logger.debug(f"アクティブポケモン抽出エラー: {e}")
            player_a_active = [PokemonBattleState(name="Unknown", hp_fraction=1.0)]
        
        # 相手のアクティブポケモンを抽出
        player_b_active = []
        try:
            opponent_active_list = getattr(battle, 'opponent_active_pokemon', [])
            for poke in opponent_active_list:
                if poke:
                    player_b_active.append(PokemonBattleState(
                        name=getattr(poke, 'species', 'Unknown'),
                        hp_fraction=getattr(poke, 'current_hp_fraction', 1.0),
                        species=getattr(poke, 'species', 'Unknown'),
                    ))
        except Exception as e:
            logger.debug(f"相手アクティブポケモン抽出エラー: {e}")
            player_b_active = [PokemonBattleState(name="Unknown", hp_fraction=1.0)]
        
        player_a = PlayerState(
            name=player_a_name,
            active=player_a_active if player_a_active else [PokemonBattleState(name="Unknown", hp_fraction=1.0)],
            reserves=[]
        )
        player_b = PlayerState(
            name=player_b_name,
            active=player_b_active if player_b_active else [PokemonBattleState(name="Unknown", hp_fraction=1.0)],
            reserves=[]
        )
        
        legal_actions = {"A": [], "B": []}
        
        return BattleState(
            player_a=player_a,
            player_b=player_b,
            turn=battle.turn,
            legal_actions=legal_actions
        )

    async def _broadcast_state(self, battle: Battle, prediction, fast_result=None) -> None:
        """現在の状態をMessageBroker経由でブロードキャスト"""
        try:
            from src.infrastructure.messaging.broker import get_message_broker
            from src.application.services.spectator_analyzer import get_spectator_analyzer
            
            broker = get_message_broker()
            analyzer = get_spectator_analyzer(use_llm=True)
            
            # 盤面情報を抽出
            player_active = self._extract_active_pokemon_detailed(battle, is_player=True)
            opponent_active = self._extract_active_pokemon_detailed(battle, is_player=False)
            player_bench = self._extract_bench_pokemon(battle, is_player=True)
            opponent_bench = self._extract_bench_pokemon(battle, is_player=False)
            field_state = self._extract_field_state(battle)
            
            # SpectatorAnalyzerで分析
            analysis = analyzer.analyze(
                player_active=player_active,
                opponent_active=opponent_active,
                player_bench=player_bench,
                opponent_bench=opponent_bench,
                field_state=field_state,
                turn=battle.turn,
            )
            
            # 勝率履歴の記録
            self._win_rate_history.append({
                "turn": battle.turn,
                "winRate": analysis.win_rate
            })
            if len(self._win_rate_history) > 20:
                self._win_rate_history = self._win_rate_history[-20:]
            
            # バトル形式を検出（シングル/ダブル）
            battle_type = "double"  # デフォルトはダブル
            try:
                from poke_env.battle import DoubleBattle
                if isinstance(battle, DoubleBattle):
                    battle_type = "double"
                else:
                    battle_type = "single"
            except Exception:
                # フォールバック: active_pokemonの数で判定
                try:
                    active_count = len(getattr(battle, 'active_pokemon', []))
                    if active_count <= 1:
                        battle_type = "single"
                    else:
                        battle_type = "double"
                except Exception:
                    battle_type = "double"  # デフォルト
            
            # ブロードキャスト用メッセージを構築
            message = {
                "type": "game_update",
                "data": {
                    "turn": battle.turn,
                    "winRate": analysis.win_rate,
                    "winRateHistory": self._win_rate_history,
                    "boardScore": analysis.board_score.total,
                    "fieldConditions": field_state,
                    "battleType": battle_type,  # シングル/ダブル
                    "p1": {
                        "name": self.target_player,
                        "rating": getattr(battle, "rating", 1500),
                        "pokemon": self._extract_team_info(battle, is_player=True),
                        "activePokemon": player_active
                    },
                    "p2": {
                        "name": "Opponent",
                        "rating": 1500,
                        "pokemon": self._extract_team_info(battle, is_player=False),
                        "activePokemon": opponent_active
                    },
                    "candidates": {
                        "p1": [c.to_dict() for c in analysis.candidates],
                        "p2": []
                    },
                    "explanation": {
                        "playerStrategy": analysis.explanation.recommended_strategy,
                        "opponentThreat": analysis.explanation.opponent_prediction,
                        "currentSituation": analysis.explanation.current_situation,
                        "topCandidateReason": analysis.explanation.top_candidate_reason,
                        "riskAnalysis": analysis.explanation.risk_analysis,
                    }
                }
            }
            
            await broker.broadcast(message)
            logger.debug(f"ブロードキャスト完了: Turn {battle.turn}")
            
        except Exception as e:
            logger.error(f"ブロードキャストエラー: {e}", exc_info=True)

    def _extract_team_info(self, battle: Battle, is_player: bool) -> List[str]:
        """バトルからチーム情報を抽出"""
        team = []
        try:
            pokemon_dict = getattr(battle, 'team' if is_player else 'opponent_team', {})
            for key, pokemon in pokemon_dict.items():
                name = getattr(pokemon, 'species', 'Unknown')
                team.append(name)
        except Exception as e:
            logger.debug(f"チーム情報抽出エラー: {e}")
        return team if team else ["ポケモン1", "ポケモン2", "ポケモン3", "ポケモン4"]

    def _extract_active_pokemon(self, battle: Battle, is_player: bool) -> List[Dict[str, Any]]:
        """アクティブポケモンの詳細を抽出"""
        active = []
        try:
            pokemon_list = getattr(battle, 'active_pokemon' if is_player else 'opponent_active_pokemon', [])
            if pokemon_list:
                for poke in pokemon_list:
                    if poke:
                        active.append({
                            "name": getattr(poke, 'species', 'Unknown'),
                            "hp": getattr(poke, 'current_hp_fraction', 1.0)
                        })
        except Exception as e:
            logger.debug(f"アクティブポケモン抽出エラー: {e}")
        return active if active else [{"name": "Unknown", "hp": 1.0}]

    def _extract_active_pokemon_detailed(self, battle: Battle, is_player: bool) -> List[Dict[str, Any]]:
        """アクティブポケモンの詳細情報を抽出"""
        active = []
        try:
            pokemon_list = getattr(battle, 'active_pokemon' if is_player else 'opponent_active_pokemon', [])
            
            if pokemon_list:
                for poke in pokemon_list:
                    if poke and not getattr(poke, 'fainted', False):
                        # タイプ情報
                        types = self._extract_types(poke)
                        # 技情報
                        moves = self._extract_moves(poke)
                        # 素早さ情報
                        speed = self._extract_speed(poke)
                        
                        active.append({
                            "name": getattr(poke, 'species', 'Unknown'),
                            "hp_fraction": getattr(poke, 'current_hp_fraction', 1.0),
                            "types": types,
                            "moves": moves,
                            "speed": speed,
                            "fainted": getattr(poke, 'fainted', False),
                        })
        except Exception as e:
            logger.debug(f"詳細ポケモン情報抽出エラー: {e}")
        
        if not active:
            active = [{
                "name": "Unknown",
                "hp_fraction": 1.0,
                "types": ["Normal"],
                "moves": [{"name": "技", "type": "Normal"}],
                "speed": 100,
                "fainted": False,
            }]
        return active

    def _extract_types(self, poke) -> List[str]:
        """ポケモンのタイプを抽出"""
        types = []
        if hasattr(poke, 'types') and poke.types:
            types = [t.name.capitalize() if hasattr(t, 'name') else str(t) for t in poke.types if t]
        return types if types else ["Normal"]

    def _extract_moves(self, poke) -> List[Dict[str, str]]:
        """ポケモンの技を抽出"""
        moves = []
        if hasattr(poke, 'moves') and poke.moves:
            for move_id, move_obj in poke.moves.items():
                move_name = getattr(move_obj, 'id', move_id)
                move_type = getattr(move_obj, 'type', None)
                type_name = move_type.name.capitalize() if move_type and hasattr(move_type, 'name') else "Normal"
                moves.append({"name": move_name, "type": type_name})
        return moves if moves else [{"name": "技", "type": "Normal"}]

    def _extract_speed(self, poke) -> int:
        """ポケモンの素早さを抽出"""
        if hasattr(poke, 'stats') and poke.stats and 'spe' in poke.stats:
            return poke.stats['spe']
        elif hasattr(poke, 'base_stats') and poke.base_stats and 'spe' in poke.base_stats:
            return poke.base_stats['spe']
        return 100

    def _extract_bench_pokemon(self, battle: Battle, is_player: bool) -> List[Dict[str, Any]]:
        """控えポケモンの情報を抽出"""
        bench = []
        try:
            pokemon_dict = getattr(battle, 'team' if is_player else 'opponent_team', {})
            active_list = getattr(battle, 'active_pokemon' if is_player else 'opponent_active_pokemon', [])
            
            active_names = {getattr(poke, 'species', '') for poke in active_list if poke}
            
            for key, poke in pokemon_dict.items():
                name = getattr(poke, 'species', 'Unknown')
                if name not in active_names and not getattr(poke, 'fainted', False):
                    types = self._extract_types(poke)
                    bench.append({
                        "name": name,
                        "hp_fraction": getattr(poke, 'current_hp_fraction', 1.0),
                        "types": types,
                        "fainted": getattr(poke, 'fainted', False),
                    })
        except Exception as e:
            logger.debug(f"控えポケモン抽出エラー: {e}")
        return bench

    def _extract_field_state(self, battle: Battle) -> Dict[str, Any]:
        """フィールド状態を抽出"""
        field_state = {}
        try:
            # 天候
            if hasattr(battle, 'weather') and battle.weather:
                weather_keys = list(battle.weather.keys())
                if weather_keys:
                    w = str(weather_keys[0]).lower()
                    if "sun" in w or "drought" in w:
                        field_state["weather"] = "sun"
                    elif "rain" in w or "drizzle" in w:
                        field_state["weather"] = "rain"
                    elif "sand" in w or "stream" in w:
                        field_state["weather"] = "sand"
                    elif "hail" in w or "snow" in w:
                        field_state["weather"] = "snow"
            
            # フィールド
            if hasattr(battle, 'fields'):
                for f in battle.fields:
                    f_str = str(f).lower()
                    if "electric" in f_str:
                        field_state["terrain"] = "electric"
                    elif "grassy" in f_str:
                        field_state["terrain"] = "grassy"
                    elif "psychic" in f_str:
                        field_state["terrain"] = "psychic"
                    elif "misty" in f_str:
                        field_state["terrain"] = "misty"
                    elif "trickroom" in f_str:
                        field_state["trickRoom"] = True

            # サイドコンディション
            if hasattr(battle, 'side_conditions'):
                sc = {str(k).lower(): v for k, v in battle.side_conditions.items()}
                if 'tailwind' in sc:
                    field_state["playerTailwind"] = True
                if 'reflect' in sc:
                    field_state["playerReflect"] = True
                if 'lightscreen' in sc:
                    field_state["playerLightScreen"] = True
            
            if hasattr(battle, 'opponent_side_conditions'):
                osc = {str(k).lower(): v for k, v in battle.opponent_side_conditions.items()}
                if 'tailwind' in osc:
                    field_state["opponentTailwind"] = True
                if 'reflect' in osc:
                    field_state["opponentReflect"] = True
                if 'lightscreen' in osc:
                    field_state["opponentLightScreen"] = True
                    
        except Exception as e:
            logger.debug(f"フィールド状態抽出エラー: {e}")
        
        return field_state

    def _generate_candidates(self, prediction, fast_result, is_player: bool) -> List[Dict[str, Any]]:
        """候補手を生成"""
        candidates = []
        
        if prediction.alternatives:
            for alt in prediction.alternatives[:3]:
                candidates.append({
                    "move1": alt.get("move1", "技1"),
                    "target1": alt.get("target1", ""),
                    "type1": alt.get("type1", "attack"),
                    "move2": alt.get("move2", "技2"),
                    "target2": alt.get("target2", ""),
                    "type2": alt.get("type2", "attack"),
                    "score": alt.get("score", 50)
                })
        
        if not candidates:
            if is_player:
                candidates = [
                    {"move1": "ドレインパンチ", "target1": "相手エース", "type1": "attack",
                     "move2": "テラクラスター", "target2": "相手サポート", "type2": "attack",
                     "score": int(prediction.p1_win_rate * 100)},
                ]
            else:
                candidates = [
                    {"move1": "アストラルビット", "target1": "全体", "type1": "attack",
                     "move2": "インファイト", "target2": "こちらエース", "type2": "attack",
                     "score": int((1 - prediction.p1_win_rate) * 100)},
                ]
        
        return candidates

    def _generate_explanation(self, p1_win: float, prediction) -> Dict[str, str]:
        """AI解説を生成"""
        if prediction.explanation:
            player_strategy = prediction.explanation
        else:
            if p1_win > 0.6:
                player_strategy = "現在有利な状況です。安定択を選ぶのが良いでしょう。"
            elif p1_win < 0.4:
                player_strategy = "厳しい状況です。大胆な択が必要かもしれません。"
            else:
                player_strategy = "互角の展開です。読み合いが勝負を分けます。"
        
        if p1_win < 0.5:
            opponent_threat = "相手は積極的に攻めてくる可能性が高いです。"
        else:
            opponent_threat = "相手は守りに入る可能性があります。"
        
        return {
            "playerStrategy": player_strategy,
            "opponentThreat": opponent_threat
        }

    def _print_commentary(self, battle: Battle, prediction) -> None:
        """実況コメントをログ出力"""
        p1_win = prediction.p1_win_rate
        p2_win = 1.0 - p1_win
        
        logger.info(f"勝率予測: {self.target_player} {p1_win:.1%} - {p2_win:.1%} Opponent")
        
        if prediction.explanation:
            logger.info(f"解説: {prediction.explanation}")
        
        if p1_win > 0.7:
            logger.info(f"{self.target_player} が優勢です！")
        elif p1_win < 0.3:
            logger.info(f"{self.target_player} がピンチです...")
        else:
            logger.info("互角の戦いです。")
        
        # WebSocket放送
        asyncio.create_task(self._broadcast_state(battle, prediction))

    async def run_loop(self) -> None:
        """メインループ"""
        asyncio.create_task(self._search_and_join_battles())
        
        logger.info("観戦ループ開始")
        while True:
            await asyncio.sleep(1)
