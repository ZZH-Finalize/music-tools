#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音乐升级核心库 - 异步版本 (asyncio)
包含音乐文件扫描、匹配、下载等核心功能，所有API调用均为异步
"""

import os
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable, Awaitable
from urllib.parse import unquote, urlparse
from async_gd_api import AsyncRateLimitedGDAPIClient
import logging
import time
from collections import deque
from difflib import SequenceMatcher
import asyncio
import aiohttp


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    现在将歌曲名和歌手名合并成一个字符串进行相似度匹配
    """
    if not search_results:
        return None

    original_name = clean_filename(original_filename).lower()

    # 尝试从原始文件名中分离出歌手和歌曲名（通常格式为"歌手 - 歌曲名"）
    import re
    parts = re.split(r'[-_~]+', original_name)
    if len(parts) >= 2:
        original_artist = parts[0].strip()
        original_song = parts[1].strip()
        # 合并歌手和歌曲名为一个字符串
        original_combined = f"{original_artist} {original_song}".strip()
    else:
        # 如果无法分离，将整个名称作为搜索字符串
        original_combined = original_name.strip()

    best_match = None
    best_score = -1  # 最高相似度得分

    for result in search_results:
        song_name = result.get('name', '').lower()
        artist = ' '.join(result.get('artist', [])).lower() if isinstance(result.get('artist'), list) else result.get('artist', '').lower()

        # 合并搜索结果中的歌手和歌曲名为一个字符串
        combined_result = f"{artist} {song_name}".strip() if artist else song_name

        # 计算合并字符串的相似度
        combined_similarity = SequenceMatcher(None, original_combined, combined_result).ratio()

        # 如果当前结果的相似度得分更高，则更新最佳匹配
        if combined_similarity > best_score:
            best_score = combined_similarity
            best_match = result

    return best_match


async def download_lossless_music_async(
    client: AsyncRateLimitedGDAPIClient,
    track_id: str,
    source: str,
    original_file_path: Path,
    output_dir: Optional[str] = None,
) -> Optional[str]:
    """
    异步下载无损音质音乐
    """
    try:
        # 尝试下载最高音质（999代表最高音质，通常为无损）
        song_info = None
        download_url = None

        # 先尝试999音质
        try:
            song_info = await client.get_song_url(track_id, source=source, br=999)
            if song_info and 'url' in song_info:
                download_url = song_info.get('url')
        except Exception:
            pass

        # 如果999音质没有可用链接，尝试740（另一个无损选项）
        if not download_url:
            try:
                song_info = await client.get_song_url(track_id, source=source, br=740)
                if song_info and 'url' in song_info:
                    download_url = song_info.get('url')
            except Exception:
                pass

        # 如果还是没有，尝试320
        if not download_url:
            try:
                song_info = await client.get_song_url(track_id, source=source, br=320)
                if song_info and 'url' in song_info:
                    download_url = song_info.get('url')
            except Exception:
                pass

        if not download_url:
            logger.warning(f"无法获取歌曲下载链接: {original_file_path.name}")
            return None
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

            # 创建新的会话用于下载
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    response.raise_for_status()

                    # 保存文件
                    with open(download_file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)

            logger.info(f"下载完成: {download_file_path}")
            return str(download_file_path)

    except Exception as e:
        logger.error(f"下载失败 {original_file_path.name}: {str(e)}")
        return None


async def upgrade_music_files_async(
    directory: str,
    source: str = "netease",
    quality: int = 99,
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
    logger.info(f"开始扫描目录: {directory}")

    # 扫描音乐文件
    music_files = scan_music_files(directory)
    logger.info(f"找到 {len(music_files)} 个音乐文件")

    if not music_files:
        logger.warning("没有找到需要升级的音乐文件")
        if completion_callback:
            await completion_callback(0, 0, len(music_files))
        return

    # 创建带速率限制的API客户端
    client = AsyncRateLimitedGDAPIClient(retries=retries, timeout=timeout)

    success_count = 0
    fail_count = 0

    async with client:
        for idx, music_file in enumerate(music_files, 1):
            logger.info(f"[{idx}/{len(music_files)}] 处理文件: {music_file.name}")

            # 更新进度
            if progress_callback:
                await progress_callback(idx, len(music_files))

            try:
                # 清理文件名以用于搜索
                search_keyword = clean_filename(music_file.name)
                # 将&替换为英文逗号
                search_keyword = search_keyword.replace('&', ',')
                logger.debug(f"搜索关键词: {search_keyword}")

                # 异步搜索音乐
                search_results = await client.search(search_keyword, source=source, count=5)

                if not search_results:
                    logger.warning(f"未找到匹配的音乐: {music_file.name}")
                    fail_count += 1
                    continue

                # 找到最佳匹配
                best_match = find_best_match(search_results, music_file.name, match_artist)
                if not best_match:
                    logger.warning(f"未找到最佳匹配: {music_file.name}")
                    fail_count += 1
                    continue

                logger.info(f"找到匹配: {best_match.get('name', '')} - {best_match.get('artist', '')}")

                # 获取曲目ID
                track_id = best_match.get('id')
                if not track_id:
                    logger.warning(f"无法获取曲目ID: {music_file.name}")
                    fail_count += 1
                    continue

                # 异步下载无损音乐
                download_result = await download_lossless_music_async(
                    client,
                    track_id,
                    source,
                    music_file,
                    output_dir
                )

                if download_result:
                    success_count += 1
                else:
                    fail_count += 1

            except Exception as e:
                logger.error(f"处理文件时出错 {music_file.name}: {str(e)}")
                fail_count += 1

    logger.info(f"处理完成!")
    logger.info(f"成功: {success_count}, 失败: {fail_count}, 总计: {len(music_files)}")

    if completion_callback:
        await completion_callback(success_count, fail_count, len(music_files))


async def match_music_files_async(
    directory: str,
    source: str = "netease",
    match_artist: bool = False,
    retries: int = 3,
    timeout: int = 30,
    progress_callback: Optional[Callable] = None,
    completion_callback: Optional[Callable] = None
) -> List[Dict[str, Any]]:
    """
    异步匹配目录下的音乐文件，返回匹配结果列表
    """
    logger.info(f"开始扫描目录: {directory}")

    # 扫描音乐文件
    music_files = scan_music_files(directory)
    logger.info(f"找到 {len(music_files)} 个音乐文件")

    if not music_files:
        logger.warning("没有找到需要匹配的音乐文件")
        if completion_callback:
            await completion_callback([])
        return []

    # 创建带速率限制的API客户端
    client = AsyncRateLimitedGDAPIClient(retries=retries, timeout=timeout)

    matched_results = []

    async with client:
        for idx, music_file in enumerate(music_files, 1):
            logger.info(f"[{idx}/{len(music_files)}] 匹配文件: {music_file.name}")

            # 更新进度
            if progress_callback:
                await progress_callback(idx, len(music_files))

            try:
                # 清理文件名以用于搜索
                search_keyword = clean_filename(music_file.name)
                # 将&替换为英文逗号
                search_keyword = search_keyword.replace('&', ',')
                logger.debug(f"搜索关键词: {search_keyword}")

                # 异步搜索音乐
                search_results = await client.search(search_keyword, source=source, count=5)

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
        await completion_callback(matched_results)

    return matched_results


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
    async def run_async():
        await upgrade_music_files_async(directory, source, quality, output_dir, match_artist, retries, timeout)

    asyncio.run(run_async())


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
    async def run_async():
        return await match_music_files_async(directory, source, match_artist, retries, timeout)

    return asyncio.run(run_async())
