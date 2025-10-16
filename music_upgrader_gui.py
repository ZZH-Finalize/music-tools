#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI音乐升级工具
功能：读取指定目录下的音乐文件（跳过flac无损格式），使用文件名调用GD API搜索同歌曲，并显示匹配结果，
用户确认后下载无损格式到本地
"""

import os
import sys
import threading
from typing import List, Optional, Dict, Any
from tkinter import ttk
import tkinter as tk
from tkinter import filedialog, messagebox

from music_upgrader_core import (
    RateLimitedGDAPIClient,
    clean_filename,
    is_music_file,
    scan_music_files,
    find_best_match,
    download_lossless_music,
    match_music_files
)

# 从核心库导入logger
from music_upgrader_core import logger


from typing import Dict, Any

class MusicUpgradeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("音乐品质升级工具")
        self.root.geometry("1000x700")

        # 初始化变量
        self.directory = ""
        self.music_files = []
        self.matched_songs: List[Optional[Dict[str, Any]]] = []
        self.client = RateLimitedGDAPIClient()

        # 创建界面
        self.create_widgets()

    def create_widgets(self):
        # 顶部路径输入区域
        path_frame = ttk.Frame(self.root)
        path_frame.pack(pady=10, padx=10, fill='x')

        ttk.Label(path_frame, text="参考目录:").pack(side='left')

        self.path_var = tk.StringVar()
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var, width=60)
        path_entry.pack(side='left', padx=(5, 5), fill='x', expand=True)

        browse_btn = ttk.Button(path_frame, text="浏览", command=self.browse_directory)
        browse_btn.pack(side='left', padx=(0, 5))

        scan_btn = ttk.Button(path_frame, text="扫描音乐文件", command=self.scan_files)
        scan_btn.pack(side='left', padx=(0, 5))

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
        self.tree = ttk.Treeview(table_frame, columns=('original', 'matched'), show='headings', height=15)
        self.tree.heading('original', text='低音质音乐文件')
        self.tree.heading('matched', text='匹配的音乐文件')
        self.tree.column('original', width=400)
        self.tree.column('matched', width=400)

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

    def browse_output_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_var.set(directory)

    def scan_files(self):
        if not self.directory:
            messagebox.showwarning("警告", "请先选择音乐目录")
            return

        try:
            self.music_files = scan_music_files(self.directory)
            self.matched_songs = [None] * len(self.music_files) # 初始化匹配列表

            # 清空表格
            for item in self.tree.get_children():
                self.tree.delete(item)

            # 添加音乐文件到表格
            for file_path in self.music_files:
                self.tree.insert('', 'end', values=(file_path.name, '等待匹配...'))

            # 启用升级按钮
            self.upgrade_btn.config(state='normal')

            # 自动开始匹配
            self.start_matching()

        except Exception as e:
            logger.error(f"扫描文件失败: {str(e)}")
            messagebox.showerror("错误", f"扫描文件失败: {str(e)}")

    def start_matching(self):
        """在后台线程中开始匹配音乐文件"""
        self.progress_var.set(0)
        self.upgrade_btn.config(state='disabled')

        # 在匹配期间禁用表格控件
        self.disable_table_during_matching()

        # 在新线程中运行匹配过程
        matching_thread = threading.Thread(target=self.match_files_threaded)
        matching_thread.daemon = True
        matching_thread.start()

    def disable_table_during_matching(self):
        """在匹配期间禁用表格控件"""
        self.tree.config(selectmode='none')  # 禁用表格选择

    def enable_table_after_matching(self):
        """匹配完成后启用表格控件"""
        self.tree.config(selectmode='browse')  # 启用表格选择
        # 绑定右键菜单事件
        self.tree.bind("<Button-3>", self.show_context_menu)  # 右键点击

    def match_files_threaded(self):
        """匹配文件的线程函数"""
        try:
            for i, music_file in enumerate(self.music_files):
                # 更新进度
                progress = (i / len(self.music_files)) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))

                # 显示当前处理的文件
                self.root.after(0, lambda f=music_file.name: self.update_status(f"正在匹配: {f}"))

                try:
                    # 清理文件名以用于搜索
                    search_keyword = clean_filename(music_file.name)
                    # 将&替换为英文逗号
                    search_keyword = search_keyword.replace('&', ',')
                    logger.debug(f"搜索关键词: {search_keyword}")

                    # 搜索音乐
                    search_results = self.client.search(search_keyword, source="netease", count=5)

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
                    self.matched_songs[i] = matched_song

                    # 更新表格显示
                    display_text = f"{matched_song.get('name', '未知')} - {matched_song.get('artist', ['未知'])[0] if isinstance(matched_song.get('artist'), list) else matched_song.get('artist', '未知')}"
                    self.root.after(0, lambda idx=i, text=display_text: self.update_table_item(idx, text))

                except Exception as e:
                    logger.error(f"匹配文件时出错 {music_file.name}: {str(e)}")
                    matched_song = {"name": "匹配失败", "artist": "", "id": None}
                    self.matched_songs[i] = matched_song
                    display_text = "匹配失败"
                    self.root.after(0, lambda idx=i, text=display_text: self.update_table_item(idx, text))

            # 匹配完成
            self.root.after(0, self.matching_complete)

        except Exception as e:
            logger.error(f"匹配过程中出错: {str(e)}")
            self.root.after(0, lambda e=e: messagebox.showerror("错误", f"匹配过程中出错: {str(e)}"))
            self.root.after(0, lambda: self.upgrade_btn.config(state='normal'))

    def update_table_item(self, index, text):
        """更新表格的指定项"""
        items = self.tree.get_children()
        if index < len(items):
            item_id = items[index]
            current_values = self.tree.item(item_id, 'values')
            self.tree.item(item_id, values=(current_values[0], text))

    def update_status(self, message):
        """更新状态信息"""
        self.root.title(f"音乐品质升级工具 - {message}")

    def matching_complete(self):
        """匹配完成后的处理"""
        self.progress_var.set(100)
        self.upgrade_btn.config(state='normal')
        self.enable_table_after_matching()  # 启用表格控件
        self.root.title("音乐品质升级工具")
        messagebox.showinfo("完成", f"匹配完成！找到 {len(self.music_files)} 个音乐文件，其中 {sum(1 for s in self.matched_songs if s and s.get('id'))} 个成功匹配。")

    def show_context_menu(self, event):
        """显示右键菜单"""
        # 获取点击位置的项
        item = self.tree.identify_row(event.y)
        if item:
            # 选中该项
            self.tree.selection_set(item)

            # 创建右键菜单
            context_menu = tk.Menu(self.root, tearoff=0)
            context_menu.add_command(label="忽略此项", command=lambda: self.ignore_item(item))
            context_menu.add_command(label="手动匹配", command=lambda: self.manual_match(item))
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

        # 更新表格显示
        current_values = self.tree.item(item, 'values')
        self.tree.item(item, values=(current_values[0], "已忽略"))

        logger.info(f"已忽略项: {current_values[0]}")

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
        search_var.set(clean_filename(original_filename))
        self.perform_search_async(index, search_var.get(), result_tree)

    def perform_search_async(self, index, keyword, result_tree):
        """异步执行搜索"""
        # 在新线程中执行搜索
        search_thread = threading.Thread(target=self._perform_search_threaded, args=(keyword, result_tree))
        search_thread.daemon = True
        search_thread.start()

    def _perform_search_threaded(self, keyword, result_tree):
        """在后台线程中执行搜索"""
        try:
            # 在主线程中清空现有结果
            self.root.after(0, lambda: self._clear_search_results(result_tree))

            if not keyword:
                return

            # 执行搜索
            search_results = self.client.search(keyword, source="netease", count=20)

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
        for result in search_results:
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

            result_tree.insert('', 'end', values=(name, artist, album), tags=(str(result),))

    def perform_search(self, index, keyword, result_tree):
        """执行搜索（保持向后兼容）"""
        try:
            # 清空现有结果
            for item in result_tree.get_children():
                result_tree.delete(item)

            if not keyword:
                return

            # 执行搜索
            search_results = self.client.search(keyword, source="netease", count=20)

            # 填充结果到表格
            for result in search_results:
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

                result_tree.insert('', 'end', values=(name, artist, album), tags=(str(result),))

        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            messagebox.showerror("错误", f"搜索失败: {str(e)}")

    def select_match(self, event, index, result_tree, window):
        """选择匹配项"""
        # 获取选中的项
        selection = result_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个匹配项")
            return

        # 获取选中项的数据
        item = result_tree.item(selection[0])
        values = item['values']

        # 获取关联的结果对象
        tags = item['tags']
        if not tags:
            messagebox.showerror("错误", "无法获取匹配结果数据")
            return

        result = tags[0]  # 第一个tag是结果对象

        # 更新主窗口的匹配结果
        self.matched_songs[index] = result

        # 更新主窗口表格显示
        items = self.tree.get_children()
        if index < len(items):
            item_id = items[index]
            current_values = self.tree.item(item_id, 'values')
            # 检查result是否为字符串
            if isinstance(result, str):
                display_text = result
            else:
                display_text = f"{result.get('name', '未知')} - {', '.join(result.get('artist', [])) if isinstance(result.get('artist'), list) else result.get('artist', '未知')}"
            self.tree.item(item_id, values=(current_values[0], display_text))

        # 关闭窗口
        window.destroy()

        logger.info(f"已选择匹配项: {values[0]}")

    def download_single(self, item):
        """下载单个歌曲"""
        # 获取项索引
        items = self.tree.get_children()
        index = items.index(item)

        # 检查是否有匹配结果
        matched_song = self.matched_songs[index]
        # 检查matched_song是否为字典且有id字段
        if not matched_song or (isinstance(matched_song, dict) and not matched_song.get('id')):
            messagebox.showwarning("警告", "该项目没有匹配结果，无法下载")
            return

        # 确认是否下载
        filename = self.music_files[index].name
        if not messagebox.askyesno("确认", f"确定要下载 {filename} 吗？"):
            return

        # 在新线程中执行下载
        download_thread = threading.Thread(target=self.download_single_threaded, args=(index,))
        download_thread.daemon = True
        download_thread.start()

    def download_single_threaded(self, index):
        """下载单个歌曲的线程函数"""
        try:
            music_file = self.music_files[index]
            matched_song = self.matched_songs[index]

            # 显示当前处理的文件
            self.root.after(0, lambda f=music_file.name: self.update_status(f"正在下载: {f}"))

            if matched_song and matched_song.get('id'):
                try:
                    # 获取输出目录
                    output_dir = self.output_var.get() or None

                    # 下载无损音乐
                    download_path = download_lossless_music(
                        self.client,
                        matched_song['id'],
                        "netease",
                        music_file,
                        output_dir
                    )

                    if download_path:
                        logger.info(f"成功下载: {music_file.name}")
                        # 更新表格显示为已下载
                        self.root.after(0, lambda idx=index: self.update_table_item(idx, "已下载"))
                        messagebox.showinfo("成功", f"成功下载: {music_file.name}")
                    else:
                        logger.warning(f"下载失败: {music_file.name}")
                        messagebox.showwarning("失败", f"下载失败: {music_file.name}")

                except Exception as e:
                    logger.error(f"下载文件失败 {music_file.name}: {str(e)}")
                    messagebox.showerror("错误", f"下载文件失败 {music_file.name}: {str(e)}")
            else:
                logger.warning(f"没有匹配结果: {music_file.name}")
                messagebox.showwarning("警告", f"没有匹配结果: {music_file.name}")

        except Exception as e:
            logger.error(f"下载过程中出错: {str(e)}")
            messagebox.showerror("错误", f"下载过程中出错: {str(e)}")


    def start_upgrade(self):
        """开始升级音乐文件"""
        if not self.directory or not self.music_files:
            messagebox.showwarning("警告", "请先扫描音乐文件")
            return

        if not any(song and song.get('id') for song in self.matched_songs if song):
            messagebox.showwarning("警告", "没有可升级的匹配文件")
            return

        # 确认是否继续
        if not messagebox.askyesno("确认", f"将要升级 {len(self.music_files)} 个文件，是否继续？"):
            return

        # 禁用控件
        self.disable_controls_during_download()

        # 在新线程中执行升级
        upgrade_thread = threading.Thread(target=self.upgrade_files_threaded)
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

    def scroll_to_item(self, index):
        """滚动到指定项"""
        items = self.tree.get_children()
        if index < len(items):
            item_id = items[index]
            self.tree.selection_set(item_id)
            self.tree.see(item_id)  # 确保该项可见
            self.tree.focus(item_id)  # 设置焦点

    def upgrade_files_threaded(self):
        """升级文件的线程函数"""
        success_count = 0
        fail_count = 0

        try:
            for i, (music_file, matched_song) in enumerate(zip(self.music_files, self.matched_songs)):
                # 更新进度
                progress = (i / len(self.music_files)) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))

                # 显示当前处理的文件
                self.root.after(0, lambda f=music_file.name: self.update_status(f"正在升级: {f}"))

                # 自动滚动到当前项
                self.root.after(0, lambda idx=i: self.scroll_to_item(idx))

                if matched_song and matched_song.get('id'):
                    try:
                        # 获取输出目录
                        output_dir = self.output_var.get() or None

                        # 下载无损音乐
                        download_path = download_lossless_music(
                            self.client,
                            matched_song['id'],
                            "netease",
                            music_file,
                            output_dir
                        )

                        if download_path:
                            success_count += 1
                            logger.info(f"成功升级: {music_file.name}")
                        else:
                            fail_count += 1
                            logger.warning(f"升级失败: {music_file.name}")

                    except Exception as e:
                        fail_count += 1
                        logger.error(f"升级文件失败 {music_file.name}: {str(e)}")
                else:
                    fail_count += 1
                    logger.warning(f"没有匹配结果: {music_file.name}")

            # 升级完成
            self.root.after(0, lambda: self.upgrade_complete(success_count, fail_count))

        except Exception as e:
            self.root.after(0, lambda e=e: messagebox.showerror("错误", f"升级过程中出错: {str(e)}"))
            self.root.after(0, lambda: self.enable_controls_after_download())

    def upgrade_complete(self, success_count, fail_count):
        """升级完成后的处理"""
        self.progress_var.set(100)
        self.enable_controls_after_download()
        self.root.title("音乐品质升级工具")
        messagebox.showinfo("完成", f"升级完成！成功: {success_count}, 失败: {fail_count}, 总计: {len(self.music_files)}")


def main():
    root = tk.Tk()
    app = MusicUpgradeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
