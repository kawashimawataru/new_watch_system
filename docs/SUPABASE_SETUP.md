# Supabase接続ガイド

## 概要

観戦AIのバトル履歴をSupabaseに保存するための設定手順です。

## 前提条件

- Supabaseアカウントとプロジェクト
- SupabaseプロジェクトのURLとAPI Key

## セットアップ手順

### 1. Supabaseプロジェクトの作成

1. [Supabase](https://supabase.com/)にアクセス
2. 新しいプロジェクトを作成
3. プロジェクトのURLとAPI Keyを取得

### 2. 環境変数の設定

`.env`ファイルまたは環境変数に以下を設定：

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key-here
```

### 3. Supabaseテーブルの作成

SupabaseのSQL Editorで以下のテーブルを作成：

```sql
-- バトル履歴テーブル
CREATE TABLE battle_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    battle_id TEXT NOT NULL UNIQUE,
    battle_tag TEXT NOT NULL,
    player_name TEXT NOT NULL,
    opponent_name TEXT NOT NULL,
    format TEXT,
    battle_type TEXT CHECK (battle_type IN ('single', 'double')),
    player_team JSONB DEFAULT '[]'::jsonb,
    opponent_team JSONB DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    status TEXT CHECK (status IN ('in_progress', 'completed', 'cancelled')),
    winner TEXT CHECK (winner IN ('player', 'opponent')),
    total_turns INTEGER DEFAULT 0,
    final_win_rate FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ターン分析テーブル
CREATE TABLE turn_analysis (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    battle_id TEXT NOT NULL REFERENCES battle_history(battle_id) ON DELETE CASCADE,
    turn INTEGER NOT NULL,
    win_rate FLOAT NOT NULL,
    board_score FLOAT,
    candidates JSONB DEFAULT '[]'::jsonb,
    explanation JSONB DEFAULT '{}'::jsonb,
    field_conditions JSONB DEFAULT '{}'::jsonb,
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(battle_id, turn)
);

-- インデックスの作成
CREATE INDEX idx_battle_history_player_name ON battle_history(player_name);
CREATE INDEX idx_battle_history_started_at ON battle_history(started_at DESC);
CREATE INDEX idx_turn_analysis_battle_id ON turn_analysis(battle_id);
CREATE INDEX idx_turn_analysis_turn ON turn_analysis(battle_id, turn);
```

### 4. Pythonパッケージのインストール

```bash
pip install supabase
```

### 5. コードの有効化

`src/infrastructure/persistence/supabase_client.py`のTODOコメント部分を実装：

```python
from supabase import create_client, Client

# __init__内で
self._client: Client = create_client(self.url, self.key)

# insert_battle_history内で
result = self._client.table("battle_history").insert(battle_data).execute()
return result.data[0]["id"] if result.data else None

# get_battle_history内で
query = self._client.table("battle_history").select("*")
if player_name:
    query = query.eq("player_name", player_name)
query = query.order("started_at", desc=True).limit(limit).offset(offset)
result = query.execute()
return result.data or []

# update_battle_history内で
result = self._client.table("battle_history").update(updates).eq("battle_id", battle_id).execute()
return len(result.data) > 0
```

### 6. 動作確認

観戦AIを起動して、バトルが開始・終了した際にSupabaseにデータが保存されることを確認：

```bash
python scripts/run_spectator.py --target VGC_AI
```

SupabaseのTable Editorで`battle_history`テーブルにデータが追加されていることを確認してください。

## データ構造

### battle_history テーブル

| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID | プライマリキー |
| battle_id | TEXT | バトルID（Showdown形式） |
| battle_tag | TEXT | バトルタグ |
| player_name | TEXT | 観戦対象プレイヤー名 |
| opponent_name | TEXT | 相手プレイヤー名 |
| format | TEXT | バトルフォーマット |
| battle_type | TEXT | "single" or "double" |
| player_team | JSONB | プレイヤーのチーム |
| opponent_team | JSONB | 相手のチーム |
| started_at | TIMESTAMPTZ | 開始時刻 |
| ended_at | TIMESTAMPTZ | 終了時刻 |
| status | TEXT | ステータス |
| winner | TEXT | 勝者 |
| total_turns | INTEGER | 総ターン数 |
| final_win_rate | FLOAT | 最終勝率 |

### turn_analysis テーブル

| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID | プライマリキー |
| battle_id | TEXT | バトルID（外部キー） |
| turn | INTEGER | ターン数 |
| win_rate | FLOAT | 勝率 |
| board_score | FLOAT | 盤面スコア |
| candidates | JSONB | 候補手リスト |
| explanation | JSONB | AI解説 |
| field_conditions | JSONB | フィールド状態 |

## トラブルシューティング

### Supabaseに接続できない

- 環境変数`SUPABASE_URL`と`SUPABASE_KEY`が正しく設定されているか確認
- Supabaseプロジェクトがアクティブか確認
- ネットワーク接続を確認

### データが保存されない

- Supabaseのログを確認
- テーブルが正しく作成されているか確認
- RLS（Row Level Security）が有効になっている場合は、ポリシーを設定

### エラーログの確認

```bash
# ログファイルを確認
tail -f logs/spectator.log | grep -i supabase
```

## 次のステップ

- バトル履歴の可視化（ダッシュボード）
- 統計分析（勝率推移、よく使われるポケモンなど）
- バトルリプレイ機能
