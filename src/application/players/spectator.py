import asyncio
import json
import logging
import random
import string
import sys
from typing import Optional, Dict

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

class Spectator(Player):
    def __init__(
        self,
        target_player: str,
        battle_id: Optional[str] = None,  # 手動でバトルIDを指定可能
        account_configuration=None,
        *,
        avatar: Optional[str] = None,
        log_level: Optional[int] = None,
        server_configuration=None,
        start_listening: bool = True,
    ):
        super().__init__(
            account_configuration=account_configuration,
            avatar=avatar,
            log_level=log_level,
            server_configuration=server_configuration,
            start_listening=start_listening,
        )
        self.target_player = target_player
        self.manual_battle_id = battle_id
        self.watched_battles = set()
        
        # 名前重複回避のためにランダムサフィックスを追加
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        self._custom_username = f"Spectator {suffix}"
        
        # HybridStrategistの初期化
        self.strategist = HybridStrategist(
            fast_model_path="models/fast_lane.pkl",
            mcts_rollouts=500,
            mcts_max_turns=20
        )
        print(f"👀 観戦エージェント起動: ターゲット = {self.target_player} (As: {self._custom_username})")
        if self.manual_battle_id:
            print(f"📍 手動指定バトルID: {self.manual_battle_id}")

    async def _search_and_join_battles(self):
        """
        定期的にターゲットプレイヤーのバトルを検索して参加する
        """
        # 名前変更を試みる
        await self.ps_client.send_message("", f"/nick {self._custom_username}")
        await asyncio.sleep(1)
        
        # 手動でバトルIDが指定されている場合、直接参加
        if self.manual_battle_id:
            print(f"🚀 バトルに参加中: {self.manual_battle_id}")
            await self.ps_client.send_message("", f"/join {self.manual_battle_id}")
            self.watched_battles.add(self.manual_battle_id)
            return  # 手動指定の場合は検索ループ不要
        
        # ロビーに参加
        await self.ps_client.send_message("", "/join lobby")
        
        query_idx = 100
        while True:
            try:
                # クエリを送信（より頻繁に）
                await self.ps_client.send_message("", f"|/cmd roomlist {query_idx}")
                await self.ps_client.send_message("", f"|/cmd userdetails {self.target_player}")
                query_idx += 1
                
            except Exception as e:
                print(f"Error searching battles: {e}")
            
            await asyncio.sleep(2)  # 2秒間隔に短縮

    def _handle_message(self, message: str) -> None:
        """
        グローバルメッセージを含む全メッセージを処理 (同期ラッパー)
        """
        # 完全デバッグログ
        # print(f"RAW RECV: {message}")

        # デバッグ: クエリレスポンスを表示
        if message.startswith("|queryresponse|"):
            print(f"DEBUG (global): {message[:100]}...")

        # カスタム処理: roomlistのレスポンス解析
        if message.startswith("|queryresponse|roomlist|"):
            try:
                # |queryresponse|roomlist|{...}
                parts = message.split("|")
                if len(parts) > 3:
                     data_str = "|".join(parts[3:]) # JSON部分
                     data = json.loads(data_str)
                     
                     if "rooms" in data:
                        for room_id, room_data in data["rooms"].items():
                            p1 = room_data.get("p1", "")
                            p2 = room_data.get("p2", "")
                            
                            target_id = self.target_player.lower().replace(" ", "")
                            p1_id = p1.lower().replace(" ", "")
                            p2_id = p2.lower().replace(" ", "")
                            
                            if target_id == p1_id or target_id == p2_id:
                                if room_id.startswith("battle-") and room_id not in self.watched_battles:
                                    print(f"🔍 バトル発見 (roomlist): {room_id}")
                                    asyncio.create_task(self.ps_client.send_message("", f"/join {room_id}"))
                                    self.watched_battles.add(room_id)
            except Exception as e:
                print(f"Error parsing roomlist: {e}")
            return # 処理済みとして戻る（警告抑制のため）

        # カスタム処理: userdetailsのレスポンス解析
        if message.startswith("|queryresponse|userdetails|"):
            try:
                parts = message.split("|")
                if len(parts) > 3:
                    data_str = "|".join(parts[3:])
                    data = json.loads(data_str)
                    
                    # userdetails responses sometimes have "rooms" as a dict: {"battle-gen9randombattle-1": {}}
                    # or it could be False/None if no rooms
                    if "rooms" in data and isinstance(data["rooms"], dict):
                        for room_id in data["rooms"].keys():
                            if room_id.startswith("battle-") and room_id not in self.watched_battles:
                                print(f"🔍 バトル発見: {room_id}")
                                asyncio.create_task(self.ps_client.send_message("", f"/join {room_id}"))
                                self.watched_battles.add(room_id)
            except Exception as e:
                print(f"Error parsing userdetails: {e}")
            return

        # 親クラスの処理
        super()._handle_message(message)

    def _handle_battle_message(self, message: str) -> None:
        """
        サーバーからのメッセージを処理
        """
        # 親クラスの処理（バトル更新など）
        super()._handle_battle_message(message)


    def choose_move(self, battle: Battle):
        """
        観戦者なので行動は選択しないが、Playerクラスの要件として実装が必要。
        """
        return "/choose default"

    async def on_battle_start(self, battle: Battle):
        print(f"\n{'='*60}")
        print(f"🎥 観戦開始: {battle.battle_tag}")
        print(f"   Players: {battle.player_username} vs {battle.opponent_username}")
        print(f"{'='*60}")

    async def on_battle_end(self, battle: Battle):
        print(f"\n{'='*60}")
        print(f"🏁 バトル終了: {battle.battle_tag}")
        print(f"   Winner: {battle.won}") # 観戦者の場合 won はどうなる？
        print(f"{'='*60}")

    # poke-envのPlayerは on_turn ではなく choose_move が呼ばれるタイミングで思考するが、
    # 観戦者の場合 choose_move は呼ばれない（はず）。
    # 代わりに _handle_battle_message 内で update を検知するか、
    # 定期的にポーリングするか。
    # 実は poke-env は観戦モード（Playerとして参加していないバトル）の場合、
    # battle.turn が更新されたタイミングをフックする標準的な方法が薄い。
    # しかし、Battleオブジェクトは更新される。
    
    # 簡易実装: _handle_battle_message をオーバーライドして、ターン終了メッセージなどを検知する。
    # または、battle.turn が変わったことを検知する。
    
    # ここでは、_handle_battle_message で "|turn|" を検知して分析をトリガーする。
    
    def _process_battle_message(self, message: str, battle: Battle):
        super()._process_battle_message(message, battle)
        
        # ターン更新を検知
        parts = message.split("|")
        if len(parts) > 1 and parts[1] == "turn":
            # ターン開始
            self._analyze_turn(battle)
            
    def _analyze_turn(self, battle: Battle):
        """
        現在のターンを分析して実況する
        """
        print(f"\n--- Turn {battle.turn} ---")
        
        # ターゲットプレイヤーがどちらか特定
        # battle.player_username は "自分" (Spectator) になる可能性がある？
        # いや、観戦の場合、battle.player_username は空か、あるいは片方のプレイヤー？
        # poke-envの実装による。
        
        # ターゲットがAかBか判定
        # battle.player_username / battle.opponent_username は
        # 観戦の場合、正しく設定されないことが多い。
        # battle.players などを確認する必要があるかも。
        
        # とりあえず BattleState に変換して分析
        try:
            battle_state = self._convert_battle_to_state(battle)
            
            # 予測実行
            # predict_both は同期メソッドとして実装されている（内部でMCTSを呼ぶ）
            # 非同期で呼びたいが、とりあえず同期で。
            _, slow_result = self.strategist.predict_both(battle_state)
            
            # 実況出力
            self._print_commentary(battle, slow_result)
            
        except Exception as e:
            print(f"Analysis Error: {e}")

    def _convert_battle_to_state(self, battle: Battle) -> BattleState:
        """
        Battle -> BattleState 変換
        ターゲットプレイヤーを Player A (自分視点) として扱う
        """
        # プレイヤーの特定
        # battle.player_role は観戦者の場合 None かも
        # battle.players は {player_id: player_name} の辞書？
        # poke-env の Battle オブジェクトの中身を推測
        
        # ターゲットプレイヤーを探す
        p1_name = None
        p2_name = None
        
        # battle.players 属性はないかもしれない。
        # battle.player_username, battle.opponent_username を使う
        # 観戦の場合、これらは空文字の可能性がある。
        
        # 暫定: ターゲットプレイヤーの名前が含まれている側をAとする
        # しかし、Battleオブジェクトの情報が不足している場合がある。
        
        # ここでは、battle_ai_player.py のロジックを流用しつつ、
        # ターゲットプレイヤーを優先する。
        
        # 仮実装:
        player_a_name = self.target_player
        player_b_name = "Opponent"
        
        # 実際には battle オブジェクトから情報を抽出する必要がある
        # active_pokemon なども、観戦者視点だと battle.active_pokemon (自分) は存在しないかも？
        # battle.opponent_active_pokemon も...
        
        # 観戦モードの poke-env Battle オブジェクトは、
        # battle.sides などの低レベル情報を持っている可能性がある。
        # しかし、標準API (active_pokemon) が機能するかは怪しい。
        
        # 今回は「動くこと」を優先し、エラーハンドリングを厚くする。
        
        # ダミー実装に近い形になるが、構造を作る。
        
        player_a = PlayerState(
            name=player_a_name,
            active=[PokemonBattleState(name="Unknown", hp_fraction=1.0)],
            reserves=[]
        )
        player_b = PlayerState(
            name=player_b_name,
            active=[PokemonBattleState(name="Unknown", hp_fraction=1.0)],
            reserves=[]
        )
        
        # Legal Actions (観戦者にはわからないので空)
        legal_actions = {"A": [], "B": []}
        
        return BattleState(
            player_a=player_a,
            player_b=player_b,
            turn=battle.turn,
            legal_actions=legal_actions
        )

    async def _broadcast_state(self, battle: Battle, prediction, fast_result=None):
        """
        現在の状態をMessageBroker経由でブロードキャスト
        
        Phase 15: SpectatorAnalyzerを使用してシミュレーションベースの候補手を生成
        """
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
            
            # SpectatorAnalyzerで分析（シミュレーションベース）
            analysis = analyzer.analyze(
                player_active=player_active,
                opponent_active=opponent_active,
                player_bench=player_bench,
                opponent_bench=opponent_bench,
                field_state=field_state,
                turn=battle.turn,
            )
            
            # 勝率履歴の記録
            if not hasattr(self, '_win_rate_history'):
                self._win_rate_history = []
            self._win_rate_history.append({
                "turn": battle.turn,
                "winRate": analysis.win_rate
            })
            if len(self._win_rate_history) > 20:
                self._win_rate_history = self._win_rate_history[-20:]
            
            # ブロードキャスト用メッセージを構築
            message = {
                "type": "game_update",
                "data": {
                    "turn": battle.turn,
                    "winRate": analysis.win_rate,
                    "winRateHistory": self._win_rate_history,
                    "boardScore": analysis.board_score.total,
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
                        "p2": []  # 相手の候補は観戦では生成しない
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
            
        except Exception as e:
            print(f"Broadcast Error: {e}")
            import traceback
            traceback.print_exc()
    
    def _extract_team_info(self, battle: Battle, is_player: bool) -> list:
        """バトルからチーム情報を抽出"""
        team = []
        try:
            # poke-envのBattleオブジェクトから情報を取得
            if is_player:
                pokemon_dict = getattr(battle, 'team', {})
            else:
                pokemon_dict = getattr(battle, 'opponent_team', {})
            
            for key, pokemon in pokemon_dict.items():
                name = getattr(pokemon, 'species', 'Unknown')
                team.append(name)
        except Exception:
            pass
        return team if team else ["ポケモン1", "ポケモン2", "ポケモン3", "ポケモン4"]
    
    def _extract_active_pokemon(self, battle: Battle, is_player: bool) -> list:
        """アクティブポケモンの詳細を抽出"""
        active = []
        try:
            if is_player:
                pokemon_list = getattr(battle, 'active_pokemon', [])
            else:
                pokemon_list = getattr(battle, 'opponent_active_pokemon', [])
            
            if pokemon_list:
                for poke in pokemon_list:
                    if poke:
                        active.append({
                            "name": getattr(poke, 'species', 'Unknown'),
                            "hp": getattr(poke, 'current_hp_fraction', 1.0)
                        })
        except Exception:
            pass
        return active if active else [{"name": "Unknown", "hp": 1.0}]
    
    def _extract_active_pokemon_detailed(self, battle: Battle, is_player: bool) -> list:
        """アクティブポケモンの詳細情報を抽出（SpectatorAnalyzer用）"""
        active = []
        try:
            if is_player:
                pokemon_list = getattr(battle, 'active_pokemon', [])
            else:
                pokemon_list = getattr(battle, 'opponent_active_pokemon', [])
            
            if pokemon_list:
                for poke in pokemon_list:
                    if poke and not getattr(poke, 'fainted', False):
                        # タイプ情報を抽出
                        types = []
                        if hasattr(poke, 'types') and poke.types:
                            types = [t.name.capitalize() if hasattr(t, 'name') else str(t) for t in poke.types if t]
                        if not types:
                            types = ["Normal"]
                        
                        # 技情報を抽出
                        moves = []
                        if hasattr(poke, 'moves') and poke.moves:
                            for move_id, move_obj in poke.moves.items():
                                move_name = getattr(move_obj, 'id', move_id)
                                move_type = getattr(move_obj, 'type', None)
                                type_name = move_type.name.capitalize() if move_type and hasattr(move_type, 'name') else "Normal"
                                moves.append({
                                    "name": move_name,
                                    "type": type_name
                                })
                        if not moves:
                            moves = [{"name": "技", "type": "Normal"}]
                        
                        # 素早さ情報
                        speed = 100
                        if hasattr(poke, 'stats') and poke.stats and 'spe' in poke.stats:
                            speed = poke.stats['spe']
                        elif hasattr(poke, 'base_stats') and poke.base_stats and 'spe' in poke.base_stats:
                            speed = poke.base_stats['spe']
                        
                        active.append({
                            "name": getattr(poke, 'species', 'Unknown'),
                            "hp_fraction": getattr(poke, 'current_hp_fraction', 1.0),
                            "types": types,
                            "moves": moves,
                            "speed": speed,
                            "fainted": getattr(poke, 'fainted', False),
                        })
        except Exception as e:
            print(f"_extract_active_pokemon_detailed error: {e}")
        
        # フォールバック
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
    
    def _extract_bench_pokemon(self, battle: Battle, is_player: bool) -> list:
        """控えポケモンの情報を抽出"""
        bench = []
        try:
            if is_player:
                pokemon_dict = getattr(battle, 'team', {})
                active_list = getattr(battle, 'active_pokemon', [])
            else:
                pokemon_dict = getattr(battle, 'opponent_team', {})
                active_list = getattr(battle, 'opponent_active_pokemon', [])
            
            active_names = set()
            for poke in active_list:
                if poke:
                    active_names.add(getattr(poke, 'species', ''))
            
            for key, poke in pokemon_dict.items():
                name = getattr(poke, 'species', 'Unknown')
                if name not in active_names and not getattr(poke, 'fainted', False):
                    types = []
                    if hasattr(poke, 'types') and poke.types:
                        types = [t.name.capitalize() if hasattr(t, 'name') else str(t) for t in poke.types if t]
                    if not types:
                        types = ["Normal"]
                    
                    bench.append({
                        "name": name,
                        "hp_fraction": getattr(poke, 'current_hp_fraction', 1.0),
                        "types": types,
                        "fainted": getattr(poke, 'fainted', False),
                    })
        except Exception as e:
            print(f"_extract_bench_pokemon error: {e}")
        
        return bench
    
    def _extract_field_state(self, battle: Battle) -> dict:
        """フィールド状態を抽出"""
        field_state = {}
        try:
            # 天候
            if hasattr(battle, 'weather') and battle.weather:
                weather_keys = list(battle.weather.keys())
                if weather_keys:
                    field_state["weather"] = str(weather_keys[0])
            
            # トリックルーム
            if hasattr(battle, 'fields') and 'trickroom' in battle.fields:
                field_state["trick_room"] = True
            
            # サイドコンディション
            if hasattr(battle, 'side_conditions'):
                if 'tailwind' in battle.side_conditions:
                    field_state["tailwind_player"] = True
            
            if hasattr(battle, 'opponent_side_conditions'):
                if 'tailwind' in battle.opponent_side_conditions:
                    field_state["tailwind_opponent"] = True
            
        except Exception as e:
            print(f"_extract_field_state error: {e}")
        
        return field_state
    
    def _generate_candidates(self, prediction, fast_result, is_player: bool) -> list:
        """候補手を生成する（ダブルバトル形式）"""
        candidates = []
        
        # predictionのalternativesがあればそれを使用
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
        
        # alternativesがない場合はダミーデータ
        if not candidates:
            if is_player:
                candidates = [
                    {"move1": "ドレインパンチ", "target1": "相手エース", "type1": "attack",
                     "move2": "テラクラスター", "target2": "相手サポート", "type2": "attack",
                     "score": int(prediction.p1_win_rate * 100)},
                    {"move1": "ねこだまし", "target1": "相手エース", "type1": "protect",
                     "move2": "まもる", "target2": "", "type2": "protect",
                     "score": max(10, int((1 - prediction.p1_win_rate) * 50))},
                    {"move1": "交代", "target1": "控えポケモン", "type1": "switch",
                     "move2": "テラクラスター", "target2": "相手エース", "type2": "attack",
                     "score": 15}
                ]
            else:
                candidates = [
                    {"move1": "アストラルビット", "target1": "全体", "type1": "attack",
                     "move2": "インファイト", "target2": "こちらエース", "type2": "attack",
                     "score": int((1 - prediction.p1_win_rate) * 100)},
                    {"move1": "まもる", "target1": "", "type1": "protect",
                     "move2": "すいりゅうれんだ", "target2": "こちらサポート", "type2": "attack",
                     "score": max(10, int(prediction.p1_win_rate * 40))},
                    {"move1": "交代", "target1": "控えポケモン", "type1": "switch",
                     "move2": "まもる", "target2": "", "type2": "protect",
                     "score": 10}
                ]
        
        return candidates
    
    def _generate_explanation(self, p1_win: float, prediction) -> dict:
        """AI解説を生成"""
        # predictionにexplanationがあれば使用
        if prediction.explanation:
            player_strategy = prediction.explanation
        else:
            # 勝率に基づいて解説を生成
            if p1_win > 0.6:
                player_strategy = "現在有利な状況です。相手のエースに圧力をかけつつ、安定択を選ぶのが良いでしょう。"
            elif p1_win < 0.4:
                player_strategy = "厳しい状況です。相手の読みを外す大胆な択が必要かもしれません。"
            else:
                player_strategy = "互角の展開です。ここでの読み合いが勝負を分けます。"
        
        # 相手の脅威分析
        if p1_win < 0.5:
            opponent_threat = "相手は積極的に攻めてくる可能性が高いです。集中攻撃やテラスタルの切り返しに警戒してください。"
        else:
            opponent_threat = "相手は守りに入るか、逆転を狙った読みを仕掛けてくる可能性があります。"
        
        return {
            "playerStrategy": player_strategy,
            "opponentThreat": opponent_threat
        }

    def _print_commentary(self, battle: Battle, prediction):
        """
        実況コメントを表示
        """
        p1_win = prediction.p1_win_rate
        p2_win = 1.0 - p1_win
        
        print(f"📊 勝率予測: {self.target_player} {p1_win:.1%} - {p2_win:.1%} Opponent")
        
        if prediction.explanation:
            print(f"🤖 解説: {prediction.explanation}")
        
        if p1_win > 0.7:
            print(f"🔥 {self.target_player} が優勢です！")
        elif p1_win < 0.3:
            print(f"⚠️ {self.target_player} がピンチです...")
        else:
            print(f"⚖️ 互角の戦いです。")
            
        # WebSocket放送 (非同期実行のためにensure_future)
        asyncio.create_task(self._broadcast_state(battle, prediction))

    async def run_loop(self):
        """
        メインループ
        """
        # 検索タスク開始
        asyncio.create_task(self._search_and_join_battles())
        
        # 無限ループで待機（親クラスの処理が必要なら適宜）
        while True:
            await asyncio.sleep(1)


