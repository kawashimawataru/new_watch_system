"""
@smogon/calc Python Wrapper

Python から Node.js の @smogon/calc を呼び出すためのラッパー。
サブプロセス経由でJSON通信を行う。
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from predictor.core.ev_estimator import SpreadHypothesis

# calc_server.js のパス
CALC_SERVER_PATH = Path(__file__).resolve().parents[2] / "smogon-calc-bridge" / "calc_server.js"


@dataclass
class SmogonDamageResult:
    """@smogon/calc の計算結果"""
    
    damage: List[int]  # ダメージの配列 (乱数16通り)
    damage_range: List[int]  # [min, max]
    description: str  # 人間可読な説明文
    kochance: Dict[str, float]  # {"chance": 0.0, "n": 2} など
    min_percent: float  # 最小ダメージ%
    max_percent: float  # 最大ダメージ%
    defender_max_hp: int  # 防御側の最大HP
    success: bool = True
    error: Optional[str] = None


class SmogonCalcWrapper:
    """
    @smogon/calc を Python から使うためのラッパー。
    
    使用例:
    ```python
    calc = SmogonCalcWrapper()
    
    attacker = SpreadHypothesis(
        nature="Modest",
        evs={"hp": 4, "spa": 252, "spe": 252},
        species="Gholdengo"
    )
    defender = SpreadHypothesis(
        nature="Jolly", 
        evs={"hp": 4, "atk": 252, "spe": 252},
        species="Dragonite"
    )
    
    result = calc.calculate_damage(
        attacker_name="Gholdengo",
        attacker_spread=attacker,
        defender_name="Dragonite",
        defender_spread=defender,
        move_name="Make It Rain",
        attacker_item="Choice Specs",
        defender_item="Choice Band"
    )
    
    print(f"ダメージ: {result.damage_range[0]}-{result.damage_range[1]}")
    print(f"説明: {result.description}")
    ```
    """
    
    def __init__(self):
        """
        @smogon/calc ブリッジサーバーを起動。
        """
        if not CALC_SERVER_PATH.exists():
            raise FileNotFoundError(
                f"Smogon calc server not found at {CALC_SERVER_PATH}. "
                "Run 'cd smogon-calc-bridge && npm install' first."
            )
        
        # Node.jsプロセスを起動 (stdin/stdoutで通信)
        self.process = subprocess.Popen(
            ["node", str(CALC_SERVER_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # 起動確認 (短時間待機)
        import time
        time.sleep(0.3)  # Node.jsの起動待ち
    
    def calculate_damage(
        self,
        attacker_name: str,
        attacker_spread: SpreadHypothesis,
        defender_name: str,
        defender_spread: SpreadHypothesis,
        move_name: str,
        attacker_item: Optional[str] = None,
        defender_item: Optional[str] = None,
        attacker_ability: Optional[str] = None,
        defender_ability: Optional[str] = None,
        field: Optional[Dict] = None,
        attacker_level: int = 50,
        defender_level: int = 50,
    ) -> SmogonDamageResult:
        """
        @smogon/calc でダメージ計算を実行。
        
        Args:
            attacker_name: 攻撃側のポケモン名
            attacker_spread: 攻撃側のEV配分
            defender_name: 防御側のポケモン名
            defender_spread: 防御側のEV配分
            move_name: 技名
            attacker_item: 攻撃側の持ち物
            defender_item: 防御側の持ち物
            attacker_ability: 攻撃側の特性
            defender_ability: 防御側の特性
            field: 場の状態 (天候、フィールドなど)
            attacker_level: 攻撃側のレベル
            defender_level: 防御側のレベル
            
        Returns:
            SmogonDamageResult: 計算結果
        """
        request = {
            "attacker": {
                "name": attacker_name,
                "nature": attacker_spread.nature,
                "evs": attacker_spread.evs,
                "ivs": getattr(attacker_spread, 'ivs', {}) or {},
                "item": attacker_item,
                "ability": attacker_ability,
                "level": attacker_level,
                "teraType": None
            },
            "defender": {
                "name": defender_name,
                "nature": defender_spread.nature,
                "evs": defender_spread.evs,
                "ivs": getattr(defender_spread, 'ivs', {}) or {},
                "item": defender_item,
                "ability": defender_ability,
                "level": defender_level,
                "teraType": None
            },
            "move": move_name,
            "field": field or {}
        }
        
        # JSONをNode.jsプロセスに送信
        request_json = json.dumps(request)
        self.process.stdin.write(request_json + "\n")
        self.process.stdin.flush()
        
        # 結果を受信
        response_line = self.process.stdout.readline()
        response = json.loads(response_line)
        
        if not response.get("success"):
            return SmogonDamageResult(
                damage=[],
                damage_range=[0, 0],
                description="",
                kochance={},
                min_percent=0.0,
                max_percent=0.0,
                defender_max_hp=0,
                success=False,
                error=response.get("error", "Unknown error")
            )
        
        return SmogonDamageResult(
            damage=response["damage"],
            damage_range=response["damageRange"],
            description=response["description"],
            kochance=response["kochance"],
            min_percent=response["minPercent"],
            max_percent=response["maxPercent"],
            defender_max_hp=response["defender"]["maxHP"]
        )
    
    def close(self):
        """Node.jsプロセスを終了。"""
        if self.process:
            self.process.terminate()
            self.process.wait()
    
    def __del__(self):
        """デストラクタでプロセスを確実に終了。"""
        self.close()
    
    def __enter__(self):
        """Context manager サポート。"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager サポート。"""
        self.close()


if __name__ == "__main__":
    """
    使用例とテスト
    """
    print("=" * 70)
    print("🧪 @smogon/calc Wrapper テスト")
    print("=" * 70)
    
    # テスト用の型定義
    gholdengo_modest = SpreadHypothesis(
        label="test",
        nature="Modest",
        evs={"hp": 4, "atk": 0, "def": 0, "spa": 252, "spd": 0, "spe": 252},
        ivs={},
        probability=1.0,
        species="Gholdengo"
    )
    
    dragonite_jolly = SpreadHypothesis(
        label="test",
        nature="Jolly",
        evs={"hp": 4, "atk": 252, "def": 0, "spa": 0, "spd": 0, "spe": 252},
        ivs={},
        probability=1.0,
        species="Dragonite"
    )
    
    print("\n攻撃側: Gholdengo (Modest H4 C252 S252)")
    print("防御側: Dragonite (Jolly H4 A252 S252)")
    print("技: Make It Rain")
    print()
    
    with SmogonCalcWrapper() as calc:
        result = calc.calculate_damage(
            attacker_name="Gholdengo",
            attacker_spread=gholdengo_modest,
            defender_name="Dragonite",
            defender_spread=dragonite_jolly,
            move_name="Make It Rain",
            attacker_item="Choice Specs",
            defender_item=None,
            attacker_ability="Good as Gold",
            defender_ability="Multiscale"
        )
        
        if result.success:
            print("✅ 計算成功!")
            print(f"\n📊 結果:")
            print(f"  ダメージ範囲: {result.damage_range[0]} - {result.damage_range[1]}")
            print(f"  ダメージ%: {result.min_percent:.1f}% - {result.max_percent:.1f}%")
            print(f"  防御側HP: {result.defender_max_hp}")
            print(f"\n📝 詳細:")
            print(f"  {result.description}")
        else:
            print(f"❌ エラー: {result.error}")
    
    print()
    print("=" * 70)
    print("✅ テスト完了")
    print("=" * 70)
