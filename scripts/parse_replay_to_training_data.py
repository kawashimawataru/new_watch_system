#!/usr/bin/env python3
"""
Showdownリプレイから訓練データ生成

776試合のリプレイを BattleState + TurnAction のペアに変換し、
Behavioral Cloning (BC) 訓練用のデータセットを作成する。

Usage:
    python scripts/parse_replay_to_training_data.py \
        --input data/replays/*.json \
        --output data/training/expert_trajectories.json

Output:
    [
        {
            "replay_id": "gen9vgc2025regh-2483659665",
            "turn": 1,
            "state": {
                "p1_active": [...],
                "p2_active": [...],
                "field": {...}
            },
            "action": {
                "p1_move_1": "Moonblast",
                "p1_target_1": "p2a",
                "p1_move_2": "Flare Blitz",
                "p1_target_2": "p2b"
            },
            "outcome": 1 or -1 (p1 win = 1, p2 win = -1)
        },
        ...
    ]
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class PokemonState:
    """ポケモンの状態"""
    species: str
    nickname: Optional[str]
    hp_current: int  # HP% (0-100)
    hp_max: int = 100
    status: Optional[str] = None  # burn, paralysis, sleep, etc.
    ability: Optional[str] = None
    item: Optional[str] = None
    terastallized: bool = False
    tera_type: Optional[str] = None


@dataclass
class BattleStateSnapshot:
    """1ターンの盤面状態"""
    turn: int
    p1_active: List[PokemonState]  # 2体まで
    p2_active: List[PokemonState]
    p1_reserves: List[str]  # 控えポケモン（種族名のみ）
    p2_reserves: List[str]
    weather: Optional[str] = None
    terrain: Optional[str] = None


@dataclass
class TurnActionRecord:
    """1ターンの行動記録"""
    p1_actions: List[Dict[str, str]]  # [{"type": "move", "move": "Moonblast", "target": "p2a"}, ...]
    p2_actions: List[Dict[str, str]]


@dataclass
class TrainingExample:
    """訓練データ1サンプル"""
    replay_id: str
    turn: int
    state: BattleStateSnapshot
    action: TurnActionRecord
    outcome: int  # 1 = p1勝利, -1 = p2勝利, 0 = 引き分け


class ShowdownLogParser:
    """
    Pokemon Showdownのログをパース
    
    ログ形式:
    - |switch|p1a: Grimmsnarl|Grimmsnarl, L50, M|100/100
    - |move|p2b: Jesus Christ|Extreme Speed|p1a: Grimmsnarl
    - |-damage|p1a: Grimmsnarl|21/100
    - |turn|2
    """
    
    def __init__(self):
        # 現在の盤面状態を追跡
        self.current_state = {
            "p1_active": {},  # {slot: PokemonState}
            "p2_active": {},
            "p1_reserves": [],
            "p2_reserves": [],
            "p1_team": {},  # {species: full_info}
            "p2_team": {},
            "weather": None,
            "terrain": None,
        }
        
        # 各ターンの行動記録
        self.turn_actions = {
            "p1": [],
            "p2": []
        }
        
        # 訓練データ
        self.training_examples: List[TrainingExample] = []
    
    def parse_replay(self, replay: Dict) -> List[TrainingExample]:
        """
        1つのリプレイをパース
        
        Args:
            replay: {
                "id": str,
                "log": str,
                "winner": str or None
            }
        
        Returns:
            訓練データリスト
        """
        replay_id = replay["id"]
        log_text = replay["log"]
        winner = self._determine_winner(log_text)
        
        # 初期化
        self.current_state = {
            "p1_active": {},
            "p2_active": {},
            "p1_reserves": [],
            "p2_reserves": [],
            "p1_team": {},
            "p2_team": {},
            "weather": None,
            "terrain": None,
        }
        self.training_examples = []
        
        # ログを行ごとに処理
        lines = log_text.split("\n")
        current_turn = 0
        turn_start_idx = 0
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # チーム構成の記録（戦闘前）
            if line.startswith("|poke|"):
                self._parse_poke(line)
            
            # ターン開始
            elif line.startswith("|turn|"):
                # 前のターンの訓練データを保存
                if current_turn > 0:
                    self._save_training_example(
                        replay_id, current_turn, winner
                    )
                
                current_turn = int(line.split("|")[2])
                self.turn_actions = {"p1": [], "p2": []}
            
            # ポケモン交代
            elif line.startswith("|switch|"):
                self._parse_switch(line)
            
            # 技使用
            elif line.startswith("|move|"):
                self._parse_move(line)
            
            # ダメージ
            elif line.startswith("|-damage|"):
                self._parse_damage(line)
            
            # 天候
            elif line.startswith("|-weather|"):
                self._parse_weather(line)
            
            # フィールド
            elif line.startswith("|-fieldstart|"):
                self._parse_field(line)
            
            # テラスタル
            elif line.startswith("|-terastallize|"):
                self._parse_terastallize(line)
            
            # 状態異常
            elif line.startswith("|-status|"):
                self._parse_status(line)
            
            # ひんし
            elif line.startswith("|faint|"):
                self._parse_faint(line)
        
        return self.training_examples
    
    def _parse_poke(self, line: str):
        """チーム構成を記録"""
        # |poke|p1|Groudon, L50|
        parts = line.split("|")
        player = parts[2]
        pokemon_info = parts[3]
        
        # 種族名を抽出
        species = pokemon_info.split(",")[0].strip()
        
        team_key = f"{player}_team"
        if team_key in self.current_state:
            self.current_state[team_key][species] = pokemon_info
    
    def _parse_switch(self, line: str):
        """ポケモン交代をパース"""
        # |switch|p1a: Grimmsnarl|Grimmsnarl, L50, M|100/100
        parts = line.split("|")
        slot_info = parts[2]  # "p1a: Grimmsnarl"
        pokemon_info = parts[3]  # "Grimmsnarl, L50, M"
        hp_info = parts[4] if len(parts) > 4 else "100/100"
        
        # スロットとニックネームを抽出
        slot_match = re.match(r"(p\d[ab]):\s*(.+)", slot_info)
        if not slot_match:
            return
        
        slot = slot_match.group(1)  # "p1a"
        nickname = slot_match.group(2)  # "Grimmsnarl"
        
        # 種族名を抽出
        species = pokemon_info.split(",")[0].strip()
        
        # HPをパース
        hp_current, hp_max = self._parse_hp(hp_info)
        
        # プレイヤーとスロット番号
        player = slot[:2]  # "p1" or "p2"
        slot_num = 0 if slot.endswith("a") else 1
        
        # PokemonStateを作成
        pokemon = PokemonState(
            species=species,
            nickname=nickname,
            hp_current=hp_current,
            hp_max=hp_max
        )
        
        # 盤面に追加
        active_key = f"{player}_active"
        self.current_state[active_key][slot_num] = pokemon
    
    def _parse_move(self, line: str):
        """技使用をパース"""
        # |move|p2b: Jesus Christ|Extreme Speed|p1a: Grimmsnarl
        parts = line.split("|")
        user_info = parts[2]  # "p2b: Jesus Christ"
        move_name = parts[3]  # "Extreme Speed"
        target_info = parts[4] if len(parts) > 4 else None  # "p1a: Grimmsnarl"
        
        # ユーザーのスロットを抽出
        user_match = re.match(r"(p\d[ab]):", user_info)
        if not user_match:
            return
        
        user_slot = user_match.group(1)  # "p2b"
        player = user_slot[:2]  # "p2"
        
        # ターゲットのスロットを抽出
        target_slot = None
        if target_info:
            target_match = re.match(r"(p\d[ab]):", target_info)
            if target_match:
                target_slot = target_match.group(1)
        
        # 行動を記録
        action = {
            "type": "move",
            "slot": user_slot,
            "move": move_name,
            "target": target_slot
        }
        
        self.turn_actions[player].append(action)
    
    def _parse_damage(self, line: str):
        """ダメージをパース"""
        # |-damage|p1a: Grimmsnarl|21/100
        parts = line.split("|")
        if len(parts) < 4:
            return
        
        slot_info = parts[2]
        hp_info = parts[3]
        
        # スロットを抽出
        slot_match = re.match(r"(p\d[ab]):", slot_info)
        if not slot_match:
            return
        
        slot = slot_match.group(1)
        player = slot[:2]
        slot_num = 0 if slot.endswith("a") else 1
        
        # HPを更新
        hp_current, hp_max = self._parse_hp(hp_info)
        
        active_key = f"{player}_active"
        if slot_num in self.current_state[active_key]:
            self.current_state[active_key][slot_num].hp_current = hp_current
            self.current_state[active_key][slot_num].hp_max = hp_max
    
    def _parse_weather(self, line: str):
        """天候をパース"""
        # |-weather|SunnyDay|[from] ability: Drought|[of] p1b: Groudon
        parts = line.split("|")
        if len(parts) >= 3:
            weather = parts[2]
            self.current_state["weather"] = weather if weather != "none" else None
    
    def _parse_field(self, line: str):
        """フィールドをパース"""
        # |-fieldstart|move: Grassy Terrain|[from] ability: Grassy Surge
        parts = line.split("|")
        if len(parts) >= 3:
            field_info = parts[2]
            if "Terrain" in field_info:
                terrain = field_info.replace("move: ", "").replace(" Terrain", "")
                self.current_state["terrain"] = terrain
    
    def _parse_terastallize(self, line: str):
        """テラスタルをパース"""
        # |-terastallize|p1a: Calyrex|Water
        parts = line.split("|")
        if len(parts) >= 4:
            slot_info = parts[2]
            tera_type = parts[3]
            
            slot_match = re.match(r"(p\d[ab]):", slot_info)
            if slot_match:
                slot = slot_match.group(1)
                player = slot[:2]
                slot_num = 0 if slot.endswith("a") else 1
                
                active_key = f"{player}_active"
                if slot_num in self.current_state[active_key]:
                    self.current_state[active_key][slot_num].terastallized = True
                    self.current_state[active_key][slot_num].tera_type = tera_type
    
    def _parse_status(self, line: str):
        """状態異常をパース"""
        # |-status|p1a: Grimmsnarl|brn
        parts = line.split("|")
        if len(parts) >= 4:
            slot_info = parts[2]
            status = parts[3]
            
            slot_match = re.match(r"(p\d[ab]):", slot_info)
            if slot_match:
                slot = slot_match.group(1)
                player = slot[:2]
                slot_num = 0 if slot.endswith("a") else 1
                
                active_key = f"{player}_active"
                if slot_num in self.current_state[active_key]:
                    self.current_state[active_key][slot_num].status = status
    
    def _parse_faint(self, line: str):
        """ひんしをパース"""
        # |faint|p1a: Grimmsnarl
        parts = line.split("|")
        if len(parts) >= 3:
            slot_info = parts[2]
            
            slot_match = re.match(r"(p\d[ab]):", slot_info)
            if slot_match:
                slot = slot_match.group(1)
                player = slot[:2]
                slot_num = 0 if slot.endswith("a") else 1
                
                active_key = f"{player}_active"
                if slot_num in self.current_state[active_key]:
                    self.current_state[active_key][slot_num].hp_current = 0
    
    def _parse_hp(self, hp_str: str) -> Tuple[int, int]:
        """HP文字列をパース"""
        # "21/100" or "0 fnt"
        if "fnt" in hp_str:
            return 0, 100
        
        try:
            parts = hp_str.split("/")
            if len(parts) == 2:
                current = int(parts[0])
                max_hp = int(parts[1])
                return current, max_hp
        except ValueError:
            pass
        
        return 100, 100
    
    def _determine_winner(self, log_text: str) -> int:
        """勝者を判定"""
        # |win|Forbranna
        win_match = re.search(r"\|win\|(.+)", log_text)
        if not win_match:
            return 0  # 引き分けor不明
        
        winner_name = win_match.group(1).strip()
        
        # p1 or p2を判定
        player_match = re.search(r"\|player\|p1\|" + re.escape(winner_name), log_text)
        if player_match:
            return 1  # p1勝利
        
        player_match = re.search(r"\|player\|p2\|" + re.escape(winner_name), log_text)
        if player_match:
            return -1  # p2勝利
        
        return 0
    
    def _save_training_example(self, replay_id: str, turn: int, outcome: int):
        """現在のターンを訓練データとして保存"""
        # 盤面状態を構築
        p1_active_list = [
            self.current_state["p1_active"].get(i)
            for i in range(2)
        ]
        p1_active_list = [p for p in p1_active_list if p is not None]
        
        p2_active_list = [
            self.current_state["p2_active"].get(i)
            for i in range(2)
        ]
        p2_active_list = [p for p in p2_active_list if p is not None]
        
        state = BattleStateSnapshot(
            turn=turn,
            p1_active=p1_active_list,
            p2_active=p2_active_list,
            p1_reserves=self.current_state["p1_reserves"],
            p2_reserves=self.current_state["p2_reserves"],
            weather=self.current_state["weather"],
            terrain=self.current_state["terrain"]
        )
        
        # 行動を構築
        action = TurnActionRecord(
            p1_actions=self.turn_actions["p1"],
            p2_actions=self.turn_actions["p2"]
        )
        
        # 訓練データとして保存
        example = TrainingExample(
            replay_id=replay_id,
            turn=turn,
            state=state,
            action=action,
            outcome=outcome
        )
        
        self.training_examples.append(example)


def parse_all_replays(
    replay_files: List[Path],
    output_path: Path,
    min_turn: int = 2,
    max_turn: int = 15
):
    """
    全リプレイを処理
    
    Args:
        replay_files: リプレイJSONファイルのリスト
        output_path: 出力先JSONパス
        min_turn: 訓練データに含める最小ターン
        max_turn: 訓練データに含める最大ターン
    """
    parser = ShowdownLogParser()
    all_examples = []
    
    total_replays = 0
    successful_replays = 0
    
    for replay_file in replay_files:
        print(f"📂 Processing: {replay_file.name}")
        
        try:
            with open(replay_file, "r", encoding="utf-8") as f:
                replays = json.load(f)
            
            for replay in replays:
                total_replays += 1
                
                try:
                    examples = parser.parse_replay(replay)
                    
                    # ターン範囲でフィルタ
                    filtered_examples = [
                        ex for ex in examples
                        if min_turn <= ex.turn <= max_turn
                    ]
                    
                    all_examples.extend(filtered_examples)
                    successful_replays += 1
                    
                except Exception as e:
                    print(f"  ⚠️  Failed to parse replay {replay.get('id', 'unknown')}: {e}")
        
        except Exception as e:
            print(f"  ❌ Failed to load file: {e}")
    
    # JSON形式で保存
    output_data = [
        {
            "replay_id": ex.replay_id,
            "turn": ex.turn,
            "state": {
                "p1_active": [asdict(p) for p in ex.state.p1_active],
                "p2_active": [asdict(p) for p in ex.state.p2_active],
                "weather": ex.state.weather,
                "terrain": ex.state.terrain
            },
            "action": {
                "p1_actions": ex.action.p1_actions,
                "p2_actions": ex.action.p2_actions
            },
            "outcome": ex.outcome
        }
        for ex in all_examples
    ]
    
    # 保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Complete!")
    print(f"   Total replays: {total_replays}")
    print(f"   Successful: {successful_replays}")
    print(f"   Training examples: {len(all_examples)}")
    print(f"   Output: {output_path}")
    
    return all_examples


if __name__ == "__main__":
    import argparse
    
    parser_cli = argparse.ArgumentParser(description="Parse Showdown replays to training data")
    parser_cli.add_argument(
        "--input",
        type=str,
        default="data/replays/*.json",
        help="Input replay files (glob pattern)"
    )
    parser_cli.add_argument(
        "--output",
        type=Path,
        default=Path("data/training/expert_trajectories.json"),
        help="Output training data path"
    )
    parser_cli.add_argument(
        "--min-turn",
        type=int,
        default=2,
        help="Minimum turn to include"
    )
    parser_cli.add_argument(
        "--max-turn",
        type=int,
        default=15,
        help="Maximum turn to include"
    )
    
    args = parser_cli.parse_args()
    
    # リプレイファイルを収集
    import glob
    replay_files = [Path(f) for f in glob.glob(args.input)]
    
    if not replay_files:
        print(f"❌ No replay files found: {args.input}")
        sys.exit(1)
    
    print(f"🚀 Found {len(replay_files)} replay files")
    
    # パース実行
    parse_all_replays(
        replay_files,
        args.output,
        min_turn=args.min_turn,
        max_turn=args.max_turn
    )
