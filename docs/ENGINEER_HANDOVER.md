# VGC AI Spectator — エンジニア引き継ぎ資料

> **最終更新**: 2026-01-12  
> **対象**: 本プロジェクトに初めて参加するエンジニア  
> **バージョン**: 2.0（環境変数・FAQ・デバッグ方法を追加）

---

## 1. プロジェクト概要

**VGC AI Spectator** は、ポケモンVGC（Video Game Championship）のダブルバトルをリアルタイムで観戦・分析し、AIによる勝率予測と最適手の提案を行うシステムです。

### 主な機能
- 🎥 Pokemon Showdown のバトルをリアルタイム観戦
- 📊 ターンごとの勝率予測（MCTSベース）
- 🎯 最適行動候補の提案（ダブルバトル対応）
- 🌤️ 天候・フィールド・壁などの状態表示
- 💥 ダメージ計算・KO確率の表示

---

## 2. 技術スタック

| レイヤー | 技術 |
|----------|------|
| **バックエンド** | Python 3.10+, FastAPI, WebSocket |
| **フロントエンド** | Next.js 16, React 18, TypeScript, Tailwind CSS |
| **AI/ML** | MCTS, LightGBM, LLM (Gemini) |
| **ポケモンデータ** | poke-env, Pokemon Showdown |
| **通信** | WebSocket (リアルタイム配信) |

---

## 3. ディレクトリ構成

```
new_watch_game_system/
├── src/                          # Python バックエンド
│   ├── domain/                   # ドメイン層 (ビジネスロジック)
│   │   ├── models/               # データモデル
│   │   │   └── complete_battle_mechanics.py  # ★ バトル仕様DB
│   │   └── services/             # ドメインサービス
│   │       ├── battle_state_simulator.py     # ★ バトルシミュレーター
│   │       └── vgc_damage_calculator.py      # ダメージ計算
│   ├── application/              # アプリケーション層
│   │   ├── players/
│   │   │   └── spectator.py      # ★ 観戦エージェント (メイン)
│   │   └── services/
│   │       └── spectator_analyzer.py
│   ├── infrastructure/           # インフラ層
│   │   └── messaging/
│   │       └── broker.py         # WebSocket ブローカー
│   └── interfaces/               # インターフェース層
│       └── api/
│           └── server.py         # ★ FastAPI サーバー
│
├── web-ui/                       # Next.js フロントエンド
│   ├── app/                      # ページ
│   ├── components/               # UIコンポーネント
│   │   ├── VisualReasoningView.tsx    # 戦術図解
│   │   ├── BattleConditionsPanel.tsx  # ★ 天候/フィールド表示
│   │   ├── BroadcastCandidateList.tsx # 候補手リスト
│   │   └── DamagePreviewBadge.tsx     # ★ KO確率バッジ
│   └── hooks/
│       └── useGameState.ts       # WebSocket接続フック
│
├── scripts/                      # 実行スクリプト
│   ├── run_battle_spectator.py   # ★ 観戦起動
│   └── run_spectator.py
│
├── pokemon-showdown/             # Pokemon Showdown サーバー (サブモジュール)
└── docs/                         # ドキュメント
```

---

## 4. セットアップ手順

### 4.1 前提条件
- Python 3.10 以上
- Node.js 18 以上
- npm または yarn

### 4.2 Python 環境構築
```bash
cd /Users/kawashimawataru/Desktop/new_watch_game_system

# 仮想環境作成 (推奨)
python -m venv venv
source venv/bin/activate

# 依存パッケージインストール
# 主要パッケージ:
pip install fastapi uvicorn websockets
pip install poke-env
pip install lightgbm numpy pandas
pip install pytest pytest-asyncio
# その他必要なパッケージは個別にインストールしてください
```

### 4.3 フロントエンド環境構築
```bash
cd web-ui
npm install
```

### 4.4 Pokemon Showdown サーバー (ローカルテスト用)
```bash
cd pokemon-showdown
npm install
node pokemon-showdown start --no-security
```

---

## 5. 起動方法

**3つのターミナル** を開いて、順番に実行します。

### 5.1 起動スクリプトの違い

