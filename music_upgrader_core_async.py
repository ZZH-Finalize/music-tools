#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音乐升级核心库 - 异步版本
包含音乐文件扫描、匹配、下载等核心功能，所有API调用均为异步
"""

import os
import requests
import re
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from urllib.parse import unquote, urlparse
from gd_api import GDAPIClient
import logging
import time
from collections import deque
from difflib import SequenceMatcher


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AsyncRateLimitedGDAPIClient(GDAPIClient):
    """
    异步带速率限制的GD音乐API客户端
    限制：5分钟内最多60次请求
    """
    def __init__(self, base_url: str = "https://music-api.gdstudio.xyz/api.php",
                 max_requests: int = 60, time_window: int = 300, retries: int = 3, timeout: int = 10):
        super().__init__(base_url)
        self.max_requests = max_requests  # 最大请求数
        self.time_window = time_window  # 时间窗口（秒），5分钟=300秒
        self.requests = deque()  # 存储请求时间戳
        self.retries = retries  # 重试次数
        self.timeout = timeout  # 超时时间（10秒）

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
        from requests.exceptions import RequestException, Timeout

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
            except Timeout as e:
                if attempt < self.retries:
                    logger.warning(f"请求超时，第 {attempt + 1} 次重试: {str(e)}")
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    logger.error(f"请求超时，已重试 {self.retries} 次: {str(e)}")
                    raise e
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

    def search_async(self, keyword: str, source: str = "netease", count: int = 20, pages: int = 1,
                     callback: Optional[Callable] = None, **kwargs):
        """异步搜索音乐"""
        def search_task():
            result = None
            error = None
            try:
                result = self._make_request(super(AsyncRateLimitedGDAPIClient, self).search, keyword, source, count, pages, **kwargs)
                result = result if result is not None else []
            except Exception as e:
                error = e
            if callback:
                callback(result, error)

        thread = threading.Thread(target=search_task, daemon=True)
        thread.start()
        return thread

    def get_song_url_async(self, track_id: str, source: str = "netease", br: int = 999,
                          callback: Optional[Callable] = None, **kwargs):
        """异步获取歌曲链接"""
        def get_song_url_task():
            result = None
            error = None
            try:
                result = self._make_request(super(AsyncRateLimitedGDAPIClient, self).get_song_url, track_id, source, br, **kwargs)
                result = result if result is not None else {}
            except Exception as e:
                error = e
            if callback:
                callback(result, error)

        thread = threading.Thread(target=get_song_url_task, daemon=True)
        thread.start()
        return thread

    def get_album_art_async(self, pic_id: str, source: str = "netease", size: int = 300,
                           callback: Optional[Callable] = None, **kwargs):
        """异步获取专辑图"""
        def get_album_art_task():
            result = None
            error = None
            try:
                result = self._make_request(super(AsyncRateLimitedGDAPIClient, self).get_album_art, pic_id, source, size, **kwargs)
                result = result if result is not None else {}
            except Exception as e:
                error = e
            if callback:
                callback(result, error)

        thread = threading.Thread(target=get_album_art_task, daemon=True)
        thread.start()
        return thread

    def get_lyrics_async(self, lyric_id: str, source: str = "netease",
                        callback: Optional[Callable] = None, **kwargs):
        """异步获取歌词"""
        def get_lyrics_task():
            result = None
            error = None
            try:
                result = self._make_request(super(AsyncRateLimitedGDAPIClient, self).get_lyrics, lyric_id, source, **kwargs)
                result = result if result is not None else {}
            except Exception as e:
                error = e
            if callback:
                callback(result, error)

        thread = threading.Thread(target=get_lyrics_task, daemon=True)
        thread.start()
        return thread

    def search_album_tracks_async(self, keyword: str, source: str = "netease", count: int = 20, pages: int = 1,
                                 callback: Optional[Callable] = None, **kwargs):
        """异步搜索专辑中的曲目列表"""
        def search_album_tracks_task():
            result = None
            error = None
            try:
                result = self._make_request(super(AsyncRateLimitedGDAPIClient, self).search_album_tracks, keyword, source, count, pages, **kwargs)
                result = result if result is not None else []
            except Exception as e:
                error = e
            if callback:
                callback(result, error)

        thread = threading.Thread(target=search_album_tracks_task, daemon=True)
        thread.start()
        return thread

    def download_song_async(self, track_id: str, source: str = "netease", br: int = 99,
                           file_path: Optional[str] = None, callback: Optional[Callable] = None, **kwargs):
        """异步下载歌曲"""
        def download_song_task():
            result = None
            error = None
            try:
                result = self._make_request(super(AsyncRateLimitedGDAPIClient, self).download_song, track_id, source, br, file_path, **kwargs)
                result = result if result is not None else ""
            except Exception as e:
                error = e
            if callback:
                callback(result, error)

        thread = threading.Thread(target=download_song_task, daemon=True)
        thread.start()
        return thread

    def download_album_art_async(self, pic_id: str, source: str = "netease", size: int = 500,
                                file_path: Optional[str] = None, callback: Optional[Callable] = None, **kwargs):
        """异步下载专辑图"""
        def download_album_art_task():
            result = None
            error = None
            try:
                result = self._make_request(super(AsyncRateLimitedGDAPIClient, self).download_album_art, pic_id, source, size, file_path, **kwargs)
                result = result if result is not None else ""
            except Exception as e:
                error = e
            if callback:
                callback(result, error)

        thread = threading.Thread(target=download_album_art_task, daemon=True)
        thread.start()
        return thread

    def download_lyrics_async(self, lyric_id: str, source: str = "netease",
                             file_path: Optional[str] = None, callback: Optional[Callable] = None, **kwargs):
        """异步下载歌词"""
        def download_lyrics_task():
            result = None
            error = None
            try:
                result = self._make_request(super(AsyncRateLimitedGDAPIClient, self).download_lyrics, lyric_id, source, file_path, **kwargs)
                result = result if result is not None else ""
            except Exception as e:
                error = e
            if callback:
                callback(result, error)

        thread = threading.Thread(target=download_lyrics_task, daemon=True)
        thread.start()
        return thread


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


def download_lossless_music_async(
    client: AsyncRateLimitedGDAPIClient,
    track_id: str,
    source: str,
    original_file_path: Path,
    output_dir: Optional[str] = None,
    callback: Optional[Callable] = None
):
    """
    异步下载无损音质音乐
    """
    def download_task():
        result = None
        error = None
        try:
            # 尝试下载最高音质（999代表最高音质，通常为无损）
            song_info = None
            download_url = None

            # 先尝试999音质
            try:
                song_info_result = [None, None] # [result, error]
                def get_song_url_callback(res, err):
                    song_info_result[0] = res
                    song_info_result[1] = err

                thread = client.get_song_url_async(track_id, source=source, br=999, callback=get_song_url_callback)
                thread.join()  # 等待完成

                if song_info_result[1]:  # 有错误
                    raise song_info_result[1]

                song_info = song_info_result[0]
                if song_info and 'url' in song_info:
                    download_url = song_info.get('url')
            except Exception:
                pass

            # 如果999音质没有可用链接，尝试740（另一个无损选项）
            if not download_url:
                try:
                    song_info_result = [None, None] # [result, error]
                    def get_song_url_callback(res, err):
                        song_info_result[0] = res
                        song_info_result[1] = err

                    thread = client.get_song_url_async(track_id, source=source, br=740, callback=get_song_url_callback)
                    thread.join()  # 等待完成

                    if song_info_result[1]:  # 有错误
                        raise song_info_result[1]

                    song_info = song_info_result[0]
                    if song_info and 'url' in song_info:
                        download_url = song_info.get('url')
                except Exception:
                    pass

            # 如果还是没有，尝试320
            if not download_url:
                try:
                    song_info_result = [None, None] # [result, error]
                    def get_song_url_callback(res, err):
                        song_info_result[0] = res
                        song_info_result[1] = err

                    thread = client.get_song_url_async(track_id, source=source, br=320, callback=get_song_url_callback)
                    thread.join() # 等待完成

                    if song_info_result[1]:  # 有错误
                        raise song_info_result[1]

                    song_info = song_info_result[0]
                    if song_info and 'url' in song_info:
                        download_url = song_info.get('url')
                except Exception:
                    pass

            if not download_url:
                logger.warning(f"无法获取歌曲下载链接: {original_file_path.name}")
                result = None
            else:
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
                response = requests.get(download_url, stream=True, timeout=client.timeout)
                response.raise_for_status()

                with open(download_file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                logger.info(f"下载完成: {download_file_path}")
                result = str(download_file_path)

        except Exception as e:
            logger.error(f"下载失败 {original_file_path.name}: {str(e)}")
            error = e
            result = None

        if callback:
            callback(result, error)

    thread = threading.Thread(target=download_task, daemon=True)
    thread.start()
    return thread


def upgrade_music_files_async(
    directory: str,
    source: str = "netease",
    quality: int = 9,
    output_dir: Optional[str] = None,
    match_artist: bool = False,
    retries: int = 3,
    timeout: int = 30,
    progress_callback: Optional[Callable] = None,
    completion_callback: Optional[Callable] = None
) -> None:
    """
    异步升级目录下的音乐文件
    """
    def upgrade_task():
        logger.info(f"开始扫描目录: {directory}")

        # 扫描音乐文件
        music_files = scan_music_files(directory)
        logger.info(f"找到 {len(music_files)} 个音乐文件")

        if not music_files:
            logger.warning("没有找到需要升级的音乐文件")
            if completion_callback:
                completion_callback(0, 0, len(music_files))
            return

        # 创建带速率限制的API客户端
        client = AsyncRateLimitedGDAPIClient(retries=retries, timeout=timeout)

        success_count = 0
        fail_count = 0

        def process_music_file(music_file, idx):
            """处理单个音乐文件的辅助函数"""
            logger.info(f"[{idx}/{len(music_files)}] 处理文件: {music_file.name}")

            # 更新进度
            if progress_callback:
                progress_callback(idx, len(music_files))

            try:
                # 清理文件名以用于搜索
                search_keyword = clean_filename(music_file.name)
                # 将&替换为英文逗号
                search_keyword = search_keyword.replace('&', ',')
                logger.debug(f"搜索关键词: {search_keyword}")

                # 异步搜索音乐
                search_result = [None, None]  # [result, error]
                def search_callback(res, err):
                    search_result[0] = res
                    search_result[1] = err

                thread = client.search_async(search_keyword, source=source, count=5, callback=search_callback)
                thread.join()  # 等待完成

                if search_result[1]:  # 有错误
                    logger.error(f"搜索失败 {music_file.name}: {search_result[1]}")
                    return False  # 表示失败

                search_results = search_result[0]
                if not search_results:
                    logger.warning(f"未找到匹配的音乐: {music_file.name}")
                    return False  # 表示失败

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

                # 异步下载无损音乐
                download_result = [None, None] # [result, error]
                def download_callback(res, err):
                    download_result[0] = res
                    download_result[1] = err

                download_lossless_music_async(
                    client,
                    track_id,
                    source,
                    music_file,
                    output_dir,
                    callback=download_callback
                )

                # 等待下载完成
                thread.join()

                if download_result[1]:  # 有错误
                    logger.error(f"下载失败 {music_file.name}: {download_result[1]}")
                    return False  # 表示失败

                return download_result[0] is not None  # 成功与否的标志

            except Exception as e:
                logger.error(f"处理文件时出错 {music_file.name}: {str(e)}")
                return False  # 表示失败

        # 处理所有音乐文件
        for idx, music_file in enumerate(music_files, 1):
            if process_music_file(music_file, idx):
                success_count += 1
            else:
                fail_count += 1

        logger.info(f"处理完成!")
        logger.info(f"成功: {success_count}, 失败: {fail_count}, 总计: {len(music_files)}")

        if completion_callback:
            completion_callback(success_count, fail_count, len(music_files))

    thread = threading.Thread(target=upgrade_task, daemon=True)
    thread.start()


def match_music_files_async(
    directory: str,
    source: str = "netease",
    match_artist: bool = False,
    retries: int = 3,
    timeout: int = 30,
    progress_callback: Optional[Callable] = None,
    completion_callback: Optional[Callable] = None
) -> None:
    """
    异步匹配目录下的音乐文件，返回匹配结果列表
    """
    def match_task():
        logger.info(f"开始扫描目录: {directory}")

        # 扫描音乐文件
        music_files = scan_music_files(directory)
        logger.info(f"找到 {len(music_files)} 个音乐文件")

        if not music_files:
            logger.warning("没有找到需要匹配的音乐文件")
            if completion_callback:
                completion_callback([])
            return

        # 创建带速率限制的API客户端
        client = AsyncRateLimitedGDAPIClient(retries=retries, timeout=timeout)

        matched_results = []

        for idx, music_file in enumerate(music_files, 1):
            logger.info(f"[{idx}/{len(music_files)}] 匹配文件: {music_file.name}")

            # 更新进度
            if progress_callback:
                progress_callback(idx, len(music_files))

            try:
                # 清理文件名以用于搜索
                search_keyword = clean_filename(music_file.name)
                # 将&替换为英文逗号
                search_keyword = search_keyword.replace('&', ',')
                logger.debug(f"搜索关键词: {search_keyword}")

                # 异步搜索音乐
                search_result = [None, None] # [result, error]
                def search_callback(res, err):
                    search_result[0] = res
                    search_result[1] = err

                thread = client.search_async(search_keyword, source=source, count=5, callback=search_callback)
                thread.join()  # 等待完成

                if search_result[1]:  # 有错误
                    logger.error(f"搜索失败 {music_file.name}: {search_result[1]}")
                    matched_results.append({
                        "file_path": music_file,
                        "file_name": music_file.name,
                        "matched_song": {"name": "匹配失败", "artist": "", "id": None}
                    })
                    continue

                search_results = search_result[0]
                if not search_results:
                    logger.warning(f"未找到匹配的音乐: {music_file.name}")
                    matched_results.append({
                        "file_path": music_file,
                        "file_name": music_file.name,
                        "matched_song": {"name": "未找到匹配", "artist": "", "id": None}
                    })
                    continue

                # 找到最佳匹配
                best_match = find_best_match(search_results, music_file.name, match_artist)
                if not best_match:
                    logger.warning(f"未找到最佳匹配: {music_file.name}")
                    matched_results.append({
                        "file_path": music_file,
                        "file_name": music_file.name,
                        "matched_song": {"name": "未找到匹配", "artist": "", "id": None}
                    })
                    continue

                logger.info(f"找到匹配: {best_match.get('name', '')} - {best_match.get('artist', '')}")

                matched_results.append({
                    "file_path": music_file,
                    "file_name": music_file.name,
                    "matched_song": best_match
                })

            except Exception as e:
                logger.error(f"匹配文件时出错 {music_file.name}: {str(e)}")
                matched_results.append({
                    "file_path": music_file,
                    "file_name": music_file.name,
                    "matched_song": {"name": "匹配失败", "artist": "", "id": None}
                })

        logger.info(f"匹配完成! 总计: {len(music_files)}")

        if completion_callback:
            completion_callback(matched_results)

    thread = threading.Thread(target=match_task, daemon=True)
    thread.start()


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
    升级目录下的音乐文件（同步版本，使用异步API但同步等待）
    """
    logger.info(f"开始扫描目录: {directory}")

    # 扫描音乐文件
    music_files = scan_music_files(directory)
    logger.info(f"找到 {len(music_files)} 个音乐文件")

    if not music_files:
        logger.warning("没有找到需要升级的音乐文件")
        return

    # 创建带速率限制的API客户端
    client = AsyncRateLimitedGDAPIClient(retries=retries, timeout=timeout)

    success_count = 0
    fail_count = 0

    def process_music_file(music_file, idx, progress_iterable=None):
        """处理单个音乐文件的辅助函数"""
        logger.info(f"[{idx}/{len(music_files)}] 处理文件: {music_file.name}")

        try:
            # 清理文件名以用于搜索
            search_keyword = clean_filename(music_file.name)
            # 将&替换为英文逗号
            search_keyword = search_keyword.replace('&', ',')
            logger.debug(f"搜索关键词: {search_keyword}")

            # 异步搜索音乐，但同步等待结果
            search_result = [None, None] # [result, error]
            def search_callback(res, err):
                search_result[0] = res
                search_result[1] = err

            thread = client.search_async(search_keyword, source=source, count=5, callback=search_callback)
            thread.join()  # 等待完成

            if search_result[1]:  # 有错误
                logger.error(f"搜索失败 {music_file.name}: {search_result[1]}")
                return False # 表示失败

            search_results = search_result[0]
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

            # 异步下载无损音乐，但同步等待结果
            download_result = [None, None]  # [result, error]
            def download_callback(res, err):
                download_result[0] = res
                download_result[1] = err

            download_thread = download_lossless_music_async(
                client,
                track_id,
                source,
                music_file,
                output_dir,
                callback=download_callback
            )

            download_thread.join()  # 等待下载完成

            if download_result[1]:  # 有错误
                logger.error(f"下载失败 {music_file.name}: {download_result[1]}")
                return False # 表示失败

            return download_result[0] is not None # 成功与否的标志

        except Exception as e:
            logger.error(f"处理文件时出错 {music_file.name}: {str(e)}")
            return False  # 表示失败

    # 简单循环处理
    for idx, music_file in enumerate(music_files, 1):
        if process_music_file(music_file, idx):
            success_count += 1
        else:
            fail_count += 1

    logger.info(f"处理完成!")
    logger.info(f"成功: {success_count}, 失败: {fail_count}, 总计: {len(music_files)}")


