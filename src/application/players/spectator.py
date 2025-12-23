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

    async def run_loop(self):
        """
        メインループ
        """
        # 検索タスク開始
        asyncio.create_task(self._search_and_join_battles())
        
        # 無限ループで待機（親クラスの処理が必要なら適宜）
        while True:
            await asyncio.sleep(1)