| スクリプト | 用途 | APIサーバー |
|-----------|------|------------|
| `run_spectator.py` | **推奨** - APIサーバーと観戦エージェントを同時起動 | ✅ 内蔵 |
| `run_battle_spectator.py` | 観戦エージェントのみ（APIサーバーは別途必要） | ❌ 別途起動 |

### 5.2 方法A: 統合起動（推奨）

**`run_spectator.py` を使用** - APIサーバーと観戦エージェントが1つのプロセスで動作します。

#### ターミナル1: Pokemon Showdown サーバー
```bash
cd pokemon-showdown
node pokemon-showdown start --no-security
```

#### ターミナル2: 統合サーバー（API + 観戦エージェント）
```bash
cd /Users/kawashimawataru/Desktop/new_watch_game_system
python scripts/run_spectator.py --target "プレイヤー名" --port 8000
```
→ APIサーバーと観戦エージェントが同時に起動

#### ターミナル3: フロントエンド
```bash
cd /Users/kawashimawataru/Desktop/new_watch_game_system/web-ui
npm run dev
```
→ `http://localhost:3000` でUI表示

### 5.3 方法B: 分離起動

**`run_battle_spectator.py` を使用** - APIサーバーと観戦エージェントを別々に起動します。

#### ターミナル1: バックエンド API
```bash
cd /Users/kawashimawataru/Desktop/new_watch_game_system
python -m src.interfaces.api.server
# または
uvicorn src.interfaces.api.server:app --host 0.0.0.0 --port 8000
```
→ `ws://localhost:8000/ws/spectator` でWebSocket待機

#### ターミナル2: フロントエンド
```bash
cd /Users/kawashimawataru/Desktop/new_watch_game_system/web-ui
npm run dev
```
→ `http://localhost:3000` でUI表示

#### ターミナル3: 観戦エージェント
```bash
cd /Users/kawashimawataru/Desktop/new_watch_game_system
python scripts/run_battle_spectator.py --target "プレイヤー名"
```

#### オプション: 特定バトルIDを指定
```bash
python scripts/run_battle_spectator.py --target "プレイヤー名" --battle "battle-gen9vgc2024-123"
```

---

## 6. データフロー

```
┌─────────────────┐    WebSocket     ┌─────────────────┐
│ Pokemon Showdown │ ──────────────▶ │   Spectator.py  │
│    (対戦サーバ)   │                 │  (観戦エージェント) │
└─────────────────┘                 └────────┬────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │ SpectatorAnalyzer│
                                    │  - シミュレーション │
                                    │  - 勝率計算       │
                                    │  - 候補手生成     │
                                    └────────┬────────┘
                                             │
                                    ┌────────▼────────┐
                                    │  MessageBroker  │
                                    │ (WebSocket配信)  │
                                    └────────┬────────┘
                                             │
                                    ┌────────▼────────┐
                                    │   Next.js UI    │
                                    │  - 勝率グラフ     │
                                    │  - 候補手表示     │
                                    │  - 天候/壁表示    │
                                    └─────────────────┘
```

---

## 7. 主要ファイル解説

### 7.1 バトルメカニクス
**`src/domain/models/complete_battle_mechanics.py`**
- 特性 132個、技 83個、アイテム 68個、状態異常 6種類のデータベース
- Pokemon Showdown のソースコードから抽出した正確な仕様

### 7.2 シミュレーター
**`src/domain/services/battle_state_simulator.py`**
- ダメージ計算、状態異常適用、ターン終了処理
- やけど攻撃0.5倍、おんみつマント、ちからずくなど実装済み

### 7.3 観戦エージェント
**`src/application/players/spectator.py`**
- poke-env を使用して Showdown に接続
- ターンごとに分析結果をWebSocket配信

### 7.4 フロントエンド
| ファイル | 役割 |
|----------|------|
| `useGameState.ts` | WebSocket接続、状態管理 |
| `BattleConditionsPanel.tsx` | 天候/フィールド/壁表示 |
| `DamagePreviewBadge.tsx` | KO確率・状態異常バッジ |
| `VisualReasoningView.tsx` | 戦術図解パネル |

---

## 8. WebSocket メッセージ形式

バックエンドからフロントエンドに送信されるJSON:

