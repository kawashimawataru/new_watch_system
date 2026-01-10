# VGC AI 操作マニュアル

---

## 1. 環境構築

### 1.1 前提条件

- Python 3.10+
- Node.js 18+
- OpenAI API キー（LLM機能に必要）

### 1.2 セットアップ

```bash
# リポジトリに移動
cd /Users/kawashimawataru/Desktop/new_watch_game_system

# 仮想環境を有効化
source .venv/bin/activate

# 依存関係をインストール（初回のみ）
pip install -r requirements.txt

# 環境変数を設定
export OPENAI_API_KEY="your-api-key"
```

---

## 2. 起動方法

### 2.1 Showdown サーバーの起動

```bash
# ターミナル1
cd pokemon-showdown
node pokemon-showdown start
```

起動成功時:
```
POKEMON SHOWDOWN SERVER
http://localhost:8000
```

### 2.2 AI 対戦の開始

```bash
# ターミナル2
cd /Users/kawashimawataru/Desktop/new_watch_game_system
source .venv/bin/activate
PYTHONPATH=. python scripts/run_predictor_trial.py
```

起動成功時:
```
🎮 VGCPredictorPlayer 初期化完了
   └─ TurnAdvisor 有効化済み
   └─ BattleMemory 有効化済み
   └─ BeliefState 有効化済み
   └─ StyleUpdater 有効化済み
   └─ RiskAwareSolver 有効化済み
   └─ TacticalMixer 有効化済み
```

---

## 3. 対戦の流れ

### 3.1 チームプレビュー

AI が自動で以下を実行:
1. **TacticalMixer**: 相手チームから戦術を選択
2. **GamePlanner**: LLM でプランを策定
3. **選出決定**: 4体を選択

### 3.2 毎ターンの処理

| 順序 | 処理 | 内容 |
|---|---|---|
| 1 | BattleMemory | 見えた技/持ち物/特性を記録 |
| 2 | BeliefUpdater | 持ち物/努力値/テラスの確率を更新 |
| 3 | StyleUpdater | 相手のProtect/交代傾向を推定 |
| 4 | RiskMode判定 | Secure/Gamble モードを決定 |
| 5 | TurnAdvisor | LLM で候補を絞り込み |
| 6 | GameSolver | 最適な行動を計算 |

---

## 4. 出力の見方

### 4.1 ターン情報

```
============================================================
📍 ターン 3
============================================================
```

### 4.2 BeliefState（隠れ情報の推定）

```
📊 BeliefState: 4体のポケモンを追跡中
  【miraidon】
    持ち物: choicescarf (40%)
    努力値: CS252 (50%)
    テラス: fairy (30%)
```

### 4.3 StyleUpdater（相手のスタイル）

```
📊 スタイル: 慎重派, サイクル志向 (P:25% S:15% F:30%)
```

### 4.4 RiskMode（リスク管理）

```
🛡️ Secure Mode (勝率65%): リスク回避優先
```
または
```
🎲 Gamble Mode (勝率35%): 上振れ狙い
```

### 4.5 TacticalMixer（戦術選択）

```
🎯 戦術テンプレ選択: TailwindRush
   追い風から高速で押し切る
```

---

## 5. 設定のカスタマイズ

### 5.1 探索設定

`predictor/core/game_solver.py` の `SolverConfig`:

```python
@dataclass
class SolverConfig:
    depth: int = 3          # 探索深さ
    n_samples: int = 12     # サンプル数
    top_k_self: int = 25    # 候補数
    tau: float = 0.25       # 温度パラメータ
```

### 5.2 リスク管理設定

`predictor/core/risk_aware_solver.py` の `RiskAwareConfig`:

```python
@dataclass
class RiskAwareConfig:
    lambda_secure: float = 0.5      # リスク回避係数
    kappa_gamble: float = 0.3       # 上振れ係数
    advantage_threshold: float = 0.55   # Secure 閾値
    disadvantage_threshold: float = 0.45  # Gamble 閾値
```

---

## 6. トラブルシューティング

### 6.1 Showdown サーバーに接続できない

```
❌ Server connection failed
```

**対処法**:
```bash
# ポート確認
lsof -i :8000

# サーバー再起動
cd pokemon-showdown
node pokemon-showdown start
```

### 6.2 LLM エラー

```
⚠️ TurnAdvisor エラー: API key not found
```

**対処法**:
```bash
export OPENAI_API_KEY="your-api-key"
```

### 6.3 行動が選択されない

```
⚠️ 候補が空です
```

**対処法**: ログを確認し、`CandidateGenerator` のデバッグ出力を確認

---

## 7. 開発者向け情報

### 7.1 ファイル構成

```
src/domain/services/
├── belief_state.py       # 隠れ情報管理
├── belief_updater.py     # Belief更新
├── battle_memory.py      # ターン間状態
├── opponent_model.py     # 相手予測
├── player_style.py       # スタイル推定
└── damage_calc_service.py # ダメージ計算

predictor/core/
├── vgc_predictor.py      # メインPredictor
├── game_solver.py        # 探索
├── game_planner.py       # プラン策定
├── turn_advisor.py       # 毎ターンLLM
├── risk_aware_solver.py  # リスク管理
├── consistent_turn_advisor.py # LLM自己整合
├── determinized_solver.py # 複数仮説MCTS
├── tactical_mixer.py     # 戦術テンプレ
└── candidate_generator.py # 候補生成
```

### 7.2 テストコマンド

```bash
# 全モジュールの構文チェック
python -c "
from predictor.core.vgc_predictor import VGCPredictor
from predictor.core.game_solver import GameSolver
from src.domain.services.belief_state import BeliefState
print('All imports OK')
"
```

---

## 8. 参考資料

- PokéChamp: https://arxiv.org/abs/2503.04094
- PokéLLMon: https://arxiv.org/abs/2402.01118
- VGC-Bench: https://arxiv.org/abs/2506.10326
