# VGC AI System

Pokemon Showdown 上で VGC（ダブルバトル）を行う AI システム。

---

## クイックスタート

```bash
# 1. 仮想環境を有効化
source .venv/bin/activate

# 2. Showdownサーバーを起動（ターミナル1）
cd pokemon-showdown && node pokemon-showdown start

# 3. AI対戦を開始（ターミナル2）
cd /Users/kawashimawataru/Desktop/new_watch_game_system
PYTHONPATH=. python scripts/run_predictor_trial.py
```

---

## ドキュメント

| ファイル | 内容 |
|---|---|
| [CURRENT_STATUS.md](CURRENT_STATUS.md) | 現在の実装状況 |
| [NEW_ARCHITECTURE_SPEC.md](NEW_ARCHITECTURE_SPEC.md) | アーキテクチャ仕様 |
| [docs/OPERATION_MANUAL.md](docs/OPERATION_MANUAL.md) | 操作マニュアル |

---

## 必要な環境変数

```bash
export OPENAI_API_KEY="your-api-key"  # LLM機能に必要
```

---

## 主要機能

### Phase 1: 基盤整備
- ダメージ計算API（ko_prob, expected）
- ターン間状態追跡（BattleMemory）
- 相手行動予測（OpponentModel）
- 評価関数改善（脅威度, プラン遂行度）

### Phase 2: 上位ロジック
- 隠れ情報の確率管理（BeliefState）
- リスク管理（Secure/Gamble モード）
- LLM自己整合（3回投票）
- 戦術テンプレ混合（6種類）

---

## ライセンス

MIT License