```json
{
  "type": "game_update",
  "data": {
    "turn": 5,
    "winRate": 62.5,
    "fieldConditions": {
      "weather": "sun",
      "terrain": "grassy",
      "playerTailwind": true,
      "opponentReflect": true
    },
    "p1": {
      "name": "Player1",
      "activePokemon": [
        {"name": "Incineroar", "hp": 0.85, "status": "burn"}
      ]
    },
    "candidates": {
      "p1": [
        {
          "move1": "ドレインパンチ", "target1": "Flutter Mane",
          "move2": "ねこだまし", "target2": "Urshifu",
          "score": 72,
          "damagePreview1": {"minPercent": 45, "maxPercent": 53, "koChance": 0}
        }
      ]
    }
  }
}
```

---

## 9. 開発ガイドライン

### コーディング規約
- **言語**: コメント・コミットメッセージは日本語
- **コミット形式**: `mmdd_HHMM_message` (例: `0112_1230_add_terrain_support`)
- **アーキテクチャ**: DDD + レイヤードアーキテクチャ

### テスト実行
```bash
# Python テスト
pytest tests/

# フロントエンド型チェック
cd web-ui && npm run build
```

---

## 10. 環境変数設定

システムは環境変数で設定をカスタマイズできます。`.env` ファイルを作成するか、シェルで設定してください。

### 10.1 主要な環境変数

| 変数名 | デフォルト値 | 説明 |
|--------|------------|------|
| `WEBSOCKET_HOST` | `0.0.0.0` | WebSocketサーバーのホスト |
| `WEBSOCKET_PORT` | `8000` | WebSocketサーバーのポート |
| `SPECTATOR_TARGET` | `VGC_AI` | 観戦対象のプレイヤー名 |
| `SPECTATOR_INTERVAL` | `2.0` | バトル検索間隔（秒） |
| `LOG_LEVEL` | `INFO` | ログレベル (DEBUG, INFO, WARNING, ERROR) |
| `DEBUG` | `false` | デバッグモード (true/false) |
| `DATABASE_URL` | `sqlite:///data/battles.db` | データベースURL |
| `OPENAI_API_KEY` | - | LLM解説用のAPIキー（オプション） |
| `LLM_PROVIDER` | `openai` | LLMプロバイダー |
| `LLM_MODEL` | `gpt-4o-mini` | LLMモデル名 |

### 10.2 設定例

```bash
# .env ファイルを作成
cat > .env << EOF
WEBSOCKET_PORT=8000
SPECTATOR_TARGET=MyPlayer
LOG_LEVEL=DEBUG
DEBUG=true
EOF

# 環境変数を読み込んで起動
export $(cat .env | xargs)
python scripts/run_spectator.py --target MyPlayer
```

---

## 11. トラブルシューティング

### 11.1 よくある問題と解決策

| 症状 | 原因 | 解決策 |
|------|------|--------|
| UI に何も表示されない | WebSocket未接続 | バックエンド起動確認、ブラウザコンソールでエラー確認 |
| 候補手が生成されない | 観戦エージェント未起動 | `run_battle_spectator.py` または `run_spectator.py` を起動 |
| ビルドエラー (WinRateChart) | 既存の型エラー | 別issue, 本機能に影響なし |
| `ModuleNotFoundError` | パス設定の問題 | `sys.path.append(project_root)` を確認 |
| Showdown接続エラー | サーバー未起動 | `pokemon-showdown` サーバーを起動 |
| ポート8000が使用中 | 既存プロセス | `lsof -i :8000` で確認し、必要に応じて終了 |

### 11.2 デバッグ方法

#### ログレベルの変更
```bash
# デバッグモードで起動
LOG_LEVEL=DEBUG python scripts/run_spectator.py --target PlayerName

# または環境変数で設定
export LOG_LEVEL=DEBUG
export DEBUG=true
```

#### ログファイルの確認
```bash
# エラーログ
tail -f logs/error.log

# 観戦ログ
tail -f logs/spectator.log
```

#### WebSocket接続の確認
```bash
# ブラウザの開発者ツールで確認
# Console タブで WebSocket エラーを確認
# Network タブで WebSocket 接続状態を確認
```

