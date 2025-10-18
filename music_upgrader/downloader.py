#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载功能模块
处理音乐文件的下载功能
"""

import asyncio
import threading
from tkinter import messagebox

from music_upgrader_core_async import AsyncRateLimitedGDAPIClient, download_lossless_music_async, logger, clean_filename
from status_manager import MusicStatus


def download_single_async_threaded(app, index):
    """在独立线程中运行异步下载"""
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(download_single_async(app, index))
    finally:
        loop.close()


async def download_single_async(app, index):
    """异步下载单个歌曲"""
    try:
        music_file = app.music_files[index]
        matched_song = app.matched_songs[index]

        # 显示当前处理的文件
        app.root.after(0, lambda f=music_file.name: app.update_status(f"正在下载: {f}"))

        if matched_song and matched_song.get('id'):
            # 获取输出目录
            output_dir = app.output_var.get() or None

            # 异步下载无损音乐
            async with AsyncRateLimitedGDAPIClient() as client:
                download_path = await download_lossless_music_async(
                    client,
                    matched_song['id'],
                    app.music_source_var.get(),
                    music_file,
                    output_dir
                )

            if download_path:
                logger.info(f"成功下载: {music_file.name}")
                # 更新状态为已下载(手动) - 因为这是通过右键菜单手动下载的
                if app.status_manager:
                    old_status = app.status_manager.get_status(index)
                    app.status_manager.set_status(index, MusicStatus.MANUAL_DOWNLOAD_COMPLETE)
                    logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.MANUAL_DOWNLOAD_COMPLETE.value}")
                # 下载完成后，第二列保持不变，只更新状态
                app.root.after(0, lambda idx=index: app.update_table_item(idx, None, MusicStatus.MANUAL_DOWNLOAD_COMPLETE.value))
                app.root.after(0, lambda: messagebox.showinfo("成功", f"成功下载: {music_file.name}"))
            else:
                logger.warning(f"下载失败: {music_file.name}")
                # 更新状态为下载失败
                if app.status_manager:
                    old_status = app.status_manager.get_status(index)
                    app.status_manager.set_status(index, MusicStatus.DOWNLOAD_FAIL)
                    logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.DOWNLOAD_FAIL.value}")
                # 下载失败时，第二列保持不变，只更新状态
                app.root.after(0, lambda idx=index: app.update_table_item(idx, None, MusicStatus.DOWNLOAD_FAIL.value))
                app.root.after(0, lambda: messagebox.showwarning("失败", f"下载失败: {music_file.name}"))
        else:
            logger.warning(f"没有匹配结果: {music_file.name}")
            app.root.after(0, lambda: messagebox.showwarning("警告", f"没有匹配结果: {music_file.name}"))

    except Exception as e:
        logger.error(f"下载过程中出错: {str(e)}")
        app.root.after(0, lambda: messagebox.showerror("错误", f"下载过程中出错: {str(e)}"))


async def upgrade_files_async(app):
    """异步升级文件"""
    success_count = 0
    fail_count = 0

    for i, (music_file, matched_song) in enumerate(zip(app.music_files, app.matched_songs)):
        # 检查是否需要取消升级
        if app.cancel_upgrading:
            logger.info("升级被用户取消")
            app.root.after(0, app.cancel_upgrading_process)
            return

        # 检查状态管理器是否存在以及当前项是否处于可下载状态
        can_download = True
        if app.status_manager:
            current_status = app.status_manager.get_status(i)
            # 只处理AUTO_MATCHED或MANUAL_MATCHED状态的文件，且不能是已忽略的
            if current_status not in [MusicStatus.AUTO_MATCHED, MusicStatus.MANUAL_MATCHED] or current_status == MusicStatus.IGNORED:
                can_download = False

        # 更新进度
        progress = (i / len(app.music_files)) * 100
        app.root.after(0, lambda p=progress: app.progress_var.set(p))

        # 显示当前处理的文件
        app.root.after(0, lambda f=music_file.name: app.update_status(f"正在升级: {f}"))

        # 自动滚动到当前项
        app.root.after(0, lambda idx=i: app.scroll_to_item(idx))

        if can_download and matched_song and matched_song.get('id'):
            try:
                # 获取输出目录
                output_dir = app.output_var.get() or None

                # 异步下载无损音乐
                async with AsyncRateLimitedGDAPIClient() as client:
                    download_path = await download_lossless_music_async(
                        client,
                        matched_song['id'],
                        app.music_source_var.get(),
                        music_file,
                        output_dir
                    )

                if download_path:
                    success_count += 1
                    logger.info(f"成功升级: {music_file.name}")
                    # 更新状态为已下载(自动) - 因为这是通过自动升级下载的
                    if app.status_manager:
                        old_status = app.status_manager.get_status(i)
                        app.status_manager.set_status(i, MusicStatus.AUTO_DOWNLOAD_COMPLETE)
                        logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.AUTO_DOWNLOAD_COMPLETE.value}")
                    # 下载完成后，第二列保持不变，只更新状态
                    app.root.after(0, lambda idx=i: app.update_table_item(idx, None, MusicStatus.AUTO_DOWNLOAD_COMPLETE.value))
                else:
                    fail_count += 1
                    logger.warning(f"升级失败: {music_file.name}")
                    # 更新状态为下载失败
                    if app.status_manager:
                        old_status = app.status_manager.get_status(i)
                        app.status_manager.set_status(i, MusicStatus.DOWNLOAD_FAIL)
                        logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.DOWNLOAD_FAIL.value}")
                    # 下载失败时，第二列保持不变，只更新状态
                    app.root.after(0, lambda idx=i: app.update_table_item(idx, None, MusicStatus.DOWNLOAD_FAIL.value))
            except Exception as e:
                fail_count += 1
                logger.error(f"升级文件失败 {music_file.name}: {str(e)}")
                # 更新状态为下载失败
                if app.status_manager:
                    old_status = app.status_manager.get_status(i)
                    app.status_manager.set_status(i, MusicStatus.DOWNLOAD_FAIL)
                    logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.DOWNLOAD_FAIL.value}")
                # 下载失败时，第二列保持不变，只更新状态
                app.root.after(0, lambda idx=i: app.update_table_item(idx, None, MusicStatus.DOWNLOAD_FAIL.value))
        else:
            # 如果文件状态不是可下载的，跳过
            if app.status_manager and app.status_manager.get_status(i) not in [MusicStatus.AUTO_MATCHED, MusicStatus.MANUAL_MATCHED]:
                logger.info(f"跳过文件（状态不可下载）: {music_file.name}")
            else:
                fail_count += 1
                logger.warning(f"没有匹配结果: {music_file.name}")

    # 所有文件处理完成
    app.is_upgrading = False  # 升级完成，重置标志
    app.root.after(0, lambda: app.upgrade_complete(success_count, fail_count))


async def match_files_async(app):
    """异步匹配文件"""
    for index, music_file in enumerate(app.music_files):
        # 检查是否需要取消匹配
        if app.cancel_matching:
            logger.info("匹配被用户取消")
            app.root.after(0, app.cancel_matching_process)
            return

        # 检查当前项是否被忽略，如果是则跳过匹配
        if app.status_manager and app.status_manager.get_status(index) == MusicStatus.IGNORED:
            logger.info(f"跳过已忽略的文件: {music_file.name}")
            # 即使跳过此文件，也要更新进度，确保进度条正确
            progress = (index / len(app.music_files)) * 10
            app.root.after(0, lambda p=progress: app.progress_var.set(p))
            continue

        # 更新进度
        progress = (index / len(app.music_files)) * 10
        app.root.after(0, lambda p=progress: app.progress_var.set(p))

        # 显示当前处理的文件
        app.root.after(0, lambda f=music_file.name: app.update_status(f"正在匹配: {f}"))

        # 自动滚动到当前项
        app.root.after(0, lambda idx=index: app.scroll_to_item(idx))

        try:
            # 检查当前是否已有匹配结果，如果有且匹配成功，则跳过本次匹配
            existing_match = app.matched_songs[index]
            if existing_match and existing_match.get('id'):
                # 如果已有匹配结果且匹配成功，则跳过本次匹配，保持原有匹配信息
                logger.info(f"文件 {music_file.name} 已有匹配结果，跳过本次匹配")
                # 更新状态，但保持原有匹配信息
                if app.status_manager:
                    old_status = app.status_manager.get_status(index)
                    app.status_manager.set_status(index, MusicStatus.AUTO_MATCHED)
                    logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.AUTO_MATCHED.value}")
                    status_text = MusicStatus.AUTO_MATCHED.value
                else:
                    status_text = "未知状态"

                # 显示原有的匹配信息
                display_text = f"{existing_match.get('name', '未知')} - {existing_match.get('artist', ['未知'])[0] if isinstance(existing_match.get('artist'), list) else existing_match.get('artist', '未知')}"
                app.root.after(0, lambda idx=index, text=display_text, st=status_text: app.update_table_item(idx, text, st))
                continue

            # 清理文件名以用于搜索
            search_keyword = clean_filename(music_file.name)
            # 将&替换为英文逗号
            search_keyword = search_keyword.replace('&', ',')
            logger.debug(f"搜索关键词: {search_keyword}")

            # 异步搜索音乐
            async with AsyncRateLimitedGDAPIClient() as client:
                search_results = await client.search(search_keyword, source=app.music_source_var.get(), count=5)

            if not search_results:
                matched_song = {"name": "未找到匹配", "artist": "", "id": None}
            else:
                # 直接使用搜索结果的第一项作为匹配结果
                matched_song = search_results[0]

            # 只有在没有已有匹配结果或已有匹配结果失败时才更新匹配结果
            # 如果新的匹配失败，但已有匹配成功，则保持原有匹配结果
            if matched_song and matched_song.get('id'):
                # 新匹配成功，更新匹配结果
                app.matched_songs[index] = matched_song
                # 同时保存到原始匹配结果列表
                app.original_matched_songs[index] = matched_song
                # 更新状态
                if app.status_manager:
                    old_status = app.status_manager.get_status(index)
                    app.status_manager.set_status(index, MusicStatus.AUTO_MATCHED)
                    logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.AUTO_MATCHED.value}")
                    status_text = MusicStatus.AUTO_MATCHED.value
                else:
                    # 如果状态管理器不存在，使用默认值
                    status_text = "未知状态"
            else:
                # 新匹配失败，但如果已有匹配成功，则保持原有匹配结果
                if existing_match and existing_match.get('id'):
                    # 保持原有匹配结果，但更新状态
                    if app.status_manager:
                        old_status = app.status_manager.get_status(index)
                        app.status_manager.set_status(index, MusicStatus.AUTO_MATCHED)
                        logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.AUTO_MATCHED.value}")
                        status_text = MusicStatus.AUTO_MATCHED.value
                    else:
                        status_text = "未知状态"
                else:
                    # 确实没有匹配结果，更新为失败
                    app.matched_songs[index] = matched_song
                    # 同时保存到原始匹配结果列表
                    app.original_matched_songs[index] = matched_song
                    # 更新状态
                    if app.status_manager:
                        old_status = app.status_manager.get_status(index)
                        app.status_manager.set_status(index, MusicStatus.MATCH_FAIL)
                        logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.MATCH_FAIL.value}")
                        status_text = MusicStatus.MATCH_FAIL.value
                    else:
                        # 如果状态管理器不存在，使用默认值
                        status_text = "未知状态"

            # 更新表格显示 - 第二列只显示音乐匹配信息
            current_match = app.matched_songs[index] if app.matched_songs[index] else matched_song
            if current_match and current_match.get('id'):
                display_text = f"{current_match.get('name', '未知')} - {current_match.get('artist', ['未知'])[0] if isinstance(current_match.get('artist'), list) else current_match.get('artist', '未知')}"
            else:
                display_text = ""  # 没有匹配结果时显示空白
            app.root.after(0, lambda idx=index, text=display_text, st=status_text: app.update_table_item(idx, text, st))

        except Exception as e:
            logger.error(f"匹配文件时出错 {music_file.name}: {str(e)}")
            matched_song = {"name": "匹配失败", "artist": "", "id": None}

            # 检查当前是否已有匹配结果，如果有且匹配成功，则不改变已有匹配信息
            existing_match = app.matched_songs[index]
            if existing_match and existing_match.get('id'):
                # 保持原有匹配结果
                logger.info(f"文件 {music_file.name} 已有匹配结果，保持原有匹配信息")
                # 更新状态，但保持原有匹配信息
                if app.status_manager:
                    old_status = app.status_manager.get_status(index)
                    app.status_manager.set_status(index, MusicStatus.AUTO_MATCHED)
                    logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.AUTO_MATCHED.value}")

                # 显示原有的匹配信息
                display_text = f"{existing_match.get('name', '未知')} - {existing_match.get('artist', ['未知'])[0] if isinstance(existing_match.get('artist'), list) else existing_match.get('artist', '未知')}"
                app.root.after(0, lambda idx=index, text=display_text: app.update_table_item(idx, text, MusicStatus.AUTO_MATCHED.value))
            else:
                # 没有原有匹配结果或原有匹配失败，更新为失败
                app.matched_songs[index] = matched_song
                # 同时保存到原始匹配结果列表
                app.original_matched_songs[index] = matched_song

                # 更新状态为匹配失败
                if app.status_manager:
                    old_status = app.status_manager.get_status(index)
                    app.status_manager.set_status(index, MusicStatus.MATCH_FAIL)
                    logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.MATCH_FAIL.value}")

                display_text = ""  # 匹配失败时显示空白
                app.root.after(0, lambda idx=index, text=display_text: app.update_table_item(idx, text, MusicStatus.MATCH_FAIL.value))

    # 所有文件处理完成
    app.root.after(0, app.matching_complete)
