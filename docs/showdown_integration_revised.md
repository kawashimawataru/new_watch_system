# Pokemon Showdown 統合プラン（改訂版）

## 現状分析と方針転換

### 試したこと

1. ✅ Pokemon Showdown サーバーをローカルに立ち上げ（成功）
2. ✅ `poke-env` ライブラリのインストール（成功）
3. ❌ `poke-env` とローカルサーバーの接続（HTTP 403 エラー）

### 問題点

- ローカル Showdown サーバーはデフォルトで公式ログインサーバーへの認証を要求
- `poke-env` の設定が複雑で、ローカル開発には不向き
- AI 開発のために WebSocket 通信は本質的ではない

## 推奨アプローチ: Showdown シミュレータの直接利用

### 方針

Pokemon Showdown の**バトルシミュレータ部分のみ**を直接利用する。

- `pokemon-showdown/sim/` ディレクトリの JavaScript コードを使用
- Node.js から直接呼び出すか、Python から subprocess で実行
- サーバー通信は不要

### メリット

1. **正確性**: Showdown の実装そのものを使うため計算誤りゼロ
2. **シンプル**: WebSocket/認証の複雑さを回避
3. **高速**: ネットワーク通信のオーバーヘッドなし
4. **オフライン**: インターネット接続不要

## 実装方法

### オプション A: Node.js スクリプト経由（推奨）

#### 1. Showdown シミュレータラッパーの作成

`pokemon-showdown/damage_calc.js`:

```javascript
// Showdownのバトルシミュレータを直接使用するスクリプト
const Sim = require('./dist/sim');

function calculateDamage(attackerData, defenderData, moveName, context) {
  // Showdownのダメージ計算ロジックを呼び出し
  const battle = new Sim.Battle();

  // チームを設定
  const p1 = battle.join('p1', 'Player 1', 1, [attackerData]);
  const p2 = battle.join('p2', 'Player 2', 1, [defenderData]);

  // ダメージを計算
  // ...

  return {
    damageRange: [minDamage, maxDamage],
    koChance: koChance,
  };
}

// コマンドライン引数から受け取る
if (require.main === module) {
  const input = JSON.parse(process.argv[2]);
  const result = calculateDamage(input.attacker, input.defender, input.move, input.context);
  console.log(JSON.stringify(result));
}

module.exports = { calculateDamage };
```

#### 2. Python から呼び出し

`predictor/engine/showdown_calculator.py`:

```python
import json
import subprocess
from pathlib import Path

SHOWDOWN_DIR = Path(__file__).parents[2] / "pokemon-showdown"
CALC_SCRIPT = SHOWDOWN_DIR / "damage_calc.js"

def calculate_damage_with_showdown(attacker, defender, move, context=None):
    """Showdownのシミュレータで正確なダメージを計算"""

    payload = json.dumps({
        "attacker": attacker,
        "defender": defender,
        "move": move,
        "context": context or {}
    })

    result = subprocess.run(
        ["node", str(CALC_SCRIPT), payload],
        capture_output=True,
        text=True,
        check=True
    )

    return json.loads(result.stdout)
```

### オプション B: WebAssembly 移植（高度）

Showdown のコアロジックを Rust/Go で再実装し、WASM にコンパイルして Python から呼び出す。
→ 工数大、後回し推奨

### オプション C: データ駆動アプローチ

完全なシミュレータを組み込む代わりに、Showdown のデータ（技・特性・道具の効果）だけを利用し、
計算ロジックは慎重に実装し直す。

- `data/showdown/*.json` を活用（既に取得済み）
- 既存の `damage_calculator.py` を改良
- Showdown のソースコードを参照しながら実装
- テストケースを Showdown と照合

## 次のステップ

### フェーズ 1: Node.js ラッパーの実装（Week 1-2）

1. `pokemon-showdown/damage_calc.js` を作成

   - Showdown の `Sim.Battle` を使用
   - ダメージ計算のみに特化

2. Python から呼び出すインターフェースを実装

   - `predictor/engine/showdown_calculator.py`
   - subprocess 経由で JSON をやり取り

3. テストケースで検証
   - 既存の `test_damage_calculator.py` と比較
   - 誤差を分析してレポート

### フェーズ 2: 既存システムへの統合（Week 3）