#### バックエンドの動作確認
```bash
# APIサーバーのヘルスチェック
curl http://localhost:8000/

# WebSocket接続テスト（wscatが必要）
wscat -c ws://localhost:8000/ws/spectator
```

### 11.3 よくある質問（FAQ）

**Q: 観戦エージェントがバトルを見つけられない**  
A: `--target` で指定したプレイヤー名が正確か確認してください。Showdownサーバー上で実際にそのプレイヤーが対戦中である必要があります。

**Q: フロントエンドが更新されない**  
A: Next.jsの開発サーバーは自動リロードされますが、ブラウザのキャッシュをクリアするか、ハードリロード（Cmd+Shift+R / Ctrl+Shift+R）を試してください。

**Q: MCTSの計算が遅い**  
A: `SPECTATOR_INTERVAL` や `mcts_rollouts` の設定を調整してください。デフォルトは500回のロールアウトですが、計算時間と精度のバランスを取る必要があります。

**Q: モデルファイルが見つからない**  
A: `models/fast_lane.pkl` が存在するか確認してください。存在しない場合は、学習スクリプトを実行してモデルを生成する必要があります。

---

## 12. 今後の課題

- [ ] ダメージ計算の精度向上（テラスタル対応）
- [ ] 実戦テストとフィードバック収集
- [ ] LLM解説の品質改善
- [ ] モバイル対応UI

---

## 13. 開発時のデバッグ手順

### 13.1 ステップバイステップデバッグ

1. **バックエンドAPIの確認**
   ```bash
   # ターミナル1: APIサーバー起動
   python -m src.interfaces.api.server
   # → "VGC AI Spectator API starting up..." が表示されればOK
   ```

2. **観戦エージェントの確認**
   ```bash
   # ターミナル2: 観戦エージェント起動
   python scripts/run_battle_spectator.py --target PlayerName
   # → "観戦エージェント起動: ターゲット = PlayerName" が表示されればOK
   ```

3. **フロントエンドの確認**
   ```bash
   # ターミナル3: フロントエンド起動
   cd web-ui && npm run dev
   # → "Ready on http://localhost:3000" が表示されればOK
   ```

4. **WebSocket接続の確認**
   - ブラウザで `http://localhost:3000` を開く
   - 開発者ツール（F12）→ Network → WS タブ
   - `ws://localhost:8000/ws/spectator` が接続されているか確認

### 13.2 コードデバッグ

#### Pythonデバッガー（pdb）の使用
```python
# コード内にブレークポイントを設定
import pdb; pdb.set_trace()

# または ipdb（より高機能）
import ipdb; ipdb.set_trace()
```

#### TypeScript/Reactデバッグ
```typescript
// ブラウザの開発者ツールでデバッグ
console.log('デバッグ情報:', data);

// React DevTools を使用
// Chrome拡張機能: React Developer Tools
```

### 13.3 パフォーマンス分析

```bash
# Pythonプロファイリング
python -m cProfile -o profile.stats scripts/run_spectator.py --target PlayerName
python -m pstats profile.stats

# メモリ使用量の確認
pip install memory_profiler
python -m memory_profiler scripts/run_spectator.py
```

---

## 14. 問い合わせ・参考資料

### 14.1 重要なドキュメント

| ファイル | 内容 |
|---------|------|
| `NEW_ARCHITECTURE_SPEC.md` | アーキテクチャ詳細仕様 |
| `CURRENT_STATUS.md` | 現在の実装状況 |
| `ForAgentRead.md` | エージェント向けガイド |
| `docs/ENGINEER_HANDOVER_CHECK_REPORT.md` | 引き継ぎ資料の検証レポート |

### 14.2 外部リソース

- **Pokemon Showdown**: https://pokemonshowdown.com/
- **poke-env ドキュメント**: https://poke-env.readthedocs.io/
- **FastAPI ドキュメント**: https://fastapi.tiangolo.com/
- **Next.js ドキュメント**: https://nextjs.org/docs

### 14.3 コミュニティ・サポート

不明点があれば、以下の順序で確認してください:
1. 本ドキュメントの該当セクション
2. `docs/` ディレクトリ内の関連ドキュメント
3. コード内のコメントとdocstring
4. プロジェクトのGitHubリポジトリ（イシュー検索）

---

**Happy Coding! 🎮**
