#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI主界面模块
包含音乐升级工具的主要界面和基本功能
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

# 导入异步核心模块（包含所有功能）
from music_upgrader_core_async import (
    AsyncRateLimitedGDAPIClient,
    download_lossless_music_async,
    upgrade_music_files_async,
    match_music_files_async,
    clean_filename,
    is_music_file,
    scan_music_files,
    match_music_files,
    logger
)

from status_manager import MusicStatus, MusicStateManager
from context_menu import ContextMenuHandler
from downloader import match_files_async, upgrade_files_async


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

        # 用于控制匹配和下载的取消操作
        self.is_matching = False
        self.is_upgrading = False
        self.cancel_matching = False
        self.cancel_upgrading = False

        # 日志等级变量
        self.log_level_var = tk.StringVar(value="INFO")
        self.log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        # 音乐源变量
        self.music_source_var = tk.StringVar(value="netease")
        self.music_sources = ["netease", "qq", "kuwo", "kugou", "migu"]

        # 创建界面
        self.create_widgets()

    def change_log_level(self, event=None):
        """更改日志等级"""
        logger.debug("按钮-更改日志等级-被点击")
        import logging
        new_level = self.log_level_var.get()
        logger.setLevel(getattr(logging, new_level))
        logger.info(f"日志等级已更改为: {new_level}")

    def change_music_source(self, event=None):
        """更改音乐源"""
        logger.debug("下拉框-更改音乐源-被选择")
        new_source = self.music_source_var.get()
        logger.info(f"音乐源已更改为: {new_source}")

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

        # 音乐源下拉框
        ttk.Label(top_control_frame, text="音乐源:").pack(side='left', padx=(10, 5))
        self.music_source_combo = ttk.Combobox(top_control_frame, textvariable=self.music_source_var,
                                               values=self.music_sources, state="readonly", width=10)
        self.music_source_combo.pack(side='left', padx=(0, 10))
        self.music_source_combo.bind('<<ComboboxSelected>>', self.change_music_source)

        # 路径输入区域
        path_frame = ttk.Frame(self.root)
        path_frame.pack(pady=10, padx=10, fill='x')

        ttk.Label(path_frame, text="参考目录:").pack(side='left')

        self.path_var = tk.StringVar()
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var, width=60)
        self.path_entry.pack(side='left', padx=(5, 5), fill='x', expand=True)

        self.browse_btn = ttk.Button(path_frame, text="浏览", command=self.browse_directory)
        self.browse_btn.pack(side='left', padx=(0, 5))

        # 输出目录输入区域
        output_frame = ttk.Frame(self.root)
        output_frame.pack(pady=5, padx=10, fill='x')

        ttk.Label(output_frame, text="输出目录:").pack(side='left')

        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_var, width=60)
        self.output_entry.pack(side='left', padx=(5, 5), fill='x', expand=True)

        self.output_browse_btn = ttk.Button(output_frame, text="浏览", command=self.browse_output_directory)
        self.output_browse_btn.pack(side='left', padx=(0, 5))

        # 创建表格框架
        table_frame = ttk.Frame(self.root)
        table_frame.pack(pady=10, padx=10, fill='both', expand=True)

        # 创建Treeview作为表格控件
        self.tree = ttk.Treeview(table_frame, columns=('original', 'matched', 'status'), show='headings', height=15)
        self.tree.heading('original', text='低音质音乐文件')
        self.tree.heading('matched', text='匹配的音乐文件')  # 第二列只显示音乐匹配信息
        self.tree.heading('status', text='状态')  # 第三列只显示状态
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

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(button_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side='left', fill='x', expand=True, padx=(0, 10))

        self.match_btn = ttk.Button(button_frame, text="自动匹配", command=self.start_matching)
        self.match_btn.pack(side='left', padx=(0, 5))

        self.upgrade_btn = ttk.Button(button_frame, text="开始升级", command=self.start_upgrade, state='disabled')
        self.upgrade_btn.pack(side='left', padx=(0, 5))

        # 移除表格选择事件绑定，避免在滚动时弹出信息框
        # self.tree.bind('<<TreeviewSelect>>', self.on_table_select)

    def browse_directory(self):
        logger.debug("按钮-浏览目录-被点击")
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
        logger.debug("按钮-浏览输出目录-被点击")
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
                self.tree.insert('', 'end', values=(file_path.name, '', MusicStatus.MATCH_PENDING.value))

            # 启用升级按钮
            self.upgrade_btn.config(state='normal')

            # 初始化右键菜单处理器
            self.context_menu_handler = ContextMenuHandler(self)
            # 在待匹配状态下绑定右键菜单事件
            self.tree.bind("<Button-3>", self.context_menu_handler.show_context_menu)  # 右键点击

        except Exception as e:
            logger.error(f"扫描文件失败: {str(e)}")
            messagebox.showerror("错误", f"扫描文件失败: {str(e)}")

    def start_matching(self):
        """在后台线程中开始匹配音乐文件或取消匹配"""
        if self.is_matching:
            # 如果正在匹配，点击按钮则取消匹配
            logger.debug("按钮-取消匹配-被点击")
            self.cancel_matching = True
        else:
            # 如果没有在匹配，开始匹配
            logger.debug("按钮-自动匹配-被点击")
            self.cancel_matching = False
            self.is_matching = True
            self.progress_var.set(0)
            self.upgrade_btn.config(state='disabled')

            # 更新按钮文本
            self.match_btn.config(text="取消匹配")

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
        self.tree.config(selectmode='none')  # 禁用表格选择，同时移除右键菜单
        self.tree.unbind("<Button-3>")  # 移除右键菜单绑定
        # 禁用音乐源下拉框
        if hasattr(self, 'music_source_combo'):
            self.music_source_combo.config(state='disabled')
        # 禁用参考目录输入框和浏览按钮
        if hasattr(self, 'path_entry'):
            self.path_entry.config(state='disabled')
        if hasattr(self, 'browse_btn'):
            self.browse_btn.config(state='disabled')
        # 禁用输出目录输入框和浏览按钮
        if hasattr(self, 'output_entry'):
            self.output_entry.config(state='disabled')
        if hasattr(self, 'output_browse_btn'):
            self.output_browse_btn.config(state='disabled')
        # 禁用升级按钮
        if hasattr(self, 'upgrade_btn'):
            self.upgrade_btn.config(state='disabled')
        # 注意：保持匹配按钮启用，以便可以点击取消
        # 注意：保持日志等级下拉框启用

    def enable_table_after_matching(self):
        """匹配完成后启用表格控件"""
        self.tree.config(selectmode='browse')  # 启用表格选择
        # 重新绑定右键菜单事件
        self.tree.bind("<Button-3>", self.context_menu_handler.show_context_menu)  # 右键点击
        # 启用音乐源下拉框
        if hasattr(self, 'music_source_combo'):
            self.music_source_combo.config(state='readonly')
        # 启用参考目录输入框和浏览按钮
        if hasattr(self, 'path_entry'):
            self.path_entry.config(state='normal')
        if hasattr(self, 'browse_btn'):
            self.browse_btn.config(state='normal')
        # 启用输出目录输入框和浏览按钮
        if hasattr(self, 'output_entry'):
            self.output_entry.config(state='normal')
        if hasattr(self, 'output_browse_btn'):
            self.output_browse_btn.config(state='normal')
        # 启用匹配按钮
        if hasattr(self, 'match_btn'):
            self.match_btn.config(state='normal')
        # 启用升级按钮
        if hasattr(self, 'upgrade_btn'):
            self.upgrade_btn.config(state='normal')

    def match_files_async_threaded(self):
        """在独立线程中运行异步匹配过程"""
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(match_files_async(self))
        finally:
            loop.close()

    def update_table_item(self, index, text, status_text=None):
        """更新表格的指定项"""
        items = self.tree.get_children()
        if index < len(items):
            item_id = items[index]
            current_values = self.tree.item(item_id, 'values')
            if text is None:
                # 如果没有提供文本，保持当前匹配文本不变
                if status_text is None:
                    # 如果状态文本也未提供，什么都不更新
                    return
                else:
                    # 只更新状态
                    self.tree.item(item_id, values=(current_values[0], current_values[1], status_text))
            elif status_text is None:
                # 如果没有提供状态文本，保持当前状态不变
                self.tree.item(item_id, values=(current_values[0], text, current_values[2]))
            else:
                # 同时更新匹配文本和状态
                self.tree.item(item_id, values=(current_values[0], text, status_text))

    def update_status(self, message):
        """更新状态信息"""
        self.root.title(f"音乐品质升级工具 - {message}")

    def cancel_matching_process(self):
        """取消匹配过程后的处理"""
        self.is_matching = False
        self.cancel_matching = False
        self.progress_var.set(0)
        self.upgrade_btn.config(state='normal')
        self.enable_table_after_matching() # 启用表格控件
        self.match_btn.config(text="自动匹配")  # 恢复按钮文本
        self.root.title("音乐品质升级工具")
        logger.info("匹配已取消")

    def matching_complete(self):
        """匹配完成后的处理"""
        self.is_matching = False  # 匹配完成，重置标志
        self.progress_var.set(10)
        self.upgrade_btn.config(state='normal')
        self.enable_table_after_matching() # 启用表格控件
        self.match_btn.config(text="自动匹配")  # 恢复按钮文本
        self.root.title("音乐品质升级工具")
        messagebox.showinfo("完成", f"匹配完成！找到 {len(self.music_files)} 个音乐文件，其中 {sum(1 for s in self.matched_songs if s and isinstance(s, dict) and s.get('id'))} 个成功匹配。")

    def start_upgrade(self):
        """开始升级音乐文件 - 自动下载所有匹配的文件（仅下载AUTO_MATCHED和MANUAL_MATCHED状态的文件）或取消下载"""
        if self.is_upgrading:
            # 如果正在升级，点击按钮则取消升级
            logger.debug("按钮-取消下载-被点击")
            self.cancel_upgrading = True
        else:
            # 如果没有在升级，开始升级
            logger.debug("按钮-开始升级-被点击")
            self.cancel_upgrading = False
            self.is_upgrading = True
            if not self.directory or not self.music_files:
                logger.warning("请先扫描音乐文件")
                messagebox.showwarning("警告", "请先扫描音乐文件")
                return

            # 计算可自动下载的文件数量（只考虑AUTO_MATCHED、MANUAL_MATCHED和DOWNLOAD_FAIL状态的文件）
            downloadable_count = 0
            if self.status_manager:
                for i in range(len(self.music_files)):
                    status = self.status_manager.get_status(i)
                    if status in [MusicStatus.AUTO_MATCHED, MusicStatus.MANUAL_MATCHED, MusicStatus.DOWNLOAD_FAIL]:
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

            # 更新按钮文本
            self.upgrade_btn.config(text="取消下载")

            # 禁用控件
            self.disable_controls_during_download()

            # 在新线程中执行升级
            upgrade_thread = threading.Thread(target=self.upgrade_files_async_threaded)
            upgrade_thread.daemon = True
            upgrade_thread.start()

    def disable_controls_during_download(self):
        """在下载期间禁用控件"""
        self.tree.config(selectmode='none') # 禁用表格选择，同时移除右键菜单
        self.tree.unbind("<Button-3>")  # 移除右键菜单绑定
        # 禁用音乐源下拉框
        if hasattr(self, 'music_source_combo'):
            self.music_source_combo.config(state='disabled')
        # 禁用参考目录输入框和浏览按钮
        if hasattr(self, 'path_entry'):
            self.path_entry.config(state='disabled')
        if hasattr(self, 'browse_btn'):
            self.browse_btn.config(state='disabled')
        # 禁用输出目录输入框和浏览按钮
        if hasattr(self, 'output_entry'):
            self.output_entry.config(state='disabled')
        if hasattr(self, 'output_browse_btn'):
            self.output_browse_btn.config(state='disabled')
        # 禁用匹配按钮
        if hasattr(self, 'match_btn'):
            self.match_btn.config(state='disabled')
        # 注意：保持升级按钮启用，以便可以点击取消
        # 注意：保持日志等级下拉框启用

    def cancel_upgrading_process(self):
        """取消升级过程后的处理"""
        self.is_upgrading = False
        self.cancel_upgrading = False
        self.progress_var.set(0)
        self.enable_controls_after_download()
        self.upgrade_btn.config(text="开始升级")  # 恢复按钮文本
        self.root.title("音乐品质升级工具")
        logger.info("升级已取消")

    def enable_controls_after_download(self):
        """下载完成后启用控件"""
        self.upgrade_btn.config(state='normal')
        self.tree.config(selectmode='browse')  # 启用表格选择
        # 重新绑定右键菜单事件
        self.tree.bind("<Button-3>", self.context_menu_handler.show_context_menu)  # 右键点击
        # 启用音乐源下拉框
        if hasattr(self, 'music_source_combo'):
            self.music_source_combo.config(state='readonly')
        # 启用参考目录输入框和浏览按钮
        if hasattr(self, 'path_entry'):
            self.path_entry.config(state='normal')
        if hasattr(self, 'browse_btn'):
            self.browse_btn.config(state='normal')
        # 启用输出目录输入框和浏览按钮
        if hasattr(self, 'output_entry'):
            self.output_entry.config(state='normal')
        if hasattr(self, 'output_browse_btn'):
            self.output_browse_btn.config(state='normal')
        # 启用匹配按钮
        if hasattr(self, 'match_btn'):
            self.match_btn.config(state='normal')

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
            loop.run_until_complete(upgrade_files_async(self))
        finally:
            loop.close()

    def upgrade_complete(self, success_count, fail_count):
        """升级完成后的处理"""
        self.is_upgrading = False  # 升级完成，重置标志
        self.progress_var.set(10)
        self.enable_controls_after_download()
        self.upgrade_btn.config(text="开始升级")  # 恢复按钮文本
        self.root.title("音乐品质升级工具")
        logger.info(f"升级完成！成功: {success_count}, 失败: {fail_count}, 总计: {len(self.music_files)}")
        messagebox.showinfo("完成", f"升级完成！成功: {success_count}, 失败: {fail_count}, 总计: {len(self.music_files)}")
