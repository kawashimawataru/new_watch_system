"""
Phase 2: データセット作成 - リプレイダウンロード

目的: Pokemon Showdown公式サイトから対戦リプレイをダウンロードし、
     学習用データセットを構築する。

実行方法:
    python scripts/phase2_download_replays.py --format gen9ou --count 100

引数:
    --format: 対戦フォーマット (gen9ou, gen9vgc2024, など)
    --count: ダウンロードするリプレイ数
    --min-rating: 最低レーティング (デフォルト: 1500)
    --output: 保存先ディレクトリ (デフォルト: data/replays/)
"""

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

try:
    import aiohttp
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ 必要なパッケージがインストールされていません")
    print("インストール: pip install aiohttp beautifulsoup4 lxml")
    exit(1)


class ReplayDownloader:
    """Pokemon Showdownのリプレイをダウンロードするクラス"""
    
    BASE_URL = "https://replay.pokemonshowdown.com"
    
    def __init__(self, format_id: str, min_rating: int = 1500):
        self.format_id = format_id
        self.min_rating = min_rating
        self.downloaded_count = 0
        self.failed_count = 0
    
    async def search_replays(
        self,
        session: aiohttp.ClientSession,
        page: int = 1
    ) -> List[str]:
        """
        指定フォーマットのリプレイを検索
        
        Returns:
            リプレイIDのリスト
        """
        # 検索APIを使用（ページネーション対応）
        url = f"{self.BASE_URL}/search.json"
        params = {
            "format": self.format_id,
            "page": page,
        }
        
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    print(f"⚠️  検索エラー (ページ {page}): HTTP {response.status}")
                    print(f"   URL: {url}?format={self.format_id}&page={page}")
                    return []
                
                data = await response.json()
                
                # JSONレスポンスからリプレイIDを抽出
                replays = data if isinstance(data, list) else []
                replay_ids = []
                
                for item in replays:
                    if isinstance(item, dict):
                        replay_id = item.get("id", "")
                        if replay_id:
                            replay_ids.append(replay_id)
                    elif isinstance(item, str):
                        replay_ids.append(item)
                
                print(f"📄 ページ {page}: {len(replay_ids)}件のリプレイを発見")
                return replay_ids
                
        except Exception as e:
            print(f"❌ 検索エラー (ページ {page}): {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def download_replay(
        self,
        session: aiohttp.ClientSession,
        replay_id: str
    ) -> Dict[str, Any] | None:
        """
        リプレイの詳細データをダウンロード
        
        Returns:
            リプレイデータ (JSON形式) または None
        """
        url = f"{self.BASE_URL}/{replay_id}.json"
        
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    self.failed_count += 1
                    return None
                
                data = await response.json()
                
                # レーティングチェック
                rating = data.get("rating")
                if rating is None or rating < self.min_rating:
                    return None
                
                self.downloaded_count += 1
                print(f"✅ [{self.downloaded_count}] {replay_id} (Rating: {rating})")
                
                return {
                    "id": replay_id,
                    "format": data.get("format"),
                    "rating": rating,
                    "uploadtime": data.get("uploadtime"),
                    "log": data.get("log", ""),
                    "players": data.get("players", []),
                    "winner": data.get("winner"),
                }
                
        except Exception as e:
            self.failed_count += 1
            print(f"❌ ダウンロード失敗 ({replay_id}): {e}")
            return None
    
    async def download_batch(
        self,
        target_count: int,
        output_dir: Path
    ) -> int:
        """
        指定数のリプレイをダウンロード
        
        Returns:
            ダウンロード成功数
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        async with aiohttp.ClientSession() as session:
            page = 1
            replays_data = []
            
            while self.downloaded_count < target_count:
                print(f"\n{'='*60}")
                print(f"ページ {page} を検索中...")
                print(f"{'='*60}")
                
                # リプレイIDを検索
                replay_ids = await self.search_replays(session, page)
                
                if not replay_ids:
                    print("⚠️  これ以上のリプレイが見つかりません")
                    break
                
                # 各リプレイをダウンロード
                for replay_id in replay_ids:
                    if self.downloaded_count >= target_count:
                        break
                    
                    replay_data = await self.download_replay(session, replay_id)
                    
                    if replay_data:
                        replays_data.append(replay_data)
                        
                        # 定期的に保存
                        if len(replays_data) % 10 == 0:
                            self._save_batch(replays_data, output_dir)
                    
                    # レート制限対策
                    await asyncio.sleep(0.5)
                
                page += 1
            
            # 最終保存
            if replays_data:
                self._save_batch(replays_data, output_dir)
        
        return self.downloaded_count
    
    def _save_batch(self, replays_data: List[Dict[str, Any]], output_dir: Path):
        """バッチでデータを保存"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.format_id}_{timestamp}.json"
        filepath = output_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(replays_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 保存: {filepath} ({len(replays_data)}件)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pokemon Showdownのリプレイをダウンロード"
    )
    parser.add_argument(
        "--format",
        type=str,
        default="gen9ou",
        help="対戦フォーマット (例: gen9ou, gen9vgc2024regh)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="ダウンロードするリプレイ数",
    )
    parser.add_argument(
        "--min-rating",
        type=int,
        default=1500,
        help="最低レーティング",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/replays"),
        help="保存先ディレクトリ",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    
    print("=" * 70)
    print("Phase 2: リプレイダウンロード")
    print("=" * 70)
    print()
    print(f"フォーマット: {args.format}")
    print(f"目標件数: {args.count}件")
    print(f"最低レーティング: {args.min_rating}")
    print(f"保存先: {args.output}")
    print()
    
    downloader = ReplayDownloader(args.format, args.min_rating)
    
    try:
        downloaded = await downloader.download_batch(args.count, args.output)
        
        print()
        print("=" * 70)
        print("ダウンロード完了")
        print("=" * 70)
        print(f"成功: {downloaded}件")
        print(f"失敗: {downloader.failed_count}件")
        print(f"保存先: {args.output}")
        print()
        print("✅ Phase 2 完了！")
        print()
        
    except KeyboardInterrupt:
        print()
        print("⚠️  ユーザーによって中断されました")
        print(f"ダウンロード済み: {downloader.downloaded_count}件")
    except Exception as e:
        print()
        print(f"❌ エラーが発生しました: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
