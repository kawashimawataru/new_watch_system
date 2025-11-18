# 立ち上げガイド

ローカル環境でバックエンド（CLI / FastAPI API）と React デモ UI を動かすためのコマンドをまとめています。以下の手順はリポジトリルート（`new_watch_game_system/`）で実行する前提です。

## 1. Python バックエンド

### 1.1 前提ツール

- Python 3.11 以降
- pip（Python に同梱）

任意で仮想環境を用意します。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

P1 バックエンド自体は標準ライブラリのみで動作します。HTTP API を使う場合だけ FastAPI と Uvicorn をインストールしてください。

```bash
pip install fastapi uvicorn
```

### 1.2 CLI（テキスト入力）

`evaluate_position` を直接叩く最小構成です。テスト用の固定データを読み込むスモークテストは次の通りです。

```bash
python -m frontend.input_cli --sample-data
```

自前のデータを使う場合は Pokepaste / バトルログ JSON / 推定 EV JSON のパスを渡します。アルゴリズムは `heuristic` / `mcts` / `ml` を `--algorithm` で切り替えられます（現状は heuristic のみ実装済み）。

```bash
python -m frontend.input_cli \
  --team-a path/to/team_a.paste \
  --team-b path/to/team_b.paste \
  --battle-log path/to/battle_log.json \
  --evs path/to/estimated_evs.json \
  --algorithm heuristic
```

パスを省略すると、標準入力で複数行入力（`.` 単独行で終了）できます。

### 1.3 FastAPI サーバー（HTTP エンドポイント）

FastAPI / Uvicorn を入れた後、以下でローカル HTTP サーバーを起動できます。

```bash
uvicorn predictor.api.server:app --reload --port 8000
```

`POST /evaluate-position` に CLI と同じペイロードを投げれば JSON 応答が返ります。CORS はデフォルトで全オリジン許可になっているため、`http://localhost:5173` からの `fetch` もそのまま通ります。簡易確認用の `curl` 例:

```bash
curl -X POST http://localhost:8000/evaluate-position \
  -H "Content-Type: application/json" \
  -d @payload.json
```

※ `payload.json` の中身は `frontend/web/public/sample-data.json` を参考に作成すると手早く試せます。

### 1.4 Showdown データ同期

- Pokédex / 技 / 道具 / タイプ相性のマスターデータは Showdown 本家の JS を `scripts/fetch_showdown_data.py` で取得し、`data/showdown/*.json` に変換しています。
- 差分チェックは `python scripts/verify_showdown_data.py` で可能です。差異が出た場合は `python scripts/fetch_showdown_data.py` を再度実行してください。

## 2. React + Vite デモ UI

### 2.1 セットアップ & 開発サーバー

前提ツール:

- Node.js 20 以降
- npm 10 以降

```bash
cd frontend/web
npm install
npm run dev
```

Vite のデフォルトポート（5173）で UI が立ち上がるため、ブラウザで `http://localhost:5173` を開きます。バックエンド API が `http://localhost:8000/evaluate-position` で動いていれば、そのままフォームからリクエスト可能です。

### 2.2 API エンドポイント切り替え

- 画面上部「API Endpoint」入力欄を直接編集する
- もしくは `frontend/web/.env` に `VITE_PREDICTOR_URL=https://example.com/evaluate-position` を定義した上で `npm run dev`

どちらでも即時に `fetch` 先を変更できます。

### 2.3 サンプルデータ

`Load Sample` ボタンで `frontend/web/public/sample-data.json` が読み込まれ、Pokepaste・バトルログ・推定 EV がすべて入力されます。バックエンドが起動していなくても UI の挙動を確認できます。

### 2.4 ポケモン立ち絵（Showdown Sprites）

- UI では `https://play.pokemonshowdown.com/sprites/gen5/*.png` の静止画を使用し、アニメーションは無効化しています。
- 立ち絵のスプライト ID は `frontend/web/src/assets/pokemon-sprites.ts` にまとめてあり、`python scripts/export_sprite_map.py` で `data/showdown/pokedex.json` から自動生成できます。
- Pokédex データを更新した際はスクリプトを再実行し、フロントのマッピングを再生成してください。

## 3. Pokemon Showdown サーバー（バトルシミュレータ）

### 3.1 セットアップ

Pokemon Showdown の公式バトルエンジンをプロジェクト内で動作させます。初回のみ以下を実行してください。

```bash
cd pokemon-showdown
npm install
npm run build
```

### 3.2 サーバー起動

```bash
cd pokemon-showdown
node pokemon-showdown start
```

デフォルトではポート 8000 で起動します。ブラウザで以下にアクセスして動作確認できます:

```
http://play.pokemonshowdown.com/~~localhost:8000
```

※ これは公式クライアントの画面を使いつつ、通信先だけローカルサーバーに向ける特殊な URL です。

### 3.3 Python からの利用

AI の評価システムから Showdown のバトルエンジンを利用する場合、`poke-env` ライブラリをインストールします。

```bash
pip install poke-env
```

詳しい統合プランは `docs/showdown_integration_plan.md` を参照してください。

## 4. 推奨ワークフロー（ローカルデモ）

1. Pokemon Showdown サーバーを起動する（別ターミナル）。

   ```bash
   cd pokemon-showdown && node pokemon-showdown start
   ```

2. Python 仮想環境を有効化し、必要なパッケージをインストールする。

   ```bash
   source .venv/bin/activate
   pip install fastapi uvicorn poke-env
   ```

3. `uvicorn predictor.api.server:app --reload --port 8001` で HTTP API を起動する（ポート 8000 は Showdown が使用）。

   ```bash
   uvicorn predictor.api.server:app --reload --port 8001
   ```

4. 別ターミナルで `cd frontend/web && npm run dev` を実行し、UI から API を叩く。

   ```bash
   cd frontend/web
   npm run dev
   ```

5. 追加で `python -m frontend.input_cli --sample-data` を走らせて回帰確認を行う。
   ```bash
   python -m frontend.input_cli --sample-data
   ```

これで **Showdown バトルエンジン**・**Python API**・**React UI** のすべてをローカルで再現できます。
