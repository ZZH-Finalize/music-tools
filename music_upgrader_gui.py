#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI音乐升级工具 (asyncio版)
功能：读取指定目录下的音乐文件（跳过flac无损格式），使用文件名调用GD API搜索同歌曲，并显示匹配结果，
用户确认后下载无损格式到本地
"""

import os
import sys
import threading
import asyncio
from typing import List, Optional, Dict, Any
from tkinter import ttk
import tkinter as tk
from tkinter import filedialog, messagebox
import concurrent.futures
from enum import Enum

# 导入异步核心模块（包含所有功能）
from music_upgrader_core_async import (
    AsyncRateLimitedGDAPIClient,
    download_lossless_music_async,
    upgrade_music_files_async,
    match_music_files_async,
    clean_filename,
    is_music_file,
    scan_music_files,
    find_best_match,
    match_music_files,
    logger
)

from typing import Dict, Any

# 定义状态枚举
class MusicStatus(Enum):
    MATCH_PENDING = "等待匹配"      # 等待匹配
    AUTO_MATCHED = "匹配(自动)"     # 匹配(自动)
    MANUAL_MATCHED = "匹配(手动)"   # 匹配(手动)
    MATCH_FAIL = "匹配失败"        # 匹配失败
    AUTO_DOWNLOAD_COMPLETE = "已下载(自动)"  # 已下载(自动)
    MANUAL_DOWNLOAD_COMPLETE = "已下载(手动)"  # 已下载(手动)
    DOWNLOAD_FAIL = "下载失败"     # 下载失败
    IGNORED = "已忽略"             # 已忽略

# 状态机管理类
class MusicStateManager:
    def __init__(self, num_items: int):
        # 当前状态列表
        self.status_list = [MusicStatus.MATCH_PENDING for _ in range(num_items)]
        # 保存被忽略前的状态列表，使用Optional[MusicStatus]类型
        self.ignored_status_backup = [None for _ in range(num_items)]  # type: List[Optional[MusicStatus]]

    def get_status(self, index: int) -> Optional[MusicStatus]:
        """获取指定索引的状态"""
        if 0 <= index < len(self.status_list):
            return self.status_list[index]
        return None

    def set_status(self, index: int, status: MusicStatus) -> bool:
        """设置指定索引的状态"""
        if 0 <= index < len(self.status_list):
            self.status_list[index] = status
            return True
        return False

    def ignore_item(self, index: int) -> bool:
        """忽略指定项"""
        if 0 <= index < len(self.status_list):
            # 保存当前状态
            self.ignored_status_backup[index] = self.status_list[index]
            # 设置为已忽略状态
            self.status_list[index] = MusicStatus.IGNORED
            return True
        return False

    def unignore_item(self, index: int) -> bool:
        """取消忽略指定项，恢复到之前的状态"""
        if 0 <= index < len(self.status_list) and self.ignored_status_backup[index] is not None:
            # 恢复到之前的状态
            previous_status = self.ignored_status_backup[index]
            if previous_status is not None:
                self.status_list[index] = previous_status
            # 清空备份状态
            self.ignored_status_backup[index] = None
            return True
        return False

    def can_ignore(self, index: int) -> bool:
        """检查是否可以忽略指定项"""
        if 0 <= index < len(self.status_list):
            current_status = self.status_list[index]
            # 任何状态都可以被忽略
            return True
        return False

    def can_manual_match(self, index: int) -> bool:
        """检查是否可以手动匹配指定项"""
        if 0 <= index < len(self.status_list):
            current_status = self.status_list[index]
            # 除了已忽略和已下载的状态外，其他状态都可以手动匹配
            return current_status not in [MusicStatus.IGNORED, MusicStatus.AUTO_DOWNLOAD_COMPLETE, MusicStatus.MANUAL_DOWNLOAD_COMPLETE]
        return False

    def can_auto_match(self, index: int) -> bool:
        """检查是否可以自动匹配指定项"""
        if 0 <= index < len(self.status_list):
            current_status = self.status_list[index]
            # 只有等待匹配和匹配失败的状态可以自动匹配
            return current_status in [MusicStatus.MATCH_PENDING, MusicStatus.MATCH_FAIL]
        return False

    def can_download(self, index: int) -> bool:
        """检查是否可以下载指定项"""
        if 0 <= index < len(self.status_list):
            current_status = self.status_list[index]
            # 只有匹配成功的状态可以下载
            return current_status in [MusicStatus.AUTO_MATCHED, MusicStatus.MANUAL_MATCHED]
        return False

    def can_unignore(self, index: int) -> bool:
        """检查是否可以取消忽略指定项"""
        if 0 <= index < len(self.status_list):
            current_status = self.status_list[index]
            # 只有已忽略的状态可以取消忽略
            return current_status == MusicStatus.IGNORED
        return False


class MusicUpgradeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("音乐品质升级工具")
        self.root.geometry("1200x700")  # 增加宽度以容纳新列

        # 初始化变量
        self.directory = ""
        self.music_files = []
        self.matched_songs: List[Optional[Dict[str, Any]]] = []
        self.original_matched_songs: List[Optional[Dict[str, Any]]] = []  # 保存原始匹配结果
        self.client = AsyncRateLimitedGDAPIClient()
        self.status_manager = None  # 状态管理器，将在扫描文件时初始化

        # 用于控制异步任务的事件循环
        self.loop = None
        self.loop_thread = None

        # 日志等级变量
        self.log_level_var = tk.StringVar(value="INFO")
        self.log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        # 创建界面
        self.create_widgets()

    def change_log_level(self, event=None):
        """更改日志等级"""
        import logging
        new_level = self.log_level_var.get()
        logger.setLevel(getattr(logging, new_level))
        logger.info(f"日志等级已更改为: {new_level}")

    def create_widgets(self):
        # 顶部控制区域
        top_control_frame = ttk.Frame(self.root)
        top_control_frame.pack(pady=5, padx=10, fill='x')

        # 日志等级下拉框
        ttk.Label(top_control_frame, text="日志等级:").pack(side='left', padx=(0, 5))
        log_level_combo = ttk.Combobox(top_control_frame, textvariable=self.log_level_var,
                                       values=self.log_levels, state="readonly", width=10)
        log_level_combo.pack(side='left', padx=(0, 10))
        log_level_combo.bind('<<ComboboxSelected>>', self.change_log_level)

        # 路径输入区域
        path_frame = ttk.Frame(self.root)
        path_frame.pack(pady=10, padx=10, fill='x')

        ttk.Label(path_frame, text="参考目录:").pack(side='left')

        self.path_var = tk.StringVar()
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var, width=60)
        path_entry.pack(side='left', padx=(5, 5), fill='x', expand=True)

        browse_btn = ttk.Button(path_frame, text="浏览", command=self.browse_directory)
        browse_btn.pack(side='left', padx=(0, 5))

        self.match_btn = ttk.Button(path_frame, text="自动匹配", command=self.start_matching)
        self.match_btn.pack(side='left', padx=(0, 5))

        # 输出目录输入区域
        output_frame = ttk.Frame(self.root)
        output_frame.pack(pady=5, padx=10, fill='x')

        ttk.Label(output_frame, text="输出目录:").pack(side='left')

        self.output_var = tk.StringVar()
        output_entry = ttk.Entry(output_frame, textvariable=self.output_var, width=60)
        output_entry.pack(side='left', padx=(5, 5), fill='x', expand=True)

        output_browse_btn = ttk.Button(output_frame, text="浏览", command=self.browse_output_directory)
        output_browse_btn.pack(side='left', padx=(0, 5))

        # 创建表格框架
        table_frame = ttk.Frame(self.root)
        table_frame.pack(pady=10, padx=10, fill='both', expand=True)

        # 创建Treeview作为表格控件
        self.tree = ttk.Treeview(table_frame, columns=('original', 'matched', 'status'), show='headings', height=15)
        self.tree.heading('original', text='低音质音乐文件')
        self.tree.heading('matched', text='匹配的音乐文件')
        self.tree.heading('status', text='状态')
        self.tree.column('original', width=400)
        self.tree.column('matched', width=400)
        self.tree.column('status', width=150)

        # 添加滚动条
        tree_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scrollbar.set)

        self.tree.pack(side='left', fill='both', expand=True)
        tree_scrollbar.pack(side='right', fill='y')

        # 底部按钮
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10, padx=10, fill='x')

        self.upgrade_btn = ttk.Button(button_frame, text="开始升级", command=self.start_upgrade, state='disabled')
        self.upgrade_btn.pack(side='right')

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(button_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side='left', fill='x', expand=True, padx=(0, 10))

        # 移除表格选择事件绑定，避免在滚动时弹出信息框
        # self.tree.bind('<<TreeviewSelect>>', self.on_table_select)

    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.directory = directory
            self.path_var.set(directory)
            # 自动设置输出目录为参考目录
            if not self.output_var.get():  # 只有当输出目录为空时才自动填充
                self.output_var.set(directory)

            # 自动扫描音乐文件
            self.auto_scan_files()

    def browse_output_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_var.set(directory)

    def auto_scan_files(self):
        """自动扫描音乐文件，但不执行匹配"""
        if not self.directory:
            logger.warning("请先选择音乐目录")
            messagebox.showwarning("警告", "请先选择音乐目录")
            return

        try:
            self.music_files = scan_music_files(self.directory)
            self.matched_songs = [None] * len(self.music_files) # 初始化匹配列表
            # 初始化状态管理器
            self.status_manager = MusicStateManager(len(self.music_files))

            # 清空表格
            for item in self.tree.get_children():
                self.tree.delete(item)

            # 添加音乐文件到表格
            for file_path in self.music_files:
                self.tree.insert('', 'end', values=(file_path.name, '等待匹配...', MusicStatus.MATCH_PENDING.value))

            # 启用升级按钮
            self.upgrade_btn.config(state='normal')

        except Exception as e:
            logger.error(f"扫描文件失败: {str(e)}")
            messagebox.showerror("错误", f"扫描文件失败: {str(e)}")

    def start_matching(self):
        """在后台线程中开始匹配音乐文件"""
        self.progress_var.set(0)
        self.upgrade_btn.config(state='disabled')

        # 在匹配期间禁用表格控件
        self.disable_table_during_matching()

        # 初始化原始匹配结果列表
        self.original_matched_songs = [None] * len(self.music_files)

        # 在新线程中运行匹配过程
        matching_thread = threading.Thread(target=self.match_files_async_threaded)
        matching_thread.daemon = True
        matching_thread.start()

    def disable_table_during_matching(self):
        """在匹配期间禁用表格控件"""
        self.tree.config(selectmode='none')  # 禁用表格选择，但保留右键菜单功能

    def enable_table_after_matching(self):
        """匹配完成后启用表格控件"""
        self.tree.config(selectmode='browse')  # 启用表格选择
        # 绑定右键菜单事件
        self.tree.bind("<Button-3>", self.show_context_menu)  # 右键点击

    def match_files_async_threaded(self):
        """在独立线程中运行异步匹配过程"""
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.match_files_async())
        finally:
            loop.close()

    async def match_files_async(self):
        """异步匹配文件"""
        for index, music_file in enumerate(self.music_files):
            # 更新进度
            progress = (index / len(self.music_files)) * 10
            self.root.after(0, lambda p=progress: self.progress_var.set(p))

            # 显示当前处理的文件
            self.root.after(0, lambda f=music_file.name: self.update_status(f"正在匹配: {f}"))

            try:
                # 清理文件名以用于搜索
                search_keyword = clean_filename(music_file.name)
                # 将&替换为英文逗号
                search_keyword = search_keyword.replace('&', ',')
                logger.debug(f"搜索关键词: {search_keyword}")

                # 异步搜索音乐
                async with AsyncRateLimitedGDAPIClient() as client:
                    search_results = await client.search(search_keyword, source="netease", count=5)

                if not search_results:
                    matched_song = {"name": "未找到匹配", "artist": "", "id": None}
                else:
                    # 找到最佳匹配
                    best_match = find_best_match(search_results, music_file.name, False)
                    if not best_match:
                        matched_song = {"name": "未找到匹配", "artist": "", "id": None}
                    else:
                        matched_song = best_match

                # 更新匹配结果
                self.matched_songs[index] = matched_song
                # 同时保存到原始匹配结果列表
                self.original_matched_songs[index] = matched_song

                # 更新状态
                if self.status_manager:
                    if matched_song and matched_song.get('id'):
                        # 匹配成功
                        old_status = self.status_manager.get_status(index)
                        self.status_manager.set_status(index, MusicStatus.AUTO_MATCHED)
                        logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.AUTO_MATCHED.value}")
                        status_text = MusicStatus.AUTO_MATCHED.value
                    else:
                        # 匹配失败
                        old_status = self.status_manager.get_status(index)
                        self.status_manager.set_status(index, MusicStatus.MATCH_FAIL)
                        logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.MATCH_FAIL.value}")
                        status_text = MusicStatus.MATCH_FAIL.value
                else:
                    # 如果状态管理器不存在，使用默认值
                    status_text = "未知状态"

                # 更新表格显示
                if matched_song and matched_song.get('id'):
                    display_text = f"{matched_song.get('name', '未知')} - {matched_song.get('artist', ['未知'])[0] if isinstance(matched_song.get('artist'), list) else matched_song.get('artist', '未知')}"
                else:
                    display_text = "未找到匹配" if not matched_song or not matched_song.get('id') else "匹配失败"
                self.root.after(0, lambda idx=index, text=display_text, st=status_text: self.update_table_item(idx, text, st))

            except Exception as e:
                logger.error(f"匹配文件时出错 {music_file.name}: {str(e)}")
                matched_song = {"name": "匹配失败", "artist": "", "id": None}
                self.matched_songs[index] = matched_song
                # 同时保存到原始匹配结果列表
                self.original_matched_songs[index] = matched_song

                # 更新状态为匹配失败
                if self.status_manager:
                    old_status = self.status_manager.get_status(index)
                    self.status_manager.set_status(index, MusicStatus.MATCH_FAIL)
                    logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.MATCH_FAIL.value}")

                display_text = "匹配失败"
                self.root.after(0, lambda idx=index, text=display_text: self.update_table_item(idx, text, MusicStatus.MATCH_FAIL.value))

        # 所有文件处理完成
        self.root.after(0, self.matching_complete)

    def update_table_item(self, index, text, status_text=None):
        """更新表格的指定项"""
        items = self.tree.get_children()
        if index < len(items):
            item_id = items[index]
            current_values = self.tree.item(item_id, 'values')
            if status_text is None:
                # 如果没有提供状态文本，保持当前状态不变
                self.tree.item(item_id, values=(current_values[0], text, current_values[2]))
            else:
                # 同时更新匹配文本和状态
                self.tree.item(item_id, values=(current_values[0], text, status_text))

    def update_status(self, message):
        """更新状态信息"""
        self.root.title(f"音乐品质升级工具 - {message}")

    def matching_complete(self):
        """匹配完成后的处理"""
        self.progress_var.set(10)
        self.upgrade_btn.config(state='normal')
        self.enable_table_after_matching() # 启用表格控件
        self.root.title("音乐品质升级工具")
        messagebox.showinfo("完成", f"匹配完成！找到 {len(self.music_files)} 个音乐文件，其中 {sum(1 for s in self.matched_songs if s and isinstance(s, dict) and s.get('id'))} 个成功匹配。")

    def show_context_menu(self, event):
        """显示右键菜单"""
        # 获取点击位置的项
        item = self.tree.identify_row(event.y)
        if item:
            # 选中该项
            self.tree.selection_set(item)

            # 获取项索引
            items = self.tree.get_children()
            index = items.index(item)

            # 获取当前状态
            current_status = self.status_manager.get_status(index) if self.status_manager else None

            # 创建右键菜单
            context_menu = tk.Menu(self.root, tearoff=0)

            # 根据当前状态添加可用的菜单项
            if current_status == MusicStatus.IGNORED:
                # 如果是已忽略状态，只显示取消忽略
                context_menu.add_command(label="取消忽略", command=lambda: self.unignore_item(item))
            else:
                # 根据状态决定是否可以忽略
                if self.status_manager and self.status_manager.can_ignore(index):
                    context_menu.add_command(label="忽略此项", command=lambda: self.ignore_item(item))

                # 根据状态决定是否可以手动匹配
                if self.status_manager and self.status_manager.can_manual_match(index):
                    context_menu.add_command(label="手动匹配", command=lambda: self.manual_match(item))

                # 根据状态决定是否可以下载
                if self.status_manager and self.status_manager.can_download(index):
                    context_menu.add_command(label="下载", command=lambda: self.download_single(item))

            # 显示菜单
            context_menu.post(event.x_root, event.y_root)

    def ignore_item(self, item):
        """忽略指定项"""
        # 获取项索引
        items = self.tree.get_children()
        index = items.index(item)

        # 更新匹配结果为忽略
        self.matched_songs[index] = {"name": "已忽略", "artist": "", "id": None}

        # 更新状态为已忽略
        if self.status_manager:
            old_status = self.status_manager.get_status(index)
            self.status_manager.ignore_item(index)
            logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.IGNORED.value}")

        # 更新表格显示
        current_values = self.tree.item(item, 'values')
        self.tree.item(item, values=(current_values[0], "已忽略", MusicStatus.IGNORED.value))

        logger.info(f"已忽略项: {current_values[0]}")

    def unignore_item(self, item):
        """取消忽略指定项，恢复到原始匹配状态"""
        # 获取项索引
        items = self.tree.get_children()
        index = items.index(item)

        # 更新状态为已取消忽略
        if self.status_manager:
            old_status = self.status_manager.get_status(index)
            self.status_manager.unignore_item(index)
            new_status = self.status_manager.get_status(index)
            logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {new_status.value if new_status else 'None'}")

        # 检查是否有原始匹配结果
        if (index < len(self.original_matched_songs) and
            self.original_matched_songs[index] is not None):
            # 恢复原始匹配结果
            original_result = self.original_matched_songs[index]
            self.matched_songs[index] = original_result

            # 更新表格显示
            if original_result and isinstance(original_result, dict):
                display_text = f"{original_result.get('name', '未知')} - {original_result.get('artist', ['未知'])[0] if isinstance(original_result.get('artist'), list) and original_result.get('artist') else original_result.get('artist', '未知')}"
                # 更新状态文本
                if self.status_manager:
                    original_status = self.status_manager.get_status(index)
                    if original_status:
                        self.root.after(0, lambda idx=index, text=display_text, st=original_status.value: self.update_table_item(idx, text, st))
                    else:
                        self.root.after(0, lambda idx=index, text=display_text: self.update_table_item(idx, text))
                else:
                    self.root.after(0, lambda idx=index, text=display_text: self.update_table_item(idx, text))
            else:
                self.root.after(0, lambda idx=index: self.update_table_item(idx, "未知"))
        else:
            # 如果没有原始匹配结果，则重新匹配
            original_filename = self.music_files[index].name

            # 清理文件名以用于搜索
            search_keyword = clean_filename(original_filename)
            # 将&替换为英文逗号
            search_keyword = search_keyword.replace('&', ',')
            logger.debug(f"重新匹配关键词: {search_keyword}")

            # 在新线程中重新匹配该文件
            matching_thread = threading.Thread(target=self.rematch_single_file, args=(index, search_keyword))
            matching_thread.daemon = True
            matching_thread.start()

        logger.info(f"已取消忽略项: {self.music_files[index].name}")

    def rematch_single_file(self, index, search_keyword):
        """在后台线程中重新匹配单个文件"""
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self._rematch_single_file_async(index, search_keyword))
        finally:
            loop.close()

    async def _rematch_single_file_async(self, index, search_keyword):
        """异步重新匹配单个文件"""
        try:
            # 异步搜索音乐
            async with AsyncRateLimitedGDAPIClient() as client:
                search_results = await client.search(search_keyword, source="netease", count=5)

            if not search_results:
                matched_song = {"name": "未找到匹配", "artist": "", "id": None}
            else:
                # 找到最佳匹配
                best_match = find_best_match(search_results, self.music_files[index].name, False)
                if not best_match:
                    matched_song = {"name": "未找到匹配", "artist": "", "id": None}
                else:
                    matched_song = best_match

            # 更新匹配结果
            self.matched_songs[index] = matched_song
            # 同时保存到原始匹配结果列表
            self.original_matched_songs[index] = matched_song

            # 更新状态
            if self.status_manager:
                old_status = self.status_manager.get_status(index)
                if matched_song and matched_song.get('id'):
                    # 匹配成功
                    self.status_manager.set_status(index, MusicStatus.AUTO_MATCHED)
                    logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.AUTO_MATCHED.value}")
                    status_text = MusicStatus.AUTO_MATCHED.value
                else:
                    # 匹配失败
                    self.status_manager.set_status(index, MusicStatus.MATCH_FAIL)
                    logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.MATCH_FAIL.value}")
                    status_text = MusicStatus.MATCH_FAIL.value
            else:
                # 如果状态管理器不存在，使用默认值
                status_text = "未知状态"

            # 更新表格显示
            if matched_song and matched_song.get('id'):
                display_text = f"{matched_song.get('name', '未知')} - {matched_song.get('artist', ['未知'])[0] if isinstance(matched_song.get('artist'), list) else matched_song.get('artist', '未知')}"
            else:
                display_text = "未找到匹配" if not matched_song or not matched_song.get('id') else "匹配失败"
            self.root.after(0, lambda idx=index, text=display_text, st=status_text: self.update_table_item(idx, text, st))

            logger.info(f"重新匹配完成: {self.music_files[index].name}")
        except Exception as e:
            logger.error(f"重新匹配文件时出错 {self.music_files[index].name}: {str(e)}")
            matched_song = {"name": "匹配失败", "artist": "", "id": None}
            self.matched_songs[index] = matched_song
            # 同时保存到原始匹配结果列表
            self.original_matched_songs[index] = matched_song

            # 更新状态为匹配失败
            if self.status_manager:
                old_status = self.status_manager.get_status(index)
                self.status_manager.set_status(index, MusicStatus.MATCH_FAIL)
                logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.MATCH_FAIL.value}")

            display_text = "匹配失败"
            self.root.after(0, lambda idx=index, text=display_text: self.update_table_item(idx, text, MusicStatus.MATCH_FAIL.value))

    def manual_match(self, item):
        """手动匹配指定项"""
        # 获取项索引
        items = self.tree.get_children()
        index = items.index(item)

        # 获取原始文件名
        original_filename = self.music_files[index].name

        # 创建手动匹配窗口
        self.create_manual_match_window(index, original_filename)

    def create_manual_match_window(self, index, original_filename):
        """创建手动匹配窗口"""
        # 创建新窗口
        match_window = tk.Toplevel(self.root)
        match_window.title(f"手动匹配 - {original_filename}")
        match_window.geometry("600x400")
        match_window.transient(self.root)  # 设置为父窗口的临时窗口
        match_window.grab_set()  # 模态窗口

        # 居中显示
        match_window.update_idletasks()
        x = (match_window.winfo_screenwidth() // 2) - (match_window.winfo_width() // 2)
        y = (match_window.winfo_screenheight() // 2) - (match_window.winfo_height() // 2)
        match_window.geometry(f"+{x}+{y}")

        # 创建界面元素
        # 搜索框
        search_frame = ttk.Frame(match_window)
        search_frame.pack(pady=10, padx=10, fill='x')

        ttk.Label(search_frame, text="搜索:").pack(side='left')

        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
        search_entry.pack(side='left', padx=(5, 5), fill='x', expand=True)

        search_btn = ttk.Button(search_frame, text="搜索", command=lambda: self.perform_search_async(index, search_var.get(), result_tree))
        search_btn.pack(side='left', padx=(0, 5))

        # 结果表格
        result_frame = ttk.Frame(match_window)
        result_frame.pack(pady=10, padx=10, fill='both', expand=True)

        # 创建Treeview作为结果列表
        result_tree = ttk.Treeview(result_frame, columns=('name', 'artist', 'album'), show='headings', height=15)
        result_tree.heading('name', text='歌曲名')
        result_tree.heading('artist', text='歌手')
        result_tree.heading('album', text='专辑')
        result_tree.column('name', width=200)
        result_tree.column('artist', width=150)
        result_tree.column('album', width=200)

        # 添加滚动条
        result_scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=result_tree.yview)
        result_tree.configure(yscrollcommand=result_scrollbar.set)

        result_tree.pack(side='left', fill='both', expand=True)
        result_scrollbar.pack(side='right', fill='y')

        # 绑定双击事件
        result_tree.bind("<Double-1>", lambda event: self.select_match(event, index, result_tree, match_window))

        # 按钮框架
        button_frame = ttk.Frame(match_window)
        button_frame.pack(pady=10, padx=10, fill='x')

        cancel_btn = ttk.Button(button_frame, text="取消", command=match_window.destroy)
        cancel_btn.pack(side='right', padx=(5, 0))

        select_btn = ttk.Button(button_frame, text="选择", command=lambda: self.select_match(None, index, result_tree, match_window))
        select_btn.pack(side='right')

        # 自动搜索原始文件名
        search_keyword = clean_filename(original_filename)
        # 将&替换为英文逗号
        search_keyword = search_keyword.replace('&', ',')
        search_var.set(search_keyword)
        self.perform_search_async(index, search_var.get(), result_tree)

    def select_match(self, event, index, result_tree, window):
        """选择匹配项"""
        # 获取选中的项
        selection = result_tree.selection()
        if not selection:
            logger.warning("请先选择一个匹配项")
            messagebox.showwarning("警告", "请先选择一个匹配项")
            return

        # 获取选中项的数据
        item = result_tree.item(selection[0])
        values = item['values']

        # 获取关联的结果对象索引
        tags = item['tags']
        if not tags:
            logger.error("无法获取匹配结果数据")
            messagebox.showerror("错误", "无法获取匹配结果数据")
            return

        tag = tags[0]  # 获取tag，格式为"search_result_X"

        # 从缓存中获取对应的结果对象
        tree_id = str(result_tree)
        if not hasattr(self, '_search_results_cache') or tree_id not in self._search_results_cache:
            logger.error("搜索结果缓存不存在")
            messagebox.showerror("错误", "搜索结果缓存不存在")
            return

        search_results = self._search_results_cache[tree_id]

        # 从tag中提取索引
        if tag.startswith("search_result_"):
            try:
                result_index = int(tag.split("_")[-1])
                if 0 <= result_index < len(search_results):
                    result = search_results[result_index]
                else:
                    logger.error("匹配结果索引超出范围")
                    messagebox.showerror("错误", "匹配结果索引超出范围")
                    return
            except ValueError:
                logger.error("匹配结果格式错误")
                messagebox.showerror("错误", "匹配结果格式错误")
                return
        else:
            logger.error("匹配结果格式错误")
            messagebox.showerror("错误", "匹配结果格式错误")
            return

        # 确保结果是一个字典对象
        if not isinstance(result, dict):
            logger.error("匹配结果格式错误")
            messagebox.showerror("错误", "匹配结果格式错误")
            return

        # 更新主窗口的匹配结果 - 存储完整的结果对象而不是字符串
        self.matched_songs[index] = result

        # 更新状态为手动匹配成功
        if self.status_manager:
            old_status = self.status_manager.get_status(index)
            self.status_manager.set_status(index, MusicStatus.MANUAL_MATCHED)
            logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.MANUAL_MATCHED.value}")

        # 更新主窗口表格显示
        items = self.tree.get_children()
        if index < len(items):
            item_id = items[index]
            current_values = self.tree.item(item_id, 'values')

            # 从result对象中获取歌曲名和艺术家信息用于显示，与主匹配逻辑保持一致
            name = result.get('name', '未知')
            artist = result.get('artist', ['未知'])[0] if isinstance(result.get('artist'), list) else result.get('artist', '未知')
            display_text = f"{name} - {artist}"
            self.tree.item(item_id, values=(current_values[0], display_text, MusicStatus.MANUAL_MATCHED.value))

        # 关闭窗口
        window.destroy()

        logger.info(f"已选择匹配项: {values[0]}")

    def perform_search_async(self, index, keyword, result_tree):
        """异步执行搜索"""
        # 在后台线程中运行异步搜索
        search_thread = threading.Thread(target=self._perform_search_async_threaded, args=(index, keyword, result_tree))
        search_thread.daemon = True
        search_thread.start()

    def _perform_search_async_threaded(self, index, keyword, result_tree):
        """在独立线程中运行异步搜索"""
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self._perform_search_async(index, keyword, result_tree))
        finally:
            loop.close()

    async def _perform_search_async(self, index, keyword, result_tree):
        """执行异步搜索"""
        try:
            # 清空现有结果
            self.root.after(0, lambda: self._clear_search_results(result_tree))

            if not keyword:
                return

            # 将&替换为英文逗号
            keyword = keyword.replace('&', ',')
            # 异步执行搜索
            async with AsyncRateLimitedGDAPIClient() as client:
                search_results = await client.search(keyword, source="netease", count=20)

            # 在主线程中填充结果到表格
            self.root.after(0, lambda: self._populate_search_results(search_results, result_tree))

        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"搜索失败: {str(e)}"))

    def _clear_search_results(self, result_tree):
        """清空搜索结果"""
        for item in result_tree.get_children():
            result_tree.delete(item)

    def _populate_search_results(self, search_results, result_tree):
        """填充搜索结果到表格"""
        # 为每个结果树存储搜索结果
        if not hasattr(self, '_search_results_cache'):
            self._search_results_cache = {}
        # 使用result_tree的id作为键来存储结果
        tree_id = str(result_tree)  # 使用树的字符串表示作为键
        self._search_results_cache[tree_id] = search_results

        for i, result in enumerate(search_results):
            name = result.get('name', '未知')
            # 处理艺术家信息，将&替换为逗号
            artist_data = result.get('artist', [])
            if isinstance(artist_data, list):
                # 将列表中的&替换为逗号
                artist_list = [artist.replace('&', ',') for artist in artist_data]
                artist = ', '.join(artist_list)
            else:
                artist = str(artist_data).replace('&', ',')
            album = result.get('album', '未知')

            result_tree.insert('', 'end', values=(name, artist, album), tags=(f"search_result_{i}",))

    def download_single(self, item):
        """下载单个歌曲"""
        # 获取项索引
        items = self.tree.get_children()
        index = items.index(item)

        # 检查是否有匹配结果
        matched_song = self.matched_songs[index]
        # 检查matched_song是否为字典且有id字段
        if not matched_song or not isinstance(matched_song, dict) or not matched_song.get('id'):
            logger.warning(f"文件 {self.music_files[index].name} 没有匹配结果，无法下载")
            messagebox.showwarning("警告", "该项目没有匹配结果，无法下载")
            return

        # 确认是否下载
        filename = self.music_files[index].name
        if not messagebox.askyesno("确认", f"确定要下载 {filename} 吗？"):
            return

        # 在新线程中执行下载
        download_thread = threading.Thread(target=self.download_single_async_threaded, args=(index,))
        download_thread.daemon = True
        download_thread.start()

    def download_single_async_threaded(self, index):
        """在独立线程中运行异步下载"""
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.download_single_async(index))
        finally:
            loop.close()

    async def download_single_async(self, index):
        """异步下载单个歌曲"""
        try:
            music_file = self.music_files[index]
            matched_song = self.matched_songs[index]

            # 显示当前处理的文件
            self.root.after(0, lambda f=music_file.name: self.update_status(f"正在下载: {f}"))

            if matched_song and matched_song.get('id'):
                # 获取输出目录
                output_dir = self.output_var.get() or None

                # 异步下载无损音乐
                async with AsyncRateLimitedGDAPIClient() as client:
                    download_path = await download_lossless_music_async(
                        client,
                        matched_song['id'],
                        "netease",
                        music_file,
                        output_dir
                    )

                if download_path:
                    logger.info(f"成功下载: {music_file.name}")
                    # 更新状态为已下载(自动)
                    if self.status_manager:
                        old_status = self.status_manager.get_status(index)
                        self.status_manager.set_status(index, MusicStatus.AUTO_DOWNLOAD_COMPLETE)
                        logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.AUTO_DOWNLOAD_COMPLETE.value}")
                    # 更新表格显示为已下载
                    self.root.after(0, lambda idx=index: self.update_table_item(idx, "已下载", MusicStatus.AUTO_DOWNLOAD_COMPLETE.value))
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"成功下载: {music_file.name}"))
                else:
                    logger.warning(f"下载失败: {music_file.name}")
                    # 更新状态为下载失败
                    if self.status_manager:
                        old_status = self.status_manager.get_status(index)
                        self.status_manager.set_status(index, MusicStatus.DOWNLOAD_FAIL)
                        logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.DOWNLOAD_FAIL.value}")
                    self.root.after(0, lambda idx=index: self.update_table_item(idx, "下载失败", MusicStatus.DOWNLOAD_FAIL.value))
                    self.root.after(0, lambda: messagebox.showwarning("失败", f"下载失败: {music_file.name}"))
            else:
                logger.warning(f"没有匹配结果: {music_file.name}")
                self.root.after(0, lambda: messagebox.showwarning("警告", f"没有匹配结果: {music_file.name}"))

        except Exception as e:
            logger.error(f"下载过程中出错: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"下载过程中出错: {str(e)}"))

    def start_upgrade(self):
        """开始升级音乐文件 - 自动下载所有匹配的文件（仅下载AUTO_MATCHED和MANUAL_MATCHED状态的文件）"""
        if not self.directory or not self.music_files:
            logger.warning("请先扫描音乐文件")
            messagebox.showwarning("警告", "请先扫描音乐文件")
            return

        # 计算可自动下载的文件数量（只考虑AUTO_MATCHED和MANUAL_MATCHED状态的文件）
        downloadable_count = 0
        if self.status_manager:
            for i in range(len(self.music_files)):
                status = self.status_manager.get_status(i)
                if status in [MusicStatus.AUTO_MATCHED, MusicStatus.MANUAL_MATCHED]:
                    downloadable_count += 1
        else:
            # 如果没有状态管理器，使用原始逻辑
            downloadable_count = sum(1 for song in self.matched_songs if song and isinstance(song, dict) and song.get('id'))

        if downloadable_count == 0:
            logger.warning("没有可升级的匹配文件")
            messagebox.showwarning("警告", "没有可升级的匹配文件")
            return

        # 确认是否继续
        if not messagebox.askyesno("确认", f"将要升级 {downloadable_count} 个文件，是否继续？"):
            return

        # 禁用控件
        self.disable_controls_during_download()

        # 在新线程中执行升级
        upgrade_thread = threading.Thread(target=self.upgrade_files_async_threaded)
        upgrade_thread.daemon = True
        upgrade_thread.start()

    def disable_controls_during_download(self):
        """在下载期间禁用控件"""
        self.upgrade_btn.config(state='disabled')
        self.tree.config(selectmode='none')  # 禁用表格选择

    def enable_controls_after_download(self):
        """下载完成后启用控件"""
        self.upgrade_btn.config(state='normal')
        self.tree.config(selectmode='browse')  # 启用表格选择
        # 绑定右键菜单事件
        self.tree.bind("<Button-3>", self.show_context_menu)  # 右键点击

    def scroll_to_item(self, index):
        """滚动到指定项"""
        items = self.tree.get_children()
        if index < len(items):
            item_id = items[index]
            self.tree.selection_set(item_id)
            self.tree.see(item_id) # 确保该项可见
            self.tree.focus(item_id) # 设置焦点

    def upgrade_files_async_threaded(self):
        """在独立线程中运行异步升级过程"""
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.upgrade_files_async())
        finally:
            loop.close()

    async def upgrade_files_async(self):
        """异步升级文件"""
        success_count = 0
        fail_count = 0

        for i, (music_file, matched_song) in enumerate(zip(self.music_files, self.matched_songs)):
            # 检查状态管理器是否存在以及当前项是否处于可下载状态
            can_download = True
            if self.status_manager:
                current_status = self.status_manager.get_status(i)
                # 只处理AUTO_MATCHED或MANUAL_MATCHED状态的文件
                if current_status not in [MusicStatus.AUTO_MATCHED, MusicStatus.MANUAL_MATCHED]:
                    can_download = False

            # 更新进度
            progress = (i / len(self.music_files)) * 100
            self.root.after(0, lambda p=progress: self.progress_var.set(p))

            # 显示当前处理的文件
            self.root.after(0, lambda f=music_file.name: self.update_status(f"正在升级: {f}"))

            # 自动滚动到当前项
            self.root.after(0, lambda idx=i: self.scroll_to_item(idx))

            if can_download and matched_song and matched_song.get('id'):
                try:
                    # 获取输出目录
                    output_dir = self.output_var.get() or None

                    # 异步下载无损音乐
                    async with AsyncRateLimitedGDAPIClient() as client:
                        download_path = await download_lossless_music_async(
                            client,
                            matched_song['id'],
                            "netease",
                            music_file,
                            output_dir
                        )

                    if download_path:
                        success_count += 1
                        logger.info(f"成功升级: {music_file.name}")
                        # 更新状态为已下载(自动)
                        if self.status_manager:
                            old_status = self.status_manager.get_status(i)
                            self.status_manager.set_status(i, MusicStatus.AUTO_DOWNLOAD_COMPLETE)
                            logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.AUTO_DOWNLOAD_COMPLETE.value}")
                        # 更新表格显示为已下载
                        self.root.after(0, lambda idx=i: self.update_table_item(idx, "已下载", MusicStatus.AUTO_DOWNLOAD_COMPLETE.value))
                    else:
                        fail_count += 1
                        logger.warning(f"升级失败: {music_file.name}")
                        # 更新状态为下载失败
                        if self.status_manager:
                            old_status = self.status_manager.get_status(i)
                            self.status_manager.set_status(i, MusicStatus.DOWNLOAD_FAIL)
                            logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.DOWNLOAD_FAIL.value}")
                        self.root.after(0, lambda idx=i: self.update_table_item(idx, "下载失败", MusicStatus.DOWNLOAD_FAIL.value))
                except Exception as e:
                    fail_count += 1
                    logger.error(f"升级文件失败 {music_file.name}: {str(e)}")
                    # 更新状态为下载失败
                    if self.status_manager:
                        old_status = self.status_manager.get_status(i)
                        self.status_manager.set_status(i, MusicStatus.DOWNLOAD_FAIL)
                        logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.DOWNLOAD_FAIL.value}")
                    self.root.after(0, lambda idx=i: self.update_table_item(idx, "下载失败", MusicStatus.DOWNLOAD_FAIL.value))
            else:
                # 如果文件状态不是可下载的，跳过
                if self.status_manager and self.status_manager.get_status(i) not in [MusicStatus.AUTO_MATCHED, MusicStatus.MANUAL_MATCHED]:
                    logger.info(f"跳过文件（状态不可下载）: {music_file.name}")
                else:
                    fail_count += 1
                    logger.warning(f"没有匹配结果: {music_file.name}")

        # 所有文件处理完成
        self.root.after(0, lambda: self.upgrade_complete(success_count, fail_count))

    def upgrade_complete(self, success_count, fail_count):
        """升级完成后的处理"""
        self.progress_var.set(100)
        self.enable_controls_after_download()
        self.root.title("音乐品质升级工具")
        logger.info(f"升级完成！成功: {success_count}, 失败: {fail_count}, 总计: {len(self.music_files)}")
        messagebox.showinfo("完成", f"升级完成！成功: {success_count}, 失败: {fail_count}, 总计: {len(self.music_files)}")


def main():
    root = tk.Tk()
    app = MusicUpgradeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