def match_music_files(
    directory: str,
    source: str = "netease",
    match_artist: bool = False,
    retries: int = 3,
    timeout: int = 30
) -> List[Dict[str, Any]]:
    """
    匹配目录下的音乐文件，返回匹配结果列表（同步版本，使用异步API但同步等待）
    """
    logger.info(f"开始扫描目录: {directory}")

    # 扫描音乐文件
    music_files = scan_music_files(directory)
    logger.info(f"找到 {len(music_files)} 个音乐文件")

    if not music_files:
        logger.warning("没有找到需要匹配的音乐文件")
        return []

    # 创建带速率限制的API客户端
    client = AsyncRateLimitedGDAPIClient(retries=retries, timeout=timeout)

    matched_results = []

    for idx, music_file in enumerate(music_files, 1):
        logger.info(f"[{idx}/{len(music_files)}] 匹配文件: {music_file.name}")

        try:
            # 清理文件名以用于搜索
            search_keyword = clean_filename(music_file.name)
            # 将&替换为英文逗号
            search_keyword = search_keyword.replace('&', ',')
            logger.debug(f"搜索关键词: {search_keyword}")

            # 异步搜索音乐，但同步等待结果
            search_result = [None, None] # [result, error]
            def search_callback(res, err):
                search_result[0] = res
                search_result[1] = err

            thread = client.search_async(search_keyword, source=source, count=5, callback=search_callback)
            thread.join()  # 等待完成

            if search_result[1]:  # 有错误
                logger.error(f"搜索失败 {music_file.name}: {search_result[1]}")
                matched_results.append({
                    "file_path": music_file,
                    "file_name": music_file.name,
                    "matched_song": {"name": "匹配失败", "artist": "", "id": None}
                })
                continue

            search_results = search_result[0]
            if not search_results:
                logger.warning(f"未找到匹配的音乐: {music_file.name}")
                matched_results.append({
                    "file_path": music_file,
                    "file_name": music_file.name,
                    "matched_song": {"name": "未找到匹配", "artist": "", "id": None}
                })
                continue

            # 找到最佳匹配
            best_match = find_best_match(search_results, music_file.name, match_artist)
            if not best_match:
                logger.warning(f"未找到最佳匹配: {music_file.name}")
                matched_results.append({
                    "file_path": music_file,
                    "file_name": music_file.name,
                    "matched_song": {"name": "未找到匹配", "artist": "", "id": None}
                })
                continue

            logger.info(f"找到匹配: {best_match.get('name', '')} - {best_match.get('artist', '')}")

            matched_results.append({
                "file_path": music_file,
                "file_name": music_file.name,
                "matched_song": best_match
            })

        except Exception as e:
            logger.error(f"匹配文件时出错 {music_file.name}: {str(e)}")
            matched_results.append({
                "file_path": music_file,
                "file_name": music_file.name,
                "matched_song": {"name": "匹配失败", "artist": "", "id": None}
            })

    logger.info(f"匹配完成! 总计: {len(music_files)}")
    return matched_results


