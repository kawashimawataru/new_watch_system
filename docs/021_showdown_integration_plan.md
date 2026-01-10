# Pokemon Showdown 統合プラン

## 概要

現在の独自実装のダメージ計算・状態管理から、Pokemon Showdown の公式バトルシミュレータを組み込むことで、計算精度を大幅に向上させます。

## 現状の課題

- `predictor/engine/damage_calculator.py`: 独自実装のダメージ計算に誤りの可能性
- `predictor/engine/state_rebuilder.py`: バトル状態の管理が不完全
- タイプ相性、特性、道具、天候などの複雑な相互作用を完全に再現するのは困難

## 統合方針

### フェーズ 1: Showdown サーバーのセットアップ（完了）

```bash
# プロジェクト内にクローン済み
cd pokemon-showdown
npm install
npm run build
node pokemon-showdown start  # ポート8000で起動
```

接続確認: http://play.pokemonshowdown.com/~~localhost:8000

### フェーズ 2: Python ↔ Showdown 連携レイヤーの構築

#### 2.1 `poke-env` の導入

`poke-env` は Python から Showdown サーバーと通信するための公式ライブラリです。

```bash
pip install poke-env
```

#### 2.2 新しいアダプターの実装

`predictor/engine/showdown_battle_simulator.py` を新規作成:

```python
from poke_env.player import Player
from poke_env.environment.battle import Battle

class ShowdownBattleSimulator:
    """
    Pokemon Showdownの実際のバトルエンジンを使って
    ダメージ計算や行動結果をシミュレートする
    """

    async def simulate_action(self, battle_state, action):
        """
        特定の行動を実行して結果を取得
        """
        pass

    async def calculate_damage(self, attacker, defender, move, context):
        """
        Showdownエンジンで正確なダメージを計算
        """
        pass
```

### フェーズ 3: 既存コードの段階的置き換え

#### 置き換え対象の優先順位

1. **ダメージ計算** (`damage_calculator.py`)

   - 独自実装 → Showdown エンジン呼び出しに変更
   - テストケースで比較検証

2. **状態管理** (`state_rebuilder.py`)

   - Showdown のバトルログフォーマットに統一
   - `poke-env.Battle` オブジェクトを直接利用

3. **行動生成** (`action_annotator.py`)
   - Showdown の合法手判定を使用

#### 互換性の維持

既存の `evaluate_position` インターフェースは変更せず、内部実装のみ切り替え:

```python
def evaluate_position(
    team_a_pokepaste: str,
    team_b_pokepaste: str,
    battle_log: Dict[str, Any],
    estimated_evs: Optional[Dict[str, Dict[str, Dict[str, int]]]] = None,
    algorithm: str = "heuristic",
    use_showdown: bool = True,  # ← 新フラグで切り替え
) -> Dict[str, Any]:
    if use_showdown:
        return _evaluate_with_showdown(...)
    else:
        return _evaluate_legacy(...)
```

### フェーズ 4: AI アルゴリズムの強化

Showdown 統合により可能になること:

#### 4.1 正確なシミュレーションベース MCTS

```python
class MCTSEvaluator:
    def evaluate(self, battle_state):
        # Showdownエンジンで実際に100手先まで展開
        for _ in range(self.rollout_count):
            result = await self.simulator.rollout(battle_state, depth=10)
            self.update_q_values(result)
```

#### 4.2 強化学習用のデータ収集

- Showdown でセルフプレイを実行
- 正確な状態遷移データを大量生成
- `eval_algorithms/ml_eval.py` の学習データとして使用

### フェーズ 5: デプロイメント構成

#### 開発環境

```
new_watch_game_system/
├── pokemon-showdown/          # ローカルShowdownサーバー
├── predictor/                 # AI評価システム
│   └── engine/
│       └── showdown_battle_simulator.py  # 新
└── frontend/                  # React UI
```

#### 本番環境の選択肢

1. **Showdown 組み込み型**: Python バックエンドに Node.js プロセスを同梱
2. **マイクロサービス型**: Showdown サーバーと Python API を分離
3. **オフライン型**: Showdown のコアロジックを Python 移植（高難度）

## マイルストーン

### Week 1: 基盤構築

- [x] Showdown サーバーのセットアップ
- [ ] `poke-env` 導入とサンプルバトル実行
- [ ] `showdown_battle_simulator.py` の骨格実装

### Week 2: ダメージ計算の移行

- [ ] 既存テストケースを Showdown 版で再実行
- [ ] 精度比較レポート作成
- [ ] `DamageCalculator` の内部を Showdown 呼び出しに変更

### Week 3: 状態管理の統一

- [ ] Showdown バトルログパーサー実装
- [ ] `StateRebuilder` を Showdown 形式に対応
- [ ] 既存の `battle_log.json` との互換性確保

### Week 4: AI 統合とテスト

- [ ] MCTS 評価器を Showdown シミュレータで実装
- [ ] エンドツーエンドテスト
- [ ] パフォーマンス測定と最適化

## 技術的な留意点

### 非同期処理

`poke-env` は async/await を使用するため、既存の同期的なコードベースと統合する際に注意が必要:

```python
import asyncio

def evaluate_position_sync(...):
    """既存の同期インターフェース"""
    return asyncio.run(_evaluate_position_async(...))

async def _evaluate_position_async(...):
    """内部は非同期で実装"""
    simulator = ShowdownBattleSimulator()
    result = await simulator.simulate(...)
    return result
```

### Showdown バージョン管理

- Showdown は頻繁に更新されるため、特定のコミットをピン留め
- `pokemon-showdown/.git` でバージョン管理
- 更新時は回帰テストを実行

### パフォーマンス

- Showdown プロセスの起動コストが大きい
- 評価時は既存プロセスを再利用（接続プール）
- 並列バトルシミュレーション対応

## 参考リンク

- Pokemon Showdown: https://github.com/smogon/pokemon-showdown
- poke-env: https://github.com/hsahovic/poke-env
- Showdown Battle Protocol: https://github.com/smogon/pokemon-showdown/blob/master/sim/SIM-PROTOCOL.md

## 次のステップ

1. `poke-env` をインストールして簡単なバトルを実行
2. `test_showdown_integration.py` を作成して基本動作を確認
3. 既存の `test_damage_calculator.py` を Showdown 版で再実装

```bash
# 次のコマンドを実行
pip install poke-env
python -m pytest tests/test_showdown_integration.py -v
```
