#!/usr/bin/env python3
"""
VGCPredictor 試運転スクリプト

新アーキテクチャ（PokéChamp + PokeLLMon）のVGCPredictorを
Showdownで試運転するためのプレイヤー。
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Optional

# .envファイルから環境変数を読み込み
def load_dotenv():
    """シンプルな.env読み込み"""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    if value and key not in os.environ:
                        os.environ[key] = value

load_dotenv()

from poke_env import LocalhostServerConfiguration
from poke_env.player import Player

try:
    from poke_env.environment.double_battle import DoubleBattle
except ImportError:
    from poke_env.battle import DoubleBattle

# 新アーキテクチャのインポート
from predictor.core.vgc_predictor import VGCPredictor, PredictorConfig

# =============================================================================
# Monkey Patch: poke-env PSClient._handle_message
# =============================================================================
# BO3や特定メッセージで発生するIndexErrorを回避し、>gameメッセージをサポート
from poke_env.ps_client.ps_client import PSClient
from poke_env.exceptions import ShowdownException
from poke_env.exceptions import ShowdownException
from asyncio import CancelledError
from poke_env.player.battle_order import BattleOrder, SingleBattleOrder

# SingleBattleOrder is imported for use with DoubleBattleOrder

async def _patched_handle_message(self, message: str):
    """Robust handle_message that avoids IndexErrors and supports >game"""
    try:
        # Debug: Raw Log
        print(f"[RAW] {message}", flush=True)

        split_messages = [m.split("|") for m in message.split("\n")]
        
        # Guard: Empty message
        if not split_messages or not split_messages[0]:
            return

        room_id = split_messages[0][0]
        
        # Support >battle AND >game (for BO3)
        if room_id.startswith(">battle") or room_id.startswith(">game"):
            try:
                await self._handle_battle_message(split_messages)
            except NotImplementedError as e:
                # tempnotifyなど未実装メッセージは無視
                print(f"  ⚠️ Ignored NotImplementedError in handle_battle_message: {e}")
            except Exception as e:
                # その他のエラーはログに出して続行
                print(f"  ❌ Error in handle_battle_message: {e}")
                import traceback
                traceback.print_exc()
            
        elif len(split_messages[0]) > 1 and split_messages[0][1] == "challstr":
            await self.log_in(split_messages[0])
            
        elif len(split_messages[0]) > 1 and split_messages[0][1] == "updateuser":
            if len(split_messages[0]) > 2 and split_messages[0][2] in [
                " " + self.username,
                " " + self.username + "@!",
            ]:
                self.logged_in.set()
            elif len(split_messages[0]) > 2 and not split_messages[0][2].startswith(" Guest "):
                self.logger.warning(
                    """Trying to login as %s, showdown returned %s """
                    """- this might prevent future actions from this agent. """
                    """Changing the agent's username might solve this problem.""",
                    self.username,
                    split_messages[0][2],
                )
                
        elif len(split_messages[0]) > 1 and "updatechallenges" in split_messages[0][1]:
            await self._update_challenges(split_messages[0])
            
        elif len(split_messages[0]) > 1 and split_messages[0][1] == "updatesearch":
            pass
            
        elif len(split_messages[0]) > 1 and split_messages[0][1] == "popup":
            self.logger.warning("Popup message received: %s", message)
            
        elif len(split_messages[0]) > 1 and split_messages[0][1] in ["nametaken"]:
            self.logger.critical("Error message received: %s", message)
            raise ShowdownException("Error message received: %s", message)
            
        elif len(split_messages[0]) > 1 and split_messages[0][1] == "pm":
            if len(split_messages) == 1:
                if len(split_messages[0]) > 4:
                    if split_messages[0][4].startswith("/challenge"):
                        await self._handle_challenge_request(split_messages[0])
                    elif split_messages[0][4].startswith("/text"):
                        self.logger.info("Received pm with text: %s", message)
                    elif split_messages[0][4].startswith("/nonotify"):
                        self.logger.info("Received pm: %s", message)
                    elif split_messages[0][4].startswith("/log"):
                        self.logger.info("Received pm: %s", message)
                    else:
                        self.logger.warning("Received pm: %s", message)
            elif len(split_messages) == 2:
                self.logger.info("Received pm: %s", message)
            else:
                pass # Ignore malformed pm
        else:
            self.logger.warning("Unhandled message: %s", message)

    except CancelledError as e:
        self.logger.critical("CancelledError intercepted: %s", e)
    except Exception as exception:
        self.logger.exception(
            "Unhandled exception raised while handling message:\n%s", message
        )
        raise exception

# Apply patch
PSClient._handle_message = _patched_handle_message




