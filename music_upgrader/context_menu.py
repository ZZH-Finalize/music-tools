#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右键菜单模块
处理音乐文件列表的右键菜单功能
"""

import tkinter as tk
from tkinter import messagebox
import threading
from typing import Optional

from status_manager import MusicStatus, MusicStateManager
from music_upgrader_core_async import clean_filename, logger, AsyncRateLimitedGDAPIClient
from manual_match_window import create_manual_match_window


class ContextMenuHandler:
    def __init__(self, app):
        self.app = app  # 主应用实例

    def show_context_menu(self, event):
        """显示右键菜单"""
        # 获取点击位置的项
        item = self.app.tree.identify_row(event.y)
        if item:
            # 选中该项
            self.app.tree.selection_set(item)

            # 获取项索引
            items = self.app.tree.get_children()
            index = items.index(item)

            # 获取当前状态
            current_status = self.app.status_manager.get_status(index) if self.app.status_manager else None

            # 创建右键菜单
            context_menu = tk.Menu(self.app.root, tearoff=0)

            # 根据当前状态添加可用的菜单项
            if current_status == MusicStatus.IGNORED:
                # 如果是已忽略状态，只显示取消忽略
                context_menu.add_command(label="取消忽略", command=lambda: self.unignore_item(item))
            else:
                # 根据状态决定是否可以忽略
                if self.app.status_manager and self.app.status_manager.can_ignore(index):
                    context_menu.add_command(label="忽略此项", command=lambda: self.ignore_item(item))

                # 根据状态决定是否可以手动匹配
                if self.app.status_manager and self.app.status_manager.can_manual_match(index):
                    context_menu.add_command(label="手动匹配", command=lambda: self.manual_match(item))

                # 根据状态决定是否可以下载
                if self.app.status_manager and self.app.status_manager.can_download(index):
                    context_menu.add_command(label="下载", command=lambda: self.download_single(item))

            # 显示菜单
            context_menu.post(event.x_root, event.y_root)

    def ignore_item(self, item):
        """忽略指定项"""
        logger.debug("右键菜单-忽略-被点击")
        # 获取项索引
        items = self.app.tree.get_children()
        index = items.index(item)

        # 更新匹配结果为忽略
        self.app.matched_songs[index] = {"name": "已忽略", "artist": "", "id": None}

        # 更新状态为已忽略
        if self.app.status_manager:
            old_status = self.app.status_manager.get_status(index)
            self.app.status_manager.ignore_item(index)
            logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.IGNORED.value}")

        # 更新表格显示
        current_values = self.app.tree.item(item, 'values')
        self.app.tree.item(item, values=(current_values[0], "", MusicStatus.IGNORED.value))  # 忽略时第二列显示空白

        logger.info(f"已忽略项: {current_values[0]}")

    def unignore_item(self, item):
        """取消忽略指定项，恢复到原始匹配状态"""
        logger.debug("右键菜单-取消忽略-被点击")
        # 获取项索引
        items = self.app.tree.get_children()
        index = items.index(item)

        # 更新状态为已取消忽略
        if self.app.status_manager:
            old_status = self.app.status_manager.get_status(index)
            self.app.status_manager.unignore_item(index)
            new_status = self.app.status_manager.get_status(index)
            logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {new_status.value if new_status else 'None'}")

        # 检查是否有原始匹配结果
        if (index < len(self.app.original_matched_songs) and
            self.app.original_matched_songs[index] is not None):
            # 恢复原始匹配结果
            original_result = self.app.original_matched_songs[index]
            self.app.matched_songs[index] = original_result

            # 更新表格显示
            if original_result and isinstance(original_result, dict):
                display_text = f"{original_result.get('name', '未知')} - {original_result.get('artist', ['未知'])[0] if isinstance(original_result.get('artist'), list) and original_result.get('artist') else original_result.get('artist', '未知')}"
                # 更新状态文本
                if self.app.status_manager:
                    original_status = self.app.status_manager.get_status(index)
                    if original_status:
                        self.app.root.after(0, lambda idx=index, text=display_text, st=original_status.value: self.app.update_table_item(idx, text, st))
                    else:
                        self.app.root.after(0, lambda idx=index, text=display_text: self.app.update_table_item(idx, text))
                else:
                    self.app.root.after(0, lambda idx=index, text=display_text: self.app.update_table_item(idx, text))
            else:
                self.app.root.after(0, lambda idx=index: self.app.update_table_item(idx, "未知"))
        else:
            # 如果没有原始匹配结果，则重新匹配
            original_filename = self.app.music_files[index].name

            # 清理文件名以用于搜索
            search_keyword = clean_filename(original_filename)
            # 将&替换为英文逗号
            search_keyword = search_keyword.replace('&', ',')
            logger.debug(f"重新匹配关键词: {search_keyword}")

            # 在新线程中重新匹配该文件
            matching_thread = threading.Thread(target=self.rematch_single_file, args=(index, search_keyword))
            matching_thread.daemon = True
            matching_thread.start()

        logger.info(f"已取消忽略项: {self.app.music_files[index].name}")

    def manual_match(self, item):
        """手动匹配指定项"""
        logger.debug("右键菜单-手动匹配-被点击")
        # 获取项索引
        items = self.app.tree.get_children()
        index = items.index(item)

        # 检查当前项是否被忽略，如果是则不允许手动匹配
        if self.app.status_manager and self.app.status_manager.get_status(index) == MusicStatus.IGNORED:
            logger.warning(f"无法手动匹配已忽略的文件: {self.app.music_files[index].name}")
            messagebox.showwarning("警告", "无法对已忽略的项目进行手动匹配，请先取消忽略")
            return

        # 获取原始文件名
        original_filename = self.app.music_files[index].name

        # 创建手动匹配窗口
        create_manual_match_window(self.app, index, original_filename)

    def download_single(self, item):
        """下载单个歌曲"""
        logger.debug("右键菜单-下载-被点击")
        # 获取项索引
        items = self.app.tree.get_children()
        index = items.index(item)

        # 检查当前项是否被忽略，如果是则不允许下载
        if self.app.status_manager and self.app.status_manager.get_status(index) == MusicStatus.IGNORED:
            logger.warning(f"无法下载已忽略的文件: {self.app.music_files[index].name}")
            messagebox.showwarning("警告", "无法下载已忽略的项目")
            return

        # 检查是否有匹配结果
        matched_song = self.app.matched_songs[index]
        # 检查matched_song是否为字典且有id字段
        if not matched_song or not isinstance(matched_song, dict) or not matched_song.get('id'):
            logger.warning(f"文件 {self.app.music_files[index].name} 没有匹配结果，无法下载")
            messagebox.showwarning("警告", "该项目没有匹配结果，无法下载")
            return

        # 确认是否下载
        filename = self.app.music_files[index].name
        if not messagebox.askyesno("确认", f"确定要下载 {filename} 吗？"):
            return

        # 在新线程中执行下载
        from downloader import download_single_async_threaded
        download_thread = threading.Thread(target=download_single_async_threaded, args=(self.app, index))
        download_thread.daemon = True
        download_thread.start()

    def rematch_single_file(self, index, search_keyword):
        """在后台线程中重新匹配单个文件"""
        # 创建新的事件循环
        import asyncio
        import threading

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self._rematch_single_file_async(index, search_keyword))
        finally:
            loop.close()

    async def _rematch_single_file_async(self, index, search_keyword):
        """异步重新匹配单个文件"""
        # 检查当前项是否被忽略，如果是则跳过匹配
        if self.app.status_manager and self.app.status_manager.get_status(index) == MusicStatus.IGNORED:
            logger.info(f"跳过已忽略的文件: {self.app.music_files[index].name}")
            return

        # 自动滚动到当前项
        self.app.root.after(0, lambda idx=index: self.app.scroll_to_item(idx))

        try:
            # 检查当前是否已有匹配结果，如果有且匹配成功，则跳过本次匹配
            existing_match = self.app.matched_songs[index]
            if existing_match and existing_match.get('id'):
                # 如果已有匹配结果且匹配成功，则跳过本次匹配，保持原有匹配信息
                logger.info(f"文件 {self.app.music_files[index].name} 已有匹配结果，跳过本次匹配")
                # 更新状态，但保持原有匹配信息
                if self.app.status_manager:
                    old_status = self.app.status_manager.get_status(index)
                    self.app.status_manager.set_status(index, MusicStatus.AUTO_MATCHED)
                    logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.AUTO_MATCHED.value}")
                    status_text = MusicStatus.AUTO_MATCHED.value
                else:
                    status_text = "未知状态"

                # 显示原有的匹配信息
                display_text = f"{existing_match.get('name', '未知')} - {existing_match.get('artist', ['未知'])[0] if isinstance(existing_match.get('artist'), list) else existing_match.get('artist', '未知')}"
                self.app.root.after(0, lambda idx=index, text=display_text, st=status_text: self.app.update_table_item(idx, text, st))
                return

            # 异步搜索音乐
            async with AsyncRateLimitedGDAPIClient() as client:
                search_results = await client.search(search_keyword, source=self.app.music_source_var.get(), count=5)

            if not search_results:
                matched_song = {"name": "未找到匹配", "artist": "", "id": None}
            else:
                # 直用搜索结果的第一项作为匹配结果
                matched_song = search_results[0]

            # 只有在没有已有匹配结果或已有匹配结果失败时才更新匹配结果
            # 如果新的匹配失败，但已有匹配成功，则保持原有匹配结果
            if matched_song and matched_song.get('id'):
                # 新匹配成功，更新匹配结果
                self.app.matched_songs[index] = matched_song
                # 同时保存到原始匹配结果列表
                self.app.original_matched_songs[index] = matched_song
                # 更新状态
                if self.app.status_manager:
                    old_status = self.app.status_manager.get_status(index)
                    self.app.status_manager.set_status(index, MusicStatus.AUTO_MATCHED)
                    logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.AUTO_MATCHED.value}")
                    status_text = MusicStatus.AUTO_MATCHED.value
                else:
                    # 如果状态管理器不存在，使用默认值
                    status_text = "未知状态"
            else:
                # 新匹配失败，但如果已有匹配成功，则保持原有匹配结果
                if existing_match and existing_match.get('id'):
                    # 保持原有匹配结果，但更新状态
                    if self.app.status_manager:
                        old_status = self.app.status_manager.get_status(index)
                        self.app.status_manager.set_status(index, MusicStatus.AUTO_MATCHED)
                        logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.AUTO_MATCHED.value}")
                        status_text = MusicStatus.AUTO_MATCHED.value
                    else:
                        status_text = "未知状态"
                else:
                    # 确实没有匹配结果，更新为失败
                    self.app.matched_songs[index] = matched_song
                    # 同时保存到原始匹配结果列表
                    self.app.original_matched_songs[index] = matched_song
                    # 更新状态
                    if self.app.status_manager:
                        old_status = self.app.status_manager.get_status(index)
                        self.app.status_manager.set_status(index, MusicStatus.MATCH_FAIL)
                        logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.MATCH_FAIL.value}")
                        status_text = MusicStatus.MATCH_FAIL.value
                    else:
                        # 如果状态管理器不存在，使用默认值
                        status_text = "未知状态"

            # 更新表格显示 - 第二列只显示音乐匹配信息
            current_match = self.app.matched_songs[index] if self.app.matched_songs[index] else matched_song
            if current_match and current_match.get('id'):
                display_text = f"{current_match.get('name', '未知')} - {current_match.get('artist', ['未知'])[0] if isinstance(current_match.get('artist'), list) else current_match.get('artist', '未知')}"
            else:
                display_text = ""  # 没有匹配结果时显示空白
            self.app.root.after(0, lambda idx=index, text=display_text, st=status_text: self.app.update_table_item(idx, text, st))

            logger.info(f"重新匹配完成: {self.app.music_files[index].name}")
        except Exception as e:
            logger.error(f"重新匹配文件时出错 {self.app.music_files[index].name}: {str(e)}")
            matched_song = {"name": "匹配失败", "artist": "", "id": None}

            # 检查当前是否已有匹配结果，如果有且匹配成功，则不改变已有匹配信息
            existing_match = self.app.matched_songs[index]
            if existing_match and existing_match.get('id'):
                # 保持原有匹配结果
                logger.info(f"文件 {self.app.music_files[index].name} 已有匹配结果，保持原有匹配信息")
                # 更新状态，但保持原有匹配信息
                if self.app.status_manager:
                    old_status = self.app.status_manager.get_status(index)
                    self.app.status_manager.set_status(index, MusicStatus.AUTO_MATCHED)
                    logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.AUTO_MATCHED.value}")

                # 显示原有的匹配信息
                display_text = f"{existing_match.get('name', '未知')} - {existing_match.get('artist', ['未知'])[0] if isinstance(existing_match.get('artist'), list) else existing_match.get('artist', '未知')}"
                self.app.root.after(0, lambda idx=index, text=display_text: self.app.update_table_item(idx, text, MusicStatus.AUTO_MATCHED.value))
            else:
                # 没有原有匹配结果或原有匹配失败，更新为失败
                self.app.matched_songs[index] = matched_song
                # 同时保存到原始匹配结果列表
                self.app.original_matched_songs[index] = matched_song

                # 更新状态为匹配失败
                if self.app.status_manager:
                    old_status = self.app.status_manager.get_status(index)
                    self.app.status_manager.set_status(index, MusicStatus.MATCH_FAIL)
                    logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.MATCH_FAIL.value}")

                display_text = ""  # 匹配失败时显示空白
                self.app.root.after(0, lambda idx=index, text=display_text: self.app.update_table_item(idx, text, MusicStatus.MATCH_FAIL.value))
