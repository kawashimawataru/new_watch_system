# VGC AI Spectator System

Pokemon Showdown 上で VGC（ダブルバトル）を観戦し、AIによる候補手予測と解説を表示するシステム。

---

## 🚀 クイックスタート

### 1. バックエンド起動

```bash
# 仮想環境を有効化
source .venv/bin/activate

# Pokemon Showdownサーバー起動 (別ターミナル)
cd pokemon-showdown && node pokemon-showdown start

# 観戦エージェント起動
python scripts/run_spectator.py --target PlayerName --battle battle-gen9vgc2024-XXXX
```

### 2. フロントエンド起動

```bash
cd web-ui
npm install  # 初回のみ
npm run dev
```

ブラウザで `http://localhost:3000` を開く

---

## 📁 プロジェクト構造

```
new_watch_game_system/
├── src/                    # Python Backend (DDD構造)
│   ├── application/players/spectator.py  # 観戦エージェント
│   └── infrastructure/messaging/broker.py # WebSocket配信
│
├── predictor/              # AI予測エンジン
│   └── player/hybrid_strategist.py  # Fast/Slow統合戦略
│
├── web-ui/                 # Next.js Frontend
│   ├── app/page.tsx        # メインページ
│   ├── components/         # UIコンポーネント
│   └── hooks/useGameState.ts # WebSocket接続
│
├── scripts/
│   └── run_spectator.py    # 起動スクリプト
│
└── docs/                   # ドキュメント
```

---

## 📺 主な機能

| 機能 | 説明 |
|------|------|
| **勝率予測** | リアルタイムで勝率をバー表示 |
| **候補手表示** | ダブルバトル形式（2匹同時行動）で予測手を表示 |
| **戦術図解** | 攻撃対象・脅威を矢印で可視化 |
| **VFX演出** | Nice Play, Fate Turn, Critical Hit 等 |

---

## 📚 ドキュメント

| ファイル | 内容 |
|---|---|
| [CURRENT_STATUS.md](CURRENT_STATUS.md) | 現在の実装状況 |
| [NEW_ARCHITECTURE_SPEC.md](NEW_ARCHITECTURE_SPEC.md) | アーキテクチャ仕様 |
| [docs/000_OPERATION_MANUAL.md](docs/000_OPERATION_MANUAL.md) | 操作マニュアル |
| [web-ui/README.md](web-ui/README.md) | フロントエンド詳細 |

---

## 🛠️ 技術スタック

### Frontend
- Next.js 16.1.1
- Tailwind CSS v4
- Framer Motion
- Lucide React

### Backend
- Python 3.10+
- FastAPI + Uvicorn
- poke-env (Pokemon Showdown API)
- LightGBM + MCTS

---

## ⚙️ 環境変数

`.env` ファイルに設定:

```bash
OPENAI_API_KEY="your-api-key"  # LLM機能に必要（オプション）
```

---

## 📜 ライセンス

MIT License