class VGCPredictorPlayer(Player):
    """
    VGCPredictorを使用したプレイヤー
    """
    
    def __init__(
        self,
        *args,
        predictor_config: Optional[PredictorConfig] = None,
        **kwargs
    ):
        # チーム順序（Index解決用）をkwargsから取り出す（Playerに渡さないため）
        self.team_order_list = kwargs.pop('team_order_list', [])
        
        super().__init__(*args, **kwargs)
        
        # LLMクライアント初期化（APIキーがあれば自動で有効）
        import os
        llm_client = None
        if os.environ.get("OPENAI_API_KEY"):
            from predictor.llm.llm_client import LLMClient
            llm_client = LLMClient()
            print("🤖 LLM有効化: OpenAI API")
        
        self._llm_client = llm_client  # 保存しておく
        
        # VGCPredictor初期化
        self.predictor = VGCPredictor(
            config=predictor_config or PredictorConfig(
                depth=2,      # 試運転なので軽めに
                n_samples=4,
                top_k=15,
                use_llm=llm_client is not None,
            ),
            llm_client=llm_client,
        )
        
        # 案1+案2: TurnAdvisor と Plan 参照
        from predictor.core.turn_advisor import TurnAdvisor
        self.turn_advisor = TurnAdvisor(llm_client=llm_client)
        self.current_plan = None  # GamePlan オブジェクトを保持
        
        # Priority 2: BattleMemory 統合
        from src.domain.services.battle_memory import BattleMemory, reset_battle_memory
        reset_battle_memory()  # 新バトル開始時にリセット
        self.battle_memory = BattleMemory()
        
        # ============= Phase 9: CandidateGenerator に battle_memory を連携 =============
        from predictor.core.candidate_generator import get_candidate_generator
        get_candidate_generator(battle_memory=self.battle_memory)
        
        # ============= Phase 2: BeliefState 統合 =============
        from src.domain.services.belief_state import BeliefState, reset_belief_state
        from src.domain.services.belief_updater import BeliefUpdater
        reset_belief_state()
        self.belief_state = BeliefState()
        self.belief_updater = BeliefUpdater(belief=self.belief_state)
        
        # ============= Phase 2: StyleUpdater 統合 =============
        from src.domain.services.player_style import StyleUpdater, reset_style_updater
        reset_style_updater()
        self.style_updater = StyleUpdater()
        
        # ============= Phase 2: RiskAwareSolver 統合 =============
        from predictor.core.risk_aware_solver import RiskAwareSolver
        self.risk_solver = RiskAwareSolver()
        
        self.turn_count = 0
        self.last_turn = -1  # 同じターンでの重複呼び出し防止
        self._last_recorded_turn = -1  # 記録済みターンの追跡
        
        # ============= Phase 2: TacticalMixer 統合 =============
        from predictor.core.tactical_mixer import TacticalMixer, get_tactical_mixer
        self.tactical_mixer = get_tactical_mixer()
        
        # ============= Phase 3: BattleRecorder 統合 =============
        from src.application.services.battle_recorder import get_battle_recorder
        self.battle_recorder = get_battle_recorder()
        
        # ============= Phase 8-1: StatParticleFilter 統合 =============
        from src.domain.services.stat_particle_filter import get_stat_particle_filter, reset_stat_particle_filter
        reset_stat_particle_filter()  # 新バトル開始時にリセット
        self.stat_filter = get_stat_particle_filter()
        
        # ============= Phase 8-3: OpponentModelAdvisor 統合 =============
        from predictor.core.opponent_model_advisor import get_opponent_model_advisor
        self.opponent_model_advisor = get_opponent_model_advisor(llm_client)
        
        # ============= Phase 8-4: EndgameSolver 統合 =============
        from predictor.core.endgame_solver import get_endgame_solver
        self.endgame_solver = get_endgame_solver()
        
        print("🎮 VGCPredictorPlayer 初期化完了")
        if llm_client:
            print("   └─ TurnAdvisor 有効化済み（毎ターンLLM候補絞り込み）")
        print("   └─ BattleMemory 有効化済み（ターン間状態追跡）")
        print("   └─ BeliefState 有効化済み（隠れ情報の確率管理）")
        print("   └─ StyleUpdater 有効化済み（相手スタイル推定）")
        print("   └─ RiskAwareSolver 有効化済み（Secure/Gambleモード）")
        print("   └─ TacticalMixer 有効化済み（戦術テンプレ混合）")
        print("   └─ BattleRecorder 有効化済み（試合データベース記録）")
        print("   └─ StatParticleFilter 有効化済み（EV/実数値オンライン推定）")
        print("   └─ OpponentModelAdvisor 有効化済み（LLM相手モデル補正）")
        print("   └─ EndgameSolver 有効化済み（終盤読み切り）")
    


    def _normalize_name(self, name: str) -> str:
        """名前を正規化（小文字、スペース・ハイフン除去）"""
        return name.lower().replace("-", "").replace(" ", "").replace(".", "")

    def teampreview(self, battle: DoubleBattle):
        """
        選出（4体選択）- LLMでゲームプランを策定
        """
        from predictor.core.game_planner import GamePlanner
        
        # デバッグ：teampreviewフラグの確認
        print(f"\n🔍 DEBUG: teampreview呼び出し")
        print(f"    battle.teampreview = {battle.teampreview}")
        print(f"    battle.turn = {battle.turn}")
        print(f"    battle.battle_tag = {battle.battle_tag}")
        
        print(f"\n{'='*60}")
        print(f"📋 選出画面 - 6体から4体を選択")
        print(f"{'='*60}")
        
        # チーム情報を取得
        # battle.team.values()の順序は保証されないため、self.team_order_listを使用する
        my_team = [p.species for p in battle.team.values() if p]
        
        if self.team_order_list:
            print("\n【登録チーム順（インデックス基準）】")
            for i, name in enumerate(self.team_order_list):
                print(f"  {i+1}. {name}")
        else:
            print("\n【自分のチーム（順序不定）】")
            for i, name in enumerate(my_team):
                print(f"  {i+1}. {name}")
        
        opp_team = [p.species for p in battle.opponent_team.values() if p]
        
        print("\n【相手のチーム】")
        for i, name in enumerate(opp_team):
            print(f"  {i+1}. {name}")
        
        # ============= Phase 2: TacticalMixer で戦術選択 =============
        if hasattr(self, 'tactical_mixer'):
            selected_tactic = self.tactical_mixer.select_template(opponent_team=opp_team)
        
        # GamePlannerでプランを策定
        planner = GamePlanner(llm_client=getattr(self, '_llm_client', None) or self._get_llm_client())
        plan = planner.plan(my_team, opp_team, battle)
        
        # プランを表示
        print(plan)
        
        # プランに基づいて選出順を決定
        # self.team_order_listがある場合はそれを使ってインデックスを解決する
        if self.team_order_list:
            order = []
            
            print(f"\n  📋 選出マッピング (Original Team Order):")
            
            # 正規化マップ作成
            team_map = {self._normalize_name(name): i+1 for i, name in enumerate(self.team_order_list)}
            
            # 先発
            for name in plan.lead:
                norm = self._normalize_name(name)
                if norm in team_map and team_map[norm] not in order:
                    idx = team_map[norm]
                    order.append(idx)
                    print(f"    先発 {name} → インデックス {idx}")
                else:
                    print(f"    ⚠️ 先発 {name} が登録チームに見つからない")
            
            # 後発
            for name in plan.back:
                norm = self._normalize_name(name)
                if norm in team_map and team_map[norm] not in order:
                    idx = team_map[norm]
                    order.append(idx)
                    print(f"    後発 {name} → インデックス {idx}")
                else:
                    print(f"    ⚠️ 後発 {name} が登録チームに見つからない")
            
            # 補完
            if len(order) < 4:
                print(f"    ⚠️ 選出が{len(order)}体のみ、補完中...")
                for i in range(1, 7):
                    if i not in order and len(order) < 4:
                        order.append(i)
                        print(f"    补完: インデックス {i}")
            
            # order_str = "".join(str(i) for i in order[:4])
            # print(f"    最終選出順: {order_str}")
            # team_order = order_str # poke-envが/teamを付与するはず
            # 安全のため、poke-envの仕様（文字列をそのまま送る場合もある）に合わせて、
            # Player.teampreviewの戻り値はOrderオブジェクト推奨だが、
            # ここではpoke-envが / team を補完することを期待して Orderの文字列を返す
            # しかし、send_orderの実装によっては / がないと /choose move になる恐れも？
            # 実は poke-env の teampreview ハンドラは戻り値を            # 残りのポケモンを追加（Showdown仕様: 6体全ての順序を指定）
            # 選出する4体を先頭に、選出しない2体を後ろに配置
            for i in range(1, 7):
                if i not in order:
                    order.append(i)
            
            # 6体全ての順序を含む文字列を作成
            order_str = "".join(str(i) for i in order)
            print(f"    最終選出順: {order_str}")
            
            # /team コマンドを使用（これが最も確実）
            team_order = f"/team {order_str}"
        else:
            # 従来通り
            team_order = planner.get_team_order(plan, my_team)
            if not team_order.startswith('/team'):
                 team_order = f"/team {team_order}"
            
        print(f"\n🎯 選出コマンド: {team_order}")
        
        # ゲームプランを保存（後のターンで参照用）
        self.current_plan = plan
        
        # ===== Phase 3: 試合開始を記録 =====
        my_team_data = [{"species": p.species, "item": p.item, "ability": p.ability} 
                        for p in battle.team.values() if p]
        opp_team_data = [{"species": p.species} 
                         for p in battle.opponent_team.values() if p]
        game_plan_data = {
            "selected_leads": plan.leads if hasattr(plan, 'leads') else [],
            "win_condition": plan.win_condition if hasattr(plan, 'win_condition') else "",
            "threat_analysis": plan.threat_analysis if hasattr(plan, 'threat_analysis') else [],
        }
        
        self.battle_recorder.start_battle(
            battle=battle,
            my_team=my_team_data,
            opp_team=opp_team_data,
            game_plan=game_plan_data
        )
        
        return team_order
    
    def _prepare_game_plan(self, battle: DoubleBattle):
        """ゲームプランをLLMで策定して保存（選出コマンドは返さない）"""
        from predictor.core.game_planner import GamePlanner
        
        # チーム情報を取得
        my_team = [p.species for p in battle.team.values() if p]
        opp_team = [p.species for p in battle.opponent_team.values() if p]
        
        # GamePlannerでプランを策定
        planner = GamePlanner(llm_client=getattr(self, '_llm_client', None) or self._get_llm_client())
        plan = planner.plan(my_team, opp_team, battle)
        
        # プランを保存
        self.current_plan = plan
        print(f"  ✅ ゲームプラン策定完了")
    
    def _get_llm_client(self):
        """LLMクライアントを取得"""
        import os
        if os.environ.get("OPENAI_API_KEY"):
            from predictor.llm.llm_client import LLMClient
            return LLMClient()
        return None
    
    async def _handle_message(self, message):
        """メッセージハンドリング（ログ出力強化版）"""
        try:
            # メッセージを分割
            lines = message.split('\n')
            
            for line in lines:
                if not line: continue
                
                # Rawログ出力（完全・バッファリング回避）
                # print(f"[RAW] {line}", flush=True) # printが出ない場合があるため、loggerも併用
                pass 
                # Raw log is too verbose for normal user, but we enabled it for debugging.
                # Since print might be suppressed, we use formatted logger if needed, 
                # but let's stick to print with explicit flush and prefix.
                print(f"[RAW] {line}", flush=True)
                # self.logger.critical(f"[RAW] {line}") # Debugging only

                if line.startswith('>'): continue
                    
                parts = line.split('|')
                if len(parts) < 2: continue
                    
                cmd = parts[1]
                
                # === 簡易テキストログ ===
                if cmd == 'move':
                    # |move|p2a: Tornadus|Bleakwind Storm|p1b: Raging Bolt|[miss]
                    if len(parts) >= 4:
                        user = parts[2].replace('p1a: ', '').replace('p1b: ', '').replace('p2a: ', 'The opposing ').replace('p2b: ', 'The opposing ')
                        move = parts[3]
                        target_info = ""
                        if len(parts) > 4 and parts[4]:
                            target_name = parts[4].replace('p1a: ', '').replace('p1b: ', '').replace('p2a: ', 'The opposing ').replace('p2b: ', 'The opposing ')
                            target_info = f" (Target: {target_name})"
                        print(f"  🔊 {user} used {move}!{target_info}", flush=True)
                
                elif cmd == 'switch':
                    if len(parts) >= 4:
                        user = parts[2].replace('p1a: ', '').replace('p1b: ', '').replace('p2a: ', 'The opposing ').replace('p2b: ', 'The opposing ')
                        species = parts[3]
                        print(f"  🔄 {user} switched to {species}!", flush=True)

                elif cmd == 'faint':
                    if len(parts) >= 3:
                        user = parts[2].replace('p1a: ', '').replace('p1b: ', '').replace('p2a: ', 'The opposing ').replace('p2b: ', 'The opposing ')
                        print(f"  💀 {user} fainted!", flush=True)
                
                elif cmd == 'error':
                    print(f"  ❌ SERVER ERROR: {line}", flush=True)

        except Exception as e:
            print(f"Error in logging: {e}")
            
        # 親クラスの処理呼び出し
        await super()._handle_message(message)

    def choose_move(self, battle: DoubleBattle):
        """
        行動選択（ターンごと）- LLMで思考
        """
        import random
        from poke_env.player.battle_order import DoubleBattleOrder
        
        # teampreviewフェーズはpoke-envが自動的にteampreview()を呼び出すため、ここでは処理しない
        # 二重送信を防ぐために削除
        if battle.teampreview:
            print("\n🔍 DEBUG: choose_move内でteampreviewフェーズを検出 (スキップ)")
            # return "/choose default"
            # 実際にはここで何か返さないとエラーになる可能性があるが、
            # poke-envはteampreview中はchoose_moveを呼ばないはず（teampreview()を呼ぶ）。
            # もし呼ばれたら、それはteampreview後か、例外的な状態。
            # 安全のため、空の文字列か、teampreviewを呼ばずに完了するのを待つ。
            pass
        
        # ★重要★ 強制交代（Force Switch）のチェック
        # 片方のポケモンが瀕死などで交代が必要な場合、Predictor（技選択）ではなく
        # 交代ロジック（_make_random_order内の交代処理など）に委譲する必要がある。
        if any(battle.force_switch):
             print(f"\n⚠️ 強制交代（Force Switch）を検出: {battle.force_switch}")
             return self._make_random_order(battle)

        # 同じターンでの重複呼び出しを防止（リトライ機構付き）
        if battle.turn == self.last_turn:
            self.retry_count = getattr(self, 'retry_count', 0) + 1
            print(f"⚠️ RE-ENTRY DETECTED for Turn {battle.turn} (Retry {self.retry_count})", flush=True)
            
            if self.retry_count <= 1:
                 print("  🔄 Spurious error suspected. Retrying predicted move...", flush=True)
                 # リトライ時は再度予測ロジックを通す（実質同じ結果になるはず）
                 # ただし無限ループ防止のため予測メソッドを呼ぶ
                 # ここで return せず下流に流すことで再計算・再送信する
                 pass
            else:
                print("  🛑 Retry limit reached. Falling back to Random.", flush=True)
                return self._make_random_order(battle)
        else:
            self.retry_count = 0
        
        self.last_turn = battle.turn
        self.turn_count += 1
        
        # ============= Priority 2: BattleMemory 記録 =============
        if hasattr(self, 'battle_memory'):
            self.battle_memory.current_turn = battle.turn
            
            # 相手のポケモンから見えた技・持ち物・特性を記録
            for opp_pokemon in battle.opponent_active_pokemon:
                if opp_pokemon and not opp_pokemon.fainted:
                    species = opp_pokemon.species
                    
                    # 見えた技を記録
                    if hasattr(opp_pokemon, 'moves') and opp_pokemon.moves:
                        for move_id in opp_pokemon.moves.keys():
                            self.battle_memory.record_seen_move(species, move_id)
                    
                    # 見えた特性を記録
                    if opp_pokemon.ability:
                        self.battle_memory.record_seen_ability(species, opp_pokemon.ability)
                    
                    # 見えた持ち物を記録
                    if opp_pokemon.item:
                        self.battle_memory.record_seen_item(species, opp_pokemon.item)
                    
                    # テラスタルを記録
                    if hasattr(opp_pokemon, 'terastallized') and opp_pokemon.terastallized:
                        tera_type = opp_pokemon.terastallized if isinstance(opp_pokemon.terastallized, str) else "unknown"
                        self.battle_memory.record_terastallize(species, tera_type)
            
            # Protect連続回数を表示（次の判断に使う）
            for opp_pokemon in battle.opponent_active_pokemon:
                if opp_pokemon and not opp_pokemon.fainted:
                    consecutive = self.battle_memory.get_consecutive_protects(opp_pokemon.species)
                    if consecutive > 0:
                        print(f"  📊 {opp_pokemon.species}: Protect連続{consecutive}回目")
        
        # ============= Phase 2: BeliefUpdater 更新 =============
        if hasattr(self, 'belief_updater'):
            for opp_pokemon in battle.opponent_active_pokemon:
                if opp_pokemon and not opp_pokemon.fainted:
                    species = opp_pokemon.species
                    
                    # ポケモンの Belief を初期化（初回のみ）
                    if species.lower() not in self.belief_state.item_beliefs:
                        self.belief_state.initialize_pokemon(species)
                    
                    # 見えた技から型を推定
                    if hasattr(opp_pokemon, 'moves') and opp_pokemon.moves:
                        for move_id in opp_pokemon.moves.keys():
                            self.belief_updater.update_from_seen_move(species, move_id)
                    
                    # 見えた持ち物を確定
                    if opp_pokemon.item:
                        self.belief_updater.update_from_seen_item(species, opp_pokemon.item)
                    
                    # テラスタイプを確定
                    if hasattr(opp_pokemon, 'terastallized') and opp_pokemon.terastallized:
                        tera_type = opp_pokemon.terastallized if isinstance(opp_pokemon.terastallized, str) else str(opp_pokemon.terastallized)
                        self.belief_updater.update_from_tera(species, tera_type)
            
            # Belief サマリーを表示（デバッグ用）
            if battle.turn <= 3:  # 最初の3ターンだけ詳細表示
                print(f"  📊 BeliefState: {len(self.belief_state.item_beliefs)}体のポケモンを追跡中")
        
        # ============= Phase 2: StyleUpdater 更新 =============
        if hasattr(self, 'style_updater'):
            # 前ターンのログからスタイルを更新
            if hasattr(battle, '_messages') and battle._messages:
                for msg in battle._messages[-10:]:  # 最新10件のメッセージを確認
                    if isinstance(msg, str):
                        self.style_updater.update_from_turn_log(msg)
            
            # スタイルサマリーを表示
            if self.style_updater.style.protect_observations > 0:
                print(f"  📊 {self.style_updater.style.get_style_summary()}")
        
        # ============= Phase 2: RiskMode 判定 =============
        if hasattr(self, 'risk_solver'):
            # 現在の勝率を簡易推定（HP差から）
            our_hp_total = sum(p.current_hp_fraction for p in battle.active_pokemon if p and not p.fainted)
            opp_hp_total = sum(p.current_hp_fraction for p in battle.opponent_active_pokemon if p and not p.fainted)
            hp_diff = our_hp_total - opp_hp_total
            estimated_win_prob = 0.5 + hp_diff * 0.15  # 簡易推定
            
            mode_desc = self.risk_solver.get_mode_description(estimated_win_prob)
            print(f"  {mode_desc}")
        
        print(f"\n{'='*60}")
        print(f"📍 ターン {battle.turn}")
        print(f"{'='*60}")
        
        # 現在の状態を表示
        self._print_battle_state(battle)
        
        # アクティブがいない場合は交代が必要
        active_count = sum(1 for p in battle.active_pokemon if p and not p.fainted)
        if active_count == 0:
            print("\n⚠️ アクティブなし - 交代選択中...")
            self._print_available_switches(battle)
            
            # ★BUG-001/002 完全修正★ 
            # ターン0でアクティブがいない = まだチームプレビュー前
            # この場合、poke-env が teampreview() を呼ぶのを待つ必要がある
            # choose_move() からコマンドを送信すると競合するため、何も返さない
            if battle.turn == 0:
                print("\n🚫 ターン0 + アクティブなし = チームプレビュー待機")
                print("    → poke-env の teampreview() に処理を委譲（何も送信しない）")
                # ゲームプランを事前に策定しておく（teampreview で使用）
                if not hasattr(self, 'current_plan') or self.current_plan is None:
                    print("\n📋 ゲームプラン未設定 - 事前策定中...")
                    self._prepare_game_plan(battle)
                # None を返すことで、サーバーへの送信をスキップする
                # poke-env は None を受け取ると何も送信しない
                return None
            
            # ターン1以降でアクティブがいない場合は強制交代のはず
            # （force_switch のチェックは上で済んでいるが、念のため）
            print("\n⚠️ ターン1以降でアクティブなし - 交代選択へ...")
        
        # ============= 案1: TurnAdvisor で候補絞り込み =============
        turn_recommendation = None
        if hasattr(self, 'turn_advisor') and self.turn_advisor and hasattr(self, '_llm_client') and self._llm_client:
            try:
                print(f"\n🤖 TurnAdvisor: 有望な候補を問い合わせ中...")
                turn_recommendation = self.turn_advisor.advise(battle, self.current_plan)
                
                if turn_recommendation:
                    print(f"  推奨技 スロット0: {turn_recommendation.slot0_moves}")
                    print(f"  推奨技 スロット1: {turn_recommendation.slot1_moves}")
                    print(f"  Protect推奨: {turn_recommendation.should_protect}")
                    print(f"  理由: {turn_recommendation.reasoning}")
                    if turn_recommendation.risk_warning:
                        print(f"  ⚠️ リスク: {turn_recommendation.risk_warning}")
                    print(f"  プラン遂行度: {turn_recommendation.plan_alignment:.1%}")
            except Exception as e:
                print(f"  ⚠️ TurnAdvisor エラー: {e}")
        
        # 予測実行
        start_time = time.time()
        try:
            result = self.predictor.predict(battle)
            elapsed = time.time() - start_time
            
            print(f"\n⏱️ 予測時間: {elapsed:.2f}秒")
            print(f"\n{result}")
            
            # ===== Phase 3: ターン開始を記録 =====
            win_prob = result.win_prob if hasattr(result, 'win_prob') else 0.5
            risk_mode_str = "neutral"
            if hasattr(self, 'risk_solver'):
                mode = self.risk_solver.determine_mode(win_prob)
                # RiskMode Enum を文字列に変換
                risk_mode_str = mode.value if hasattr(mode, 'value') else str(mode)
            
            advisor_data = None
            if turn_recommendation:
                advisor_data = {
                    "slot0_moves": list(turn_recommendation.slot0_moves) if turn_recommendation.slot0_moves else [],
                    "slot1_moves": list(turn_recommendation.slot1_moves) if turn_recommendation.slot1_moves else [],
                    "should_protect": turn_recommendation.should_protect,
                    "reasoning": turn_recommendation.reasoning,
                    "plan_alignment": turn_recommendation.plan_alignment,
                }
            
            # 予測行動を記録
            predicted_my = {"best_action": str(result.best_action) if hasattr(result, 'best_action') else ""}
            predicted_opp = {"top_opponent_actions": [str(a) for a in result.opponent_actions[:3]] if hasattr(result, 'opponent_actions') else []}
            
            self.battle_recorder.record_turn_start(
                battle=battle,
                turn_number=battle.turn,
                predicted_win_prob=win_prob,
                predicted_my_action=predicted_my,
                predicted_opp_action=predicted_opp,
                risk_mode=risk_mode_str,
                advisor_recommendation=advisor_data,
            )
            
            # ============= 案2: ゲームプラン参照 =============
            if hasattr(self, 'current_plan') and self.current_plan:
                print(f"\n🎯 ゲームプランに基づいて行動選択中...")
                print(f"   勝ち筋: {self.current_plan.win_condition}")
                if self.current_plan.primary_threats:
                    # 相手のアクティブに脅威がいるか確認
                    for p in battle.opponent_active_pokemon:
                        if p and not p.fainted and self.current_plan.is_primary_threat(p.species):
                            print(f"   ⚠️ 主要脅威 {p.species} が場にいます！優先的に処理を検討")
                self._print_llm_action_recommendation(battle, result)
            
            # ★重要★ 予測結果から最適行動を選択（TurnAdvisorの推奨も考慮）
            return self._make_predicted_order(battle, result, turn_recommendation)
            
        except Exception as e:
            print(f"\n⚠️ 予測エラー: {e}")
            import traceback
            traceback.print_exc()
            # エラー時のみランダム
            return self._make_random_order(battle)
    
    def _print_llm_action_recommendation(self, battle: DoubleBattle, prediction_result):
        """LLMベースの行動推奨を表示"""
        if not hasattr(self, 'current_plan'):
            return
        
        plan = self.current_plan
        
        # 現在のアクティブポケモン
        active_names = []
        for p in battle.active_pokemon:
            if p and not p.fainted:
                active_names.append(p.species)
        
        # 相手のアクティブ
        opp_active = []
        for p in battle.opponent_active_pokemon:
            if p and not p.fainted:
                opp_active.append(p.species)
        
        print(f"\n  📋 現在の対戦：{active_names} vs {opp_active}")
        
        # 個別対策を参照
        for opp_name in opp_active:
            # 正規化して対策を検索
            for key, strategy in plan.matchup_analysis.items():
                if key.lower().replace("-", "").replace(" ", "") == opp_name.lower().replace("-", "").replace(" ", ""):
                    print(f"    → vs {opp_name}: {strategy}")
    
    def _make_random_order(self, battle: DoubleBattle):
        """ランダムな行動を選択"""
        import random
        from poke_env.player.battle_order import DoubleBattleOrder
        
        orders = []
        
        # force_switchで交代が必要なスロットを確認
        force_switch = getattr(battle, 'force_switch', [False, False])
        
        # force_switchの状態を確認
        any_force = any(force_switch)
        
        if any_force:
            # === 強制交代モード ===
            # force_switchがTrueのスロットのみ交代を選択
            print(f"  🔄 強制交代モード: force_switch={force_switch}")
            used_species = set()
            
            for i in range(2):
                if i < len(force_switch) and force_switch[i]:
                    # 交代が必要
                    if i < len(battle.available_switches) and battle.available_switches[i]:
                        available = [s for s in battle.available_switches[i] if s.species not in used_species]
                        if available:
                            switch = random.choice(available)
                            used_species.add(switch.species)
                            orders.append(self.create_order(switch))
                            print(f"    → Slot{i}: {switch.species}に交代")
                        else:
                            print(f"    → Slot{i}: 交代先なし")
                            orders.append(None)
                    else:
                        print(f"    → Slot{i}: 交代不可（available_switches空）")
                        orders.append(None)
                else:
                    # 交代不要（Pass）
                    orders.append(None)
            
            # force_switch時は交代だけを返す（技選択は不要）
            if len(orders) >= 2:
                result_order = DoubleBattleOrder(orders[0], orders[1])
            elif len(orders) == 1:
                result_order = DoubleBattleOrder(orders[0], None)
            else:
                print("  ⚠️ 交代先なし - デフォルト")
                result_order = self.choose_default_move()
            
            print(f"DEBUG: choose_move (switch) returning: {result_order!s} (force_switch={force_switch})", flush=True)
            return result_order
        
        else:
            # === 通常行動モード ===
            # 両方のポケモンの技選択
            for i in range(2):
                pokemon = battle.active_pokemon[i] if i < len(battle.active_pokemon) else None
                if pokemon is None or pokemon.fainted:
                    continue
                
                available_moves = list(battle.available_moves[i]) if i < len(battle.available_moves) else []
                available_switches = list(battle.available_switches[i]) if i < len(battle.available_switches) else []
                
                if available_moves:
                    move = random.choice(available_moves)
                    # ターゲットが必要な場合
                    target = 0
                    # ターゲットが必要な場合
                    target = 0
                    if hasattr(move, 'target'):
                        # Enum対応 & 正規化
                        mt = move.target
                        mt_str = (mt.name if hasattr(mt, 'name') else str(mt)).lower().replace("_", "").replace("-", "")
                        
                        if mt_str in ("normal", "any"):
                            opp_active = [j for j, p in enumerate(battle.opponent_active_pokemon) if p and not p.fainted]
                            if opp_active:
                                target_idx = random.choice(opp_active)
                                target = target_idx + 1 # 1 or 2 (Opponents)
                                
                    order = self.create_order(move, move_target=target)
                    orders.append(order)
                elif available_switches:
                    switch = random.choice(available_switches)
                    orders.append(self.create_order(switch))
            
            # 通常行動の返却
            if len(orders) >= 2:
                result_order = DoubleBattleOrder(orders[0], orders[1])
            elif len(orders) == 1:
                # Double Battleで1つしかオーダーがない場合、2つ目はNone (Pass) にする
                print("  ⚠️ オーダー不足 - Noneで補完")
                result_order = DoubleBattleOrder(orders[0], None)
            else:
                print("  ⚠️ 行動なし - デフォルト選択")
                result_order = self.choose_default_move()
            
            print(f"DEBUG: choose_move (random) returning: {result_order!s}", flush=True)
            return result_order
    
    def _make_predicted_order(self, battle: DoubleBattle, result, turn_recommendation=None):
        """予測結果から最適行動を選択（TurnAdvisorの推奨も考慮）"""
        from poke_env.player.battle_order import DoubleBattleOrder
        from predictor.engine.simulator_adapter import ActionType
        
        best_action = result.best_action
        if not best_action:
            print("  ⚠️ 最善手なし - ランダム選択")
            return self._make_random_order(battle)
        
        orders = []
        
        # ============= TurnAdvisor の推奨を事前処理 =============
        should_protect = [False, False]
        should_tera = [False, False]
        should_switch = [False, False]
        switch_to = [None, None]
        
        if turn_recommendation:
            should_protect = turn_recommendation.should_protect or [False, False]
            should_switch = turn_recommendation.should_switch or [False, False]
            # should_tera は slot0, slot1 のデータから取得
            # TurnRecommendation が拡張されている場合に対応
            if hasattr(turn_recommendation, 'slot0_tera'):
                should_tera[0] = turn_recommendation.slot0_tera
            if hasattr(turn_recommendation, 'slot1_tera'):
                should_tera[1] = turn_recommendation.slot1_tera
        
        # Slot0, Slot1の行動を処理
        for i, order in enumerate([best_action.slot0, best_action.slot1]):
            # アクティブポケモン確認
            pokemon = battle.active_pokemon[i] if i < len(battle.active_pokemon) else None
            
            # 既に瀕死や存在しない場合はNone
            if pokemon is None or pokemon.fainted:
                orders.append(None)
                continue
            
            available_moves = battle.available_moves[i] if i < len(battle.available_moves) else []
            
            # ============= 交代判断: MCTS評価結果を優先 =============
            # TurnAdvisorの should_switch は「ヒント表示」のみ
            # 実際の行動選択は MCTS 評価結果（order.action_type）に従う
            if i < len(should_switch) and should_switch[i]:
                hp_pct = int(pokemon.current_hp_fraction * 100)
                print(f"  💡 Slot{i} ({pokemon.species} HP{hp_pct}%): TurnAdvisorが交代推奨（ヒント）")
                # 実際の判断は MCTS 結果（order）に委ねる
                # continue しない → 以下の order.action_type 判定に進む
            
            # ============= Protect 推奨の処理 =============
            if i < len(should_protect) and should_protect[i]:
                # Protect/Detect/Spiky Shield 等を探す
                protect_moves = [m for m in available_moves if m.id in ('protect', 'detect', 'spikyshield', 'silktrap', 'kingsshield', 'banefulbunker', 'obstruct', 'burningbulwark')]
                if protect_moves:
                    protect_move = protect_moves[0]
                    
                    # ============= 2連守の確率判定 =============
                    # 連続成功確率: 1回目100% → 2回目33% → 3回目11%
                    consecutive_protects = 0
                    if hasattr(self, 'battle_memory') and self.battle_memory:
                        # 自分のポケモンの連続Protect回数を確認
                        consecutive_protects = self.battle_memory.get_consecutive_protects(pokemon.species)
                    
                    if consecutive_protects >= 1:
                        # 2連守以上は勝率が非常に高い時のみ使用
                        success_prob = 1.0 / (3 ** consecutive_protects)  # 33%, 11%, 3.7%...
                        current_win_prob = getattr(result, 'win_prob', 0.5)
                        
                        # 勝率65%以上でないと2連守は使わない
                        if current_win_prob < 0.65:
                            print(f"  ⚠️ Slot{i}: 2連守は成功率{success_prob*100:.1f}%、勝率{current_win_prob*100:.1f}%では使用しない")
                        else:
                            print(f"  🛡️ Slot{i}: 2連守（成功率{success_prob*100:.1f}%）だが勝率{current_win_prob*100:.1f}%なので使用")
                            orders.append(self.create_order(protect_move, move_target=0, terastallize=False))
                            continue
                    else:
                        # 1連守は通常通り使用
                        print(f"  🛡️ Slot{i}: TurnAdvisor が Protect 推奨 → {protect_move.id} を選択")
                        orders.append(self.create_order(protect_move, move_target=0, terastallize=False))
                        continue
                else:
                    print(f"  ⚠️ Slot{i}: Protect 推奨だが技がない - 通常行動")
            
            print(f"  Slot{i} Action: {order}")
            
            if order.action_type == ActionType.PASS:
                orders.append(None)
                
            elif order.action_type == ActionType.SWITCH:
                # 交代
                available_switches = battle.available_switches[i]
                if order.switch_index is not None and 0 <= order.switch_index < len(available_switches):
                    switch_mon = available_switches[order.switch_index]
                    orders.append(self.create_order(switch_mon))
                else:
                    print(f"    ⚠️ 交代先インデックス不正或者なし ({order.switch_index}) - ランダム交代")
                    if available_switches:
                        orders.append(self.create_order(available_switches[0]))
                    else:
                        orders.append(None)
                        
            elif order.action_type in (ActionType.MOVE, ActionType.TERA_MOVE):
                # 技
                move_id = order.move_id
                
                # IDで技を検索
                found_move = next((m for m in available_moves if m.id == move_id), None)
                
                if found_move:
                    # ============= テラスタル推奨の処理 =============
                    should_use_tera = (order.action_type == ActionType.TERA_MOVE)
                    
                    # TurnAdvisor がテラス推奨 かつ テラス可能なら切る
                    if i < len(should_tera) and should_tera[i]:
                        # テラスタルが可能かチェック
                        can_tera = hasattr(battle, 'can_terastallize') and battle.can_terastallize
                        if not hasattr(battle, 'can_terastallize'):
                            # 属性がない場合はアクティブポケモンから推定
                            can_tera = not getattr(pokemon, 'terastallized', False)
                        
                        if can_tera:
                            should_use_tera = True
                            print(f"  ⚡ Slot{i}: TurnAdvisor がテラス推奨 → テラスタルを切る")
                    
                    terastallize = should_use_tera
                    
                    # ターゲット変換
                    raw_target = order.target
                    if raw_target == -1: target = 1
                    elif raw_target == -2: target = 2
                    elif raw_target == 1: target = -1
                    elif raw_target == 2: target = -2
                    else: target = raw_target
                    
                    # スプレッド技や自分対象技の場合、ターゲット指定を除外
                    if hasattr(found_move, 'target'):
                        mt = found_move.target
                        print(f"DEBUG: Move {found_move.id} target={mt} (type={type(mt)})", flush=True)
                        
                        no_target_types = (
                            'alladjacentfoes', 'alladjacent', 'self', 'allies', 
                            'allyside', 'foeside', 'all', 'field'
                        )
                        mt_str = (mt.name if hasattr(mt, 'name') else str(mt)).lower().replace("_", "").replace("-", "")
                        
                        if mt_str in no_target_types:
                             print(f"    ⚠️ Spread/Self Move ({found_move.id}, target={mt}) - Removing target index")
                             target = 0
                    
                    orders.append(self.create_order(found_move, move_target=target, terastallize=terastallize))
                    print(f"    🚀 コマンド生成: {found_move.id} (orig={raw_target}, conv={target}, tera={terastallize})", flush=True)
                else:
                    print(f"    ⚠️ 技が見つかりません ({move_id}) - ランダム技")
                    if available_moves:
                        orders.append(self.create_order(available_moves[0]))
                    else:
                        orders.append(None)
            else:
                orders.append(None)

        # DoubleBattleOrder作成
        if len(orders) >= 2:
            result_order = DoubleBattleOrder(orders[0], orders[1])
        elif len(orders) == 1:
            result_order = DoubleBattleOrder(orders[0], None)
        else:
            result_order = self._make_random_order(battle)
            
        print(f"DEBUG: choose_move (predicted) returning: {result_order!s}", flush=True)
        return result_order

    def _make_switch_order(self, battle: DoubleBattle):
        """交代選択（force_switch時）"""
        import random
        from poke_env.player.battle_order import DoubleBattleOrder
        
        orders = []
        used_switches = set()
        
        # force_switchで交代が必要なスロットのみ処理
        force_switch = getattr(battle, 'force_switch', [False, False])
        print(f"  🔄 _make_switch_order: force_switch={force_switch}")
        
        for i in range(2):
            if i < len(force_switch) and force_switch[i]:
                if i < len(battle.available_switches) and battle.available_switches[i]:
                    available = [s for s in battle.available_switches[i] if s.species not in used_switches]
                    if available:
                        switch = random.choice(available)
                        used_switches.add(switch.species)
                        orders.append(self.create_order(switch))
                        print(f"  → Slot{i}: {switch.species}に交代")
        
        if len(orders) >= 2:
            return DoubleBattleOrder(orders[0], orders[1])
        elif len(orders) == 1:
            # Double Battleで1つしかオーダーがない場合、2つ目はNone (Pass) にする
            print("  ⚠️ オーダー不足 (Switch) - Noneで補完")
            return DoubleBattleOrder(orders[0], None)
        else:
            # 本当に何もできない場合はデフォルト
            return self.choose_default_move()
    
    def _print_available_switches(self, battle: DoubleBattle):
        """交代可能なポケモンを表示"""
        print("\n【交代可能】")
        for i in range(2):
            if i < len(battle.available_switches) and battle.available_switches[i]:
                switches = list(battle.available_switches[i])
                names = [s.species for s in switches]
                print(f"  Slot{i}: {', '.join(names)}")
    
    def _print_battle_state(self, battle: DoubleBattle):
        """バトル状態を表示"""
        print("\n【自分のアクティブ】")
        for i, p in enumerate(battle.active_pokemon):
            if p and not p.fainted:
                hp = int(p.current_hp_fraction * 100)
                status = f" [{p.status.name}]" if p.status else ""
                print(f"  Slot{i}: {p.species} HP{hp}%{status}")
        
        print("\n【相手のアクティブ】")
        for i, p in enumerate(battle.opponent_active_pokemon):
            if p and not p.fainted:
                hp = int(p.current_hp_fraction * 100)
                status = f" [{p.status.name}]" if p.status else ""
                print(f"  Slot{i}: {p.species} HP{hp}%{status}")
        
        # 残数（選出された4体のみをカウント）
        # teamに入っているポケモンが選出されたポケモン
        # ただし、battle開始後はteamに4体しかいないはず
        self_remaining = sum(1 for p in battle.team.values() if p and not p.fainted)
        
        # 相手の残数は「判明している中での残数」
        # opponent_teamには見えたポケモンしか入っていない
        opp_seen = len([p for p in battle.opponent_team.values() if p])  # 判明している数
        opp_alive = sum(1 for p in battle.opponent_team.values() if p and not p.fainted)
        opp_fainted = opp_seen - opp_alive
        
        # 相手の選出は4体。見えていない選出がいる可能性
        # ただしBo3のlobbyでは6体見えてしまうので、activeと控えで計算
        opp_active_count = sum(1 for p in battle.opponent_active_pokemon if p and not p.fainted)
        opp_bench = [p for p in battle.opponent_team.values() if p and not p.fainted and p not in battle.opponent_active_pokemon]
        
        # VGCでは選出は4体
        MAX_VGC_SELECTION = 4
        opp_alive_actual = opp_active_count + len(opp_bench)
        
        # 見えてない選出がある可能性（最大4体 - 判明している生存数）
        opp_unseen = max(0, MAX_VGC_SELECTION - opp_seen) if opp_seen < MAX_VGC_SELECTION else 0
        
        # VGCでは最大4体なので調整
        self_remaining = min(self_remaining, MAX_VGC_SELECTION)
        opp_remaining = min(opp_alive_actual, MAX_VGC_SELECTION)
        
        if opp_unseen > 0:
            print(f"\n📊 残数: 自分 {self_remaining}/4 vs 相手 {opp_remaining}/4 (+控え未確認)")
        else:
            print(f"\n📊 残数: 自分 {self_remaining}/4 vs 相手 {opp_remaining}/4")
        
        # 控え表示（自分）
        bench = [p for p in battle.team.values() if p and not p.fainted and p not in battle.active_pokemon]
        if bench:
            print(f"【自分の控え】{', '.join(p.species for p in bench)}")
        
        # 相手の判明している控え
        opp_bench = [p for p in battle.opponent_team.values() if p and not p.fainted and p not in battle.opponent_active_pokemon]
        if opp_bench:
            print(f"【相手の判明控え】{', '.join(p.species for p in opp_bench)}")


