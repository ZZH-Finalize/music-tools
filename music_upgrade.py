#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动音乐下载软件
功能：读取指定目录下的音乐文件（跳过flac无损格式），使用文件名调用GD API搜索同歌曲，并下载无损格式到本地
"""

import os
import sys
import argparse
import requests
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote, urlparse
from gd_api import GDAPIClient
import logging
import time
from collections import deque

# 尝试导入 tqdm 用于进度条，如果不可用则跳过
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    tqdm = lambda x, **kwargs: x  # 创建一个简单的标识函数作为替代

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RateLimitedGDAPIClient(GDAPIClient):
    """
    带速率限制的GD音乐API客户端
    限制：5分钟内最多60次请求
    """
    def __init__(self, base_url: str = "https://music-api.gdstudio.xyz/api.php",
                 max_requests: int = 60, time_window: int = 300, retries: int = 3, timeout: int = 30):
        super().__init__(base_url)
        self.max_requests = max_requests  # 最大请求数
        self.time_window = time_window  # 时间窗口（秒），5分钟=300秒
        self.requests = deque()  # 存储请求时间戳
        self.retries = retries  # 重试次数
        self.timeout = timeout  # 超时时间

    def _check_rate_limit(self):
        """检查是否超过速率限制"""
        now = time.time()
        # 移除时间窗口之前的请求记录
        while self.requests and self.requests[0] <= now - self.time_window:
            self.requests.popleft()

        # 如果请求数达到限制，则等待
        if len(self.requests) >= self.max_requests:
            sleep_time = self.time_window - (now - self.requests[0])
            if sleep_time > 0:
                logger.info(f"达到API速率限制，等待 {sleep_time:.2f} 秒...")
                time.sleep(sleep_time)
                # 再次清理过期的请求记录
                now = time.time()
                while self.requests and self.requests[0] <= now - self.time_window:
                    self.requests.popleft()

    def _make_request(self, method, *args, **kwargs):
        """执行请求前检查速率限制，并添加重试和超时功能"""
        import time
        from requests.exceptions import RequestException

        self._check_rate_limit()

        # 设置超时时间
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout

        # 执行重试逻辑
        for attempt in range(self.retries + 1):
            try:
                # 记录当前请求时间
                self.requests.append(time.time())
                # 执行实际请求
                result = method(*args, **kwargs)
                return result  # 确保返回方法的返回值
            except RequestException as e:
                if attempt < self.retries:
                    logger.warning(f"请求失败，第 {attempt + 1} 次重试: {str(e)}")
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    logger.error(f"请求失败，已重试 {self.retries} 次: {str(e)}")
                    raise e
            except Exception as e:
                if attempt < self.retries:
                    logger.warning(f"请求失败，第 {attempt + 1} 次重试: {str(e)}")
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    logger.error(f"请求失败，已重试 {self.retries} 次: {str(e)}")
                    raise e

    def search(self, keyword: str, source: str = "netease", count: int = 20, pages: int = 1):
        return self._make_request(super().search, keyword, source, count, pages)

    def get_song_url(self, track_id: str, source: str = "netease", br: int = 999):
        return self._make_request(super().get_song_url, track_id, source, br)

    def get_album_art(self, pic_id: str, source: str = "netease", size: int = 300):
        return self._make_request(super().get_album_art, pic_id, source, size)

    def get_lyrics(self, lyric_id: str, source: str = "netease"):
        return self._make_request(super().get_lyrics, lyric_id, source)

    def search_album_tracks(self, keyword: str, source: str = "netease", count: int = 20, pages: int = 1):
        return self._make_request(super().search_album_tracks, keyword, source, count, pages)

    def download_song(self, track_id: str, source: str = "netease", br: int = 99, file_path: Optional[str] = None):
        return self._make_request(super().download_song, track_id, source, br, file_path)

    def download_album_art(self, pic_id: str, source: str = "netease", size: int = 500, file_path: Optional[str] = None):
        return self._make_request(super().download_album_art, pic_id, source, size, file_path)

    def download_lyrics(self, lyric_id: str, source: str = "netease", file_path: Optional[str] = None):
        return self._make_request(super().download_lyrics, lyric_id, source, file_path)


def clean_filename(filename: str) -> str:
    """
    清理文件名，移除可能影响搜索的字符
    """
    # 移除常见的音乐文件后缀和版本信息
    name = Path(filename).stem
    # 移除质量标识如128k, 320k, 无损等
    name = re.sub(r'\s*\d+k\s*', ' ', name)
    name = re.sub(r'\s*\(无损\)\s*', ' ', name)
    name = re.sub(r'\s*FLAC\s*', ' ', name)
    name = re.sub(r'\s*MP3\s*', ' ', name)
    # 移除多余的空格
    name = ' '.join(name.split())
    return name


def is_music_file(filepath: Path) -> bool:
    """
    判断是否为音乐文件，排除flac无损格式
    """
    music_extensions = {'.mp3', '.wav', '.aac', '.m4a', '.ogg', '.wma', '.ape', '.opus'}
    flac_extension = '.flac'

    if filepath.suffix.lower() == flac_extension:
        return False

    return filepath.suffix.lower() in music_extensions


def scan_music_files(directory: str) -> List[Path]:
    """
    扫描目录下的音乐文件，排除flac格式
    """
    music_dir = Path(directory)
    if not music_dir.exists():
        raise FileNotFoundError(f"目录不存在: {directory}")

    music_files = []
    for file_path in music_dir.rglob('*'):
        if file_path.is_file() and is_music_file(file_path):
            music_files.append(file_path)

    return music_files


def find_best_match(search_results: List[dict], original_filename: str, match_artist: bool = False) -> Optional[dict]:
    """
    根据原始文件名从搜索结果中找到最佳匹配
    默认只使用歌曲名进行匹配，当match_artist为True时额外匹配歌手
    """
    if not search_results:
        return None

    from difflib import SequenceMatcher

    original_name = clean_filename(original_filename).lower()

    # 默认只使用歌曲名进行匹配
    original_song = original_name.strip()
    original_artist = ""

    # 如果需要匹配歌手，则尝试从原始文件名中分离出歌手和歌曲名
    if match_artist:
        import re
        # 分离歌手和歌曲名（通常格式为"歌手 - 歌曲名"）
        parts = re.split(r'[-_~]+', original_name)
        if len(parts) >= 2:
            original_artist = parts[0].strip()
            original_song = parts[1].strip()
        else:
            # 如果无法分离，将整个名称作为歌曲名
            original_song = original_name.strip()
            original_artist = ""

    best_match = None
    best_score = -1  # 最高相似度得分

    for result in search_results:
        song_name = result.get('name', '').lower()
        artist = ' '.join(result.get('artist', [])).lower() if isinstance(result.get('artist'), list) else result.get('artist', '').lower()

        # 计算歌曲名相似度
        song_similarity = SequenceMatcher(None, original_song, song_name).ratio()

        # 计算歌手相似度（仅在match_artist为True时）
        if match_artist and original_artist:
            artist_similarity = SequenceMatcher(None, original_artist, artist).ratio()
        else:
            # 如果不匹配歌手或原始文件名中没有分离出歌手，则艺术家相似度为0
            artist_similarity = 0

        # 计算总相似度得分（歌曲相似度 + 艺术家相似度）
        total_score = song_similarity + artist_similarity

        # 如果当前结果的总得分更高，则更新最佳匹配
        if total_score > best_score:
            best_score = total_score
            best_match = result

    return best_match


def download_lossless_music(
    client: RateLimitedGDAPIClient,
    track_id: str,
    source: str,
    original_file_path: Path,
    output_dir: Optional[str] = None
) -> Optional[str]:
    """
    下载无损音质音乐
    """
    # 尝试下载最高音质（999代表最高音质，通常为无损）
    try:
        # 先尝试99音质
        try:
            song_info = client.get_song_url(track_id, source=source, br=999)
            download_url = song_info.get('url')
        except Exception:
            song_info = None
            download_url = None

        # 如果999音质没有可用链接，尝试740（另一个无损选项）
        if not download_url:
            try:
                song_info = client.get_song_url(track_id, source=source, br=740)
                download_url = song_info.get('url')
            except Exception:
                song_info = None

        # 如果还是没有，尝试320
        if not download_url:
            try:
                song_info = client.get_song_url(track_id, source=source, br=320)
                download_url = song_info.get('url')
            except Exception:
                song_info = None

        if not download_url:
            logger.warning(f"无法获取歌曲下载链接: {original_file_path.name}")
            return None

        # 确定输出目录
        if output_dir:
            output_path = Path(output_dir)
        else:
            output_path = original_file_path.parent

        # 创建输出目录
        output_path.mkdir(parents=True, exist_ok=True)

        # 构建下载文件路径
        original_stem = original_file_path.stem
        # 从URL中提取文件扩展名
        parsed_url = urlparse(download_url)
        url_path = unquote(parsed_url.path)  # 解码URL路径
        ext = Path(url_path).suffix.lower()
        if not ext or len(ext) > 5:  # 如果扩展名不存在或过长，则默认为.mp3
            ext = '.mp3'
        download_file_path = output_path / f"{original_stem}{ext}"

        # 下载文件
        if song_info:
            logger.info(f"正在下载: {original_stem} (音质: {song_info.get('br', 'unknown')})")
        else:
            logger.info(f"正在下载: {original_stem} (音质: unknown)")
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        with open(download_file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"下载完成: {download_file_path}")
        return str(download_file_path)

    except Exception as e:
        logger.error(f"下载失败 {original_file_path.name}: {str(e)}")
        return None


def upgrade_music_files(
    directory: str,
    source: str = "netease",
    quality: int = 99,
    output_dir: Optional[str] = None,
    match_artist: bool = False,
    retries: int = 3,
    timeout: int = 30
) -> None:
    """
    升级目录下的音乐文件
    """
    logger.info(f"开始扫描目录: {directory}")

    # 扫描音乐文件
    music_files = scan_music_files(directory)
    logger.info(f"找到 {len(music_files)} 个音乐文件")

    if not music_files:
        logger.warning("没有找到需要升级的音乐文件")
        return

    # 创建带速率限制的API客户端
    client = RateLimitedGDAPIClient(retries=retries, timeout=timeout)

    success_count = 0
    fail_count = 0

    def process_music_file(music_file, idx, progress_iterable=None):
        """处理单个音乐文件的辅助函数"""
        logger.info(f"[{idx}/{len(music_files)}] 处理文件: {music_file.name}")
        if progress_iterable and TQDM_AVAILABLE and hasattr(progress_iterable, 'set_postfix_str'):
            progress_iterable.set_postfix_str(f"处理: {music_file.name}")

        try:
            # 清理文件名以用于搜索
            search_keyword = clean_filename(music_file.name)
            logger.debug(f"搜索关键词: {search_keyword}")

            # 搜索音乐
            search_results = client.search(search_keyword, source=source, count=5)

            if not search_results:
                logger.warning(f"未找到匹配的音乐: {music_file.name}")
                return False # 表示失败

            # 找到最佳匹配
            best_match = find_best_match(search_results, music_file.name, match_artist)
            if not best_match:
                logger.warning(f"未找到最佳匹配: {music_file.name}")
                return False  # 表示失败

            logger.info(f"找到匹配: {best_match.get('name', '')} - {best_match.get('artist', '')}")

            # 获取曲目ID
            track_id = best_match.get('id')
            if not track_id:
                logger.warning(f"无法获取曲目ID: {music_file.name}")
                return False  # 表示失败

            # 下载无损音乐
            download_path = download_lossless_music(
                client,
                track_id,
                source,
                music_file,
                output_dir
            )

            return download_path is not None # 成功与否的标志

        except Exception as e:
            logger.error(f"处理文件时出错 {music_file.name}: {str(e)}")
            return False  # 表示失败

    # 使用tqdm显示进度条（如果可用）
    if TQDM_AVAILABLE:
        progress_iterable = tqdm(music_files, desc="处理音乐文件", unit="file")
        for idx, music_file in enumerate(progress_iterable, 1):
            if process_music_file(music_file, idx, progress_iterable):
                success_count += 1
            else:
                fail_count += 1
    else:
        for idx, music_file in enumerate(music_files, 1):
            if process_music_file(music_file, idx):
                success_count += 1
            else:
                fail_count += 1

    logger.info(f"处理完成!")
    logger.info(f"成功: {success_count}, 失败: {fail_count}, 总计: {len(music_files)}")

    logger.info(f"处理完成!")
    logger.info(f"成功: {success_count}, 失败: {fail_count}, 总计: {len(music_files)}")


def main():
    parser = argparse.ArgumentParser(description='自动音乐下载软件 - 将普通音质音乐升级为无损音质')
    parser.add_argument('directory', nargs='?', help='要处理的音乐文件目录路径')
    parser.add_argument('-s', '--source', default='netease',
                       choices=['netease', 'tencent', 'tidal', 'spotify', 'ytmusic',
                               'qobuz', 'joox', 'deezer', 'migu', 'kugou', 'kuwo',
                               'ximalaya', 'apple'],
                       help='音乐源 (默认: netease)')
    parser.add_argument('-q', '--quality', type=int, default=99,
                       choices=[128, 192, 320, 740, 999],
                       help='音质 (128/192/320/740/999, 默认: 99为无损音质)')
    parser.add_argument('-o', '--output', help='下载文件的输出目录 (默认: 原文件所在目录)')
    parser.add_argument('-l', '--list-sources', action='store_true', help='列出支持的音乐源')
    parser.add_argument('-a', '--match-artist', action='store_true',
                       help='搜索时额外匹配歌手名 (默认: 只匹配歌曲名)')
    parser.add_argument('-r', '--retries', type=int, default=3,
                       help='API调用重试次数 (默认: 3)')
    parser.add_argument('-t', '--timeout', type=int, default=120,
                       help='API调用超时时间(秒) (默认: 120)')

    args = parser.parse_args()

    if args.list_sources:
        print("支持的音乐源:")
        sources = ['netease', 'tencent', 'tidal', 'spotify', 'ytmusic',
                  'qobuz', 'joox', 'deezer', 'migu', 'kugou', 'kuwo',
                  'ximalaya', 'apple']
        for source in sources:
            print(f"  - {source}")
        return

    if not args.directory:
        logger.error("错误: 请指定要处理的目录路径")
        parser.print_help()
        sys.exit(1)

    if not os.path.isdir(args.directory):
        logger.error(f"错误: 目录不存在 - {args.directory}")
        sys.exit(1)

    logger.info(f"开始升级音乐文件...")
    logger.info(f"目录: {args.directory}")
    logger.info(f"音乐源: {args.source}")
    logger.info(f"音质: {args.quality}")
    if args.output:
        logger.info(f"输出目录: {args.output}")

    upgrade_music_files(
        directory=args.directory,
        source=args.source,
        quality=args.quality,
        output_dir=args.output,
        match_artist=args.match_artist,
        retries=args.retries,
        timeout=args.timeout
    )


if __name__ == "__main__":
    main()