1. `DamageCalculator` クラスに切り替えフラグを追加

   ```python
   def estimate_percent(self, ..., use_showdown=True):
       if use_showdown:
           return self._calculate_with_showdown(...)
       else:
           return self._calculate_legacy(...)
   ```

2. `evaluate_position` に伝播

   ```python
   def evaluate_position(..., use_showdown_calculator=True):
       calculator = DamageCalculator(use_showdown=use_showdown_calculator)
       ...
   ```

3. パフォーマンス測定
   - subprocess のオーバーヘッドを確認
   - 必要なら Node.js プロセスを常駐させる

### フェーズ 3: 完全なバトルシミュレーション（Week 4 以降）

ダメージ計算だけでなく、ターン進行全体をシミュレート:

1. `pokemon-showdown/battle_simulator.js` を作成

   - 初期状態から n 手先までシミュレート
   - MCTS のロールアウトで使用

2. MCTS 評価器の実装
   ```python
   class MCTSEvaluator:
       def rollout(self, state, depth=5):
           # Showdownシミュレータで実際に対戦を進める
           result = subprocess.run([
               "node",
               "pokemon-showdown/battle_simulator.js",
               json.dumps(state)
           ])
           return json.loads(result.stdout)
   ```

## 代替案: Damage Calc の改良（データ駆動）

もし Node.js との連携が難しい場合、既存の `damage_calculator.py` を改良:

### 改良ポイント

1. **Showdown ソースコードを参照**

   - `pokemon-showdown/sim/battle.ts`
   - `pokemon-showdown/sim/dex-moves.ts`
   - ロジックを正確に移植

2. **不足している特性・道具効果を追加**

   - `ABILITY_ATTACK_BOOSTS` に追加
   - `DEFENSIVE_ABILITIES` に追加
   - 特性の相互作用（いかく → まけんき など）

3. **テストケースの充実**

   - Showdown のダメージ計算結果と照合
   - Smogon の Damage Calculator と比較
   - 誤差を 1%以下に抑える

4. **複雑な相互作用の実装**
   - フィールド効果（エレキフィールド → 地面無効）
   - 連続技のダメージ減衰
   - ランダム性の正確な再現

## プロジェクト構造（更新版）

```
new_watch_game_system/
├── pokemon-showdown/              # Showdown本体
│   ├── damage_calc.js             # NEW: ダメージ計算ラッパー
│   ├── battle_simulator.js        # NEW: バトルシミュレータラッパー
│   └── dist/sim/                  # コンパイル済みシミュレータ
├── predictor/
│   ├── engine/
│   │   ├── damage_calculator.py          # 既存（レガシー）
│   │   ├── showdown_calculator.py        # NEW: Showdown呼び出し
│   │   └── showdown_battle_simulator.py  # スタブのまま
│   └── core/
│       └── eval_algorithms/
│           └── mcts_eval.py       # Showdownシミュレータを使用
├── tests/
│   ├── test_damage_calculator.py
│   └── test_showdown_calculator.py  # NEW
└── docs/
    └── showdown_integration_revised.md  # このファイル
```

## まとめ

### 現時点での推奨アクション

1. ✅ **Pokemon Showdown は既にセットアップ済み**

   - `pokemon-showdown/` ディレクトリに配置

2. **次にやること（優先順）:**

   **A. 短期（今週）: Node.js ラッパーの作成**

   - `pokemon-showdown/damage_calc.js` を実装
   - Python から subprocess で呼び出し
   - テストで精度検証

   **B. 中期（来週）: ダメージ計算の統合**

   - `DamageCalculator` に Showdown オプションを追加
   - 既存コードとの互換性を保ちながら切り替え

   **C. 長期（2 週間後〜）: MCTS のロールアウト実装**

   - バトル全体のシミュレーション
   - ツリー探索での利用

3. **バックアッププラン:**
   - Node.js 連携が難しければ、データ駆動で `damage_calculator.py` を改良
   - Showdown のソースコードを参照して正確性を向上

## 参考リンク

- Showdown Simulator API: `pokemon-showdown/sim/README.md`
- Smogon Damage Calculator: https://calc.pokemonshowdown.com/
- Damage Calculation Formula: https://bulbapedia.bulbagarden.net/wiki/Damage