async def main():
    """メイン"""
    import random
    import string
    
    # ユニークな名前を生成
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    player_name = f"VGCPred_{suffix}"
    
    print("="*60)
    print("🚀 VGCPredictor 試運転")
    print("="*60)
    print()
    print("Showdownサーバー: localhost:8000")
    print("フォーマット: gen9vgc2026regfbo3")  # BO3形式（オープンチームシート）
    print(f"プレイヤー名: {player_name}")
    print()
    
    # チーム設定
    TEAM = """
Flutter Mane @ Booster Energy  
Ability: Protosynthesis  
Level: 50  
Tera Type: Fairy  
EVs: 244 HP / 244 Def / 20 Spe  
Bold Nature  
IVs: 0 Atk  
- Moonblast  
- Icy Wind  
- Thunder Wave  
- Taunt  

Gholdengo @ Metal Coat  
Ability: Good as Gold  
Level: 50  
Tera Type: Water  
EVs: 244 HP / 4 Def / 132 SpA / 4 SpD / 124 Spe  
Modest Nature  
- Make It Rain  
- Shadow Ball  
- Nasty Plot  
- Protect  

Ogerpon-Wellspring (F) @ Wellspring Mask  
Ability: Water Absorb  
Level: 50  
Tera Type: Water  
EVs: 188 HP / 60 Atk / 4 Def / 4 SpD / 252 Spe  
Jolly Nature  
- Ivy Cudgel  
- Horn Leech  
- Follow Me  
- Spiky Shield  

Landorus @ Life Orb  
Ability: Sheer Force  
Level: 50  
Tera Type: Poison  
EVs: 52 HP / 4 Def / 196 SpA / 4 SpD / 252 Spe  
Modest Nature  
IVs: 0 Atk  
- Earth Power  
- Sludge Bomb  
- Substitute  
- Protect  

Arcanine-Hisui @ Choice Band  
Ability: Intimidate  
Level: 50  
Tera Type: Grass  
EVs: 68 HP / 252 Atk / 4 Def / 4 SpD / 180 Spe  
Adamant Nature  
- Flare Blitz  
- Rock Slide  
- Extreme Speed  
- Head Smash  

Raging Bolt @ Assault Vest  
Ability: Protosynthesis  
Level: 50  
Tera Type: Electric  
EVs: 188 HP / 4 Def / 244 SpA / 4 SpD / 68 Spe  
Modest Nature  
IVs: 20 Atk  
- Dragon Pulse  
- Thunderbolt  
- Thunderclap  
- Electroweb  
"""
    
    # チーム情報をパースして種族リストを作成
    team_lines = TEAM.strip().split('\n')
    original_team_species = []
    
    # ブロックの先頭行（種族名）を抽出するためのフラグ
    is_new_block = True
    
    for line in team_lines:
        line = line.strip()
        if not line:
            is_new_block = True
            continue
            
        if is_new_block:
            # Species @ Item or Species
            if "@" in line:
                species = line.split("@")[0].strip()
            else:
                # 性別 (M) (F) の除去
                parts = line.split()
                if parts and parts[-1] in ["(M)", "(F)"]:
                    species = " ".join(parts[:-1])
                else:
                    species = line
            
            if species:
                original_team_species.append(species)
            
            is_new_block = False
            
    print(f"📋 チーム構成 (解析済み): {original_team_species}")

    # プレイヤー作成
    from poke_env import AccountConfiguration
    player = VGCPredictorPlayer(
        # アカウント設定（名前を指定）
        account_configuration=AccountConfiguration(player_name, None),
        battle_format="gen9vgc2026regfbo3",  # BO3形式
        server_configuration=LocalhostServerConfiguration,
        max_concurrent_battles=1,
        team=TEAM,
        team_order_list=original_team_species,  # オリジナルの順序を渡す
    )
    
    print("📡 Showdownに接続中...")
    print()
    print("=" * 60)
    print(f"⚡ チャレンジを待機中...")
    print(f"  Showdownで /challenge {player_name} gen9vgc2026regfbo3")
    print("=" * 60)
    
    # チャレンジ待機
    await player.accept_challenges(None, 1)
    
    print("\n✅ 試運転完了！")


if __name__ == "__main__":
    asyncio.run(main())
