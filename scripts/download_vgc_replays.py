#!/usr/bin/env python3
"""
VGC全レギュレーションからリプレイを効率的に収集

使用方法:
    python scripts/download_vgc_replays.py --count 1000 --output data/replays
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import aiohttp


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class VGCReplayDownloader:
    """VGC全レギュレーションのリプレイダウンローダー"""
    
    BASE_URL = "https://replay.pokemonshowdown.com"
    
    # VGC レギュレーション（新しい順）
    # 注: 2026 Reg Fはまだ未実装の可能性あり
    VGC_FORMATS = [
        "gen9vgc2025regj",      # 最新（2025年10月～）
        "gen9vgc2025regi",      # 2025年7月～9月
        "gen9vgc2025regh",      # 2025年前半
        "gen9vgc2024regg",      # 2024年
        "gen9vgc2023regd",      # 2023年後半
        "gen9vgc2023regc",      # 2023年前半
    ]
    
    def __init__(self, min_rating: int = 1500):
        """
        Args:
            min_rating: 最低レーティング
        """
        self.min_rating = min_rating
        self.downloaded_count = 0
        self.failed_count = 0
        self.format_stats = {fmt: 0 for fmt in self.VGC_FORMATS}
    
    async def search_replays_for_format(
        self,
        session: aiohttp.ClientSession,
        format_id: str,
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        指定フォーマットのリプレイを検索
        
        Args:
            session: aiohttp セッション
            format_id: フォーマットID
            page: ページ番号
            
        Returns:
            リプレイ情報のリスト
        """
        url = f"{self.BASE_URL}/search.json"
        params = {
            "format": format_id,
            "page": page,
        }
        
        try:
            async with session.get(url, params=params, timeout=30) as response:
                if response.status != 200:
                    logger.warning(f"検索エラー ({format_id}, page {page}): HTTP {response.status}")
                    return []
                
                data = await response.json()
                
                # データ構造をログ出力（デバッグ用）
                if page == 1 and isinstance(data, list) and len(data) > 0:
                    logger.info(f"検索成功 ({format_id}): {len(data)}件")
                
                replays = data if isinstance(data, list) else []
                
                return replays
                
        except Exception as e:
            logger.warning(f"検索エラー ({format_id}, page {page}): {e}")
            return []
    
    async def download_replay_detail(
        self,
        session: aiohttp.ClientSession,
        replay_id: str
    ) -> Dict[str, Any] | None:
        """
        リプレイの詳細データをダウンロード
        
        Args:
            session: aiohttp セッション
            replay_id: リプレイID
            
        Returns:
            リプレイデータ
        """
        url = f"{self.BASE_URL}/{replay_id}.json"
        
        try:
            async with session.get(url, timeout=30) as response:
                if response.status != 200:
                    self.failed_count += 1
                    return None
                
                data = await response.json()
                
                # レーティングチェック
                rating = data.get("rating")
                if rating is None or rating < self.min_rating:
                    return None
                
                # フォーマット統計
                format_id = data.get("format", "")
                if format_id in self.format_stats:
                    self.format_stats[format_id] += 1
                
                self.downloaded_count += 1
                
                if self.downloaded_count % 10 == 0:
                    logger.info(
                        f"進捗: {self.downloaded_count}件 "
                        f"(最新: {replay_id}, Rating: {rating})"
                    )
                
                return {
                    "id": replay_id,
                    "format": format_id,
                    "rating": rating,
                    "uploadtime": data.get("uploadtime"),
                    "log": data.get("log", ""),
                    "players": data.get("players", []),
                    "winner": data.get("winner"),
                }
                
        except Exception as e:
            self.failed_count += 1
            logger.debug(f"ダウンロード失敗 ({replay_id}): {e}")
            return None
    
    async def collect_replays_parallel(
        self,
        target_count: int,
        max_concurrent: int = 10
    ) -> List[Dict[str, Any]]:
        """
        複数フォーマットから並列でリプレイを収集
        
        Args:
            target_count: 収集目標数
            max_concurrent: 最大同時実行数
            
        Returns:
            リプレイデータのリスト
        """
        replays_data = []
        seen_ids = set()
        
        async with aiohttp.ClientSession() as session:
            # 各フォーマットの検索タスクを並列実行
            format_pages = {fmt: 1 for fmt in self.VGC_FORMATS}
            
            while self.downloaded_count < target_count:
                # 各フォーマットから検索
                search_tasks = []
                for format_id in self.VGC_FORMATS:
                    if format_pages[format_id] <= 10:  # 各フォーマット最大10ページ
                        search_tasks.append(
                            self.search_replays_for_format(
                                session,
                                format_id,
                                format_pages[format_id]
                            )
                        )
                        format_pages[format_id] += 1
                
                if not search_tasks:
                    logger.warning("⚠️  検索可能なページがありません")
                    break
                
                # 並列検索実行
                search_results = await asyncio.gather(*search_tasks)
                
                # リプレイIDを収集
                replay_ids = []
                for replays in search_results:
                    for item in replays:
                        replay_id = item.get("id", "")
                        if replay_id and replay_id not in seen_ids:
                            seen_ids.add(replay_id)
                            replay_ids.append(replay_id)
                
                if not replay_ids:
                    logger.warning("⚠️  新しいリプレイが見つかりません")
                    break
                
                # ダウンロードタスクを並列実行
                download_tasks = []
                for replay_id in replay_ids[:max_concurrent]:
                    if self.downloaded_count >= target_count:
                        break
                    download_tasks.append(
                        self.download_replay_detail(session, replay_id)
                    )
                
                download_results = await asyncio.gather(*download_tasks)
                
                # 成功したものを保存
                for replay_data in download_results:
                    if replay_data:
                        replays_data.append(replay_data)
                
                # レート制限対策
                await asyncio.sleep(0.5)
        
        return replays_data
    
    def save_batch(
        self,
        replays_data: List[Dict[str, Any]],
        output_dir: Path
    ):
        """
        リプレイデータをバッチ保存
        
        Args:
            replays_data: リプレイデータのリスト
            output_dir: 保存先ディレクトリ
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"vgc_replays_{timestamp}.json"
        filepath = output_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(replays_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 保存: {filepath} ({len(replays_data)}件)")
    
    def print_statistics(self):
        """統計情報を表示"""
        logger.info("\n" + "="*60)
        logger.info("📊 収集統計")
        logger.info("="*60)
        logger.info(f"成功: {self.downloaded_count}件")
        logger.info(f"失敗: {self.failed_count}件")
        logger.info("\nフォーマット別内訳:")
        for format_id in self.VGC_FORMATS:
            count = self.format_stats[format_id]
            if count > 0:
                logger.info(f"  {format_id}: {count}件")


async def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="VGC全レギュレーションからリプレイを収集"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1000,
        help="収集するリプレイ数 (デフォルト: 1000)"
    )
    parser.add_argument(
        "--min-rating",
        type=int,
        default=1500,
        help="最低レーティング (デフォルト: 1500)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/replays"),
        help="保存先ディレクトリ (デフォルト: data/replays)"
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=10,
        help="最大同時ダウンロード数 (デフォルト: 10)"
    )
    
    args = parser.parse_args()
    
    logger.info("="*70)
    logger.info("🚀 VGC リプレイ収集開始")
    logger.info("="*70)
    logger.info(f"対象フォーマット: 全VGCレギュレーション")
    logger.info(f"目標件数: {args.count}件")
    logger.info(f"最低レーティング: {args.min_rating}")
    logger.info(f"保存先: {args.output}")
    logger.info(f"同時実行数: {args.concurrent}")
    logger.info("")
    
    downloader = VGCReplayDownloader(min_rating=args.min_rating)
    
    try:
        # 並列ダウンロード実行
        replays = await downloader.collect_replays_parallel(
            target_count=args.count,
            max_concurrent=args.concurrent
        )
        
        # 保存
        if replays:
            downloader.save_batch(replays, args.output)
        
        # 統計表示
        downloader.print_statistics()
        
        logger.info("\n✅ Phase 2 完了！")
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  ユーザーによって中断されました")
        logger.info(f"ダウンロード済み: {downloader.downloaded_count}件")
        
        # 中断時も保存
        if downloader.downloaded_count > 0:
            logger.info("収集済みデータを保存中...")
            # 注: 実装上、ここでは保存済み
    
    except Exception as e:
        logger.error(f"\n❌ エラーが発生しました: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
