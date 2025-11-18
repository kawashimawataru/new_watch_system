"""
Showdown ローカルサーバーとの接続設定を調整するスクリプト。

ローカルサーバーで認証なしで接続できるように config.js を修正します。
"""

import re
from pathlib import Path

SHOWDOWN_DIR = Path(__file__).parent.parent / "pokemon-showdown"
CONFIG_FILE = SHOWDOWN_DIR / "config" / "config.js"


def configure_local_server():
    """ローカル開発用にShowdownサーバーの設定を変更"""

    if not CONFIG_FILE.exists():
        print(f"エラー: {CONFIG_FILE} が見つかりません")
        return False

    print(f"設定ファイルを読み込み: {CONFIG_FILE}")

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = f.read()

    # バックアップを作成
    backup_file = CONFIG_FILE.with_suffix(".js.backup")
    if not backup_file.exists():
        with open(backup_file, "w", encoding="utf-8") as f:
            f.write(config)
        print(f"✓ バックアップを作成: {backup_file}")

    modified = False

    # 1. ログインサーバーをnullに設定（認証を無効化）
    if "exports.loginserver = 'http://play.pokemonshowdown.com/';" in config:
        config = config.replace(
            "exports.loginserver = 'http://play.pokemonshowdown.com/';",
            "exports.loginserver = null; // ローカル開発用: 認証を無効化",
        )
        print("✓ ログインサーバーを無効化")
        modified = True

    # 2. autojoinsを設定（オプション: ログイン時に自動参加するチャンネル）
    if "exports.autojoins" not in config:
        # autojoinsの設定を追加
        autojoin_config = """

// ローカル開発用: 自動参加チャンネル
exports.autojoins = [];
"""
        # loginserver設定の後に挿入
        config = re.sub(
            r"(exports\.loginserver[^\n]*\n)",
            r"\1" + autojoin_config,
            config,
        )
        print("✓ autojoins設定を追加")
        modified = True

    if modified:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(config)
        print(f"\n✓ 設定ファイルを更新しました")
        print("\n次のステップ:")
        print("1. Showdownサーバーを再起動してください")
        print("   cd pokemon-showdown && node pokemon-showdown start")
        print("2. AIプレイヤーを実行してください")
        print("   python -m frontend.battle_ai_player")
        return True
    else:
        print("\n設定は既に適用されています")
        return True


if __name__ == "__main__":
    success = configure_local_server()
    exit(0 if success else 1)
