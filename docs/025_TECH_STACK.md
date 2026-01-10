# 技術スタック

**最終更新**: 2024-12-24

## 言語・ランタイム

| 技術 | バージョン | 用途 |
|------|-----------|------|
| Python | 3.13 | バックエンド全般 |
| Node.js | 20+ | Pokemon Showdownサーバー |
| TypeScript | 5.x | React UI（一時停止中）|

## Python依存ライブラリ

| ライブラリ | バージョン | 用途 |
|-----------|-----------|------|
| poke-env | 0.10.0+ | Showdown通信 |
| lightgbm | latest | FastLane勝率予測 |
| numpy | latest | 数値計算 |
| websockets | 15.0.1 | WebSocket通信 |

## インフラ

| 技術 | 用途 |
|------|------|
| Pokemon Showdown (Local) | 対戦サーバー (localhost:8000) |

## ディレクトリ構成 (DDD準拠)

```
new_watch_game_system/
├── src/                     # DDD構造テンプレート (新規コード用)
│   ├── domain/models/       # BattleState等のコピー
│   ├── application/         # Strategist, Playerのコピー
│   └── infrastructure/      # 将来の外部接続用
├── predictor/               # 現行ロジック層 (安定版)
│   ├── core/                # ドメインモデル
│   │   ├── models.py        # BattleState, PlayerState
│   │   └── eval_algorithms/ # 評価アルゴリズム
│   ├── player/              # ユースケース
│   │   ├── hybrid_strategist.py
│   │   └── monte_carlo_strategist.py
│   └── engine/              # シミュレーション
├── frontend/                # プレゼンテーション層
│   └── vgc_ai_player.py     # VGC対戦AI
├── scripts/                 # エントリーポイント
│   ├── run_vgc_ai.py        # VGC AI起動
│   └── archive/             # 未使用スクリプト
├── models/                  # 学習済みモデル
│   └── fast_lane.pkl
└── pokemon-showdown/        # Showdownサーバー
```

## 実行方法

```bash
# 1. Showdownサーバー起動
cd pokemon-showdown && node pokemon-showdown start

# 2. VGC AI起動
python scripts/run_vgc_ai.py --strategy heuristic

# 3. ブラウザで http://localhost:8000 にアクセスしてチャレンジ
```
