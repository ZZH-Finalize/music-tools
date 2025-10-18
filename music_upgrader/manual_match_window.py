#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手动匹配窗口模块
创建手动匹配音乐文件的窗口界面
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import asyncio
from typing import List, Optional, Dict, Any

from music_upgrader_core_async import AsyncRateLimitedGDAPIClient, clean_filename, logger
from status_manager import MusicStatus


def create_manual_match_window(app, index, original_filename):
    """创建手动匹配窗口"""
    # 创建新窗口
    match_window = tk.Toplevel(app.root)

    # 检查当前状态，如果是下载完成状态，添加相应提示
    current_status = app.status_manager.get_status(index) if app.status_manager else None
    is_rematch_after_download = current_status in [MusicStatus.AUTO_DOWNLOAD_COMPLETE, MusicStatus.MANUAL_DOWNLOAD_COMPLETE]

    if is_rematch_after_download:
        match_window.title(f"重新匹配已下载歌曲 - {original_filename}")
    else:
        match_window.title(f"手动匹配 - {original_filename}")

    match_window.geometry("600x400")
    match_window.transient(app.root)  # 设置为父窗口的临时窗口
    match_window.grab_set()  # 模态窗口

    # 居中显示
    match_window.update_idletasks()
    x = (match_window.winfo_screenwidth() // 2) - (match_window.winfo_width() // 2)
    y = (match_window.winfo_screenheight() // 2) - (match_window.winfo_height() // 2)
    match_window.geometry(f"+{x}+{y}")

    # 如果是重新匹配下载完成的歌曲，添加提示信息
    if is_rematch_after_download:
        warning_label = ttk.Label(match_window, text="⚠️ 正在重新匹配已下载的歌曲", foreground="orange")
        warning_label.pack(pady=(10, 0))
        info_label = ttk.Label(match_window, text="选择新的匹配项后，可以重新下载", foreground="gray")
        info_label.pack(pady=(0, 5))

    # 创建界面元素
    # 搜索框
    search_frame = ttk.Frame(match_window)
    search_frame.pack(pady=10, padx=10, fill='x')

    ttk.Label(search_frame, text="搜索:").pack(side='left')

    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
    search_entry.pack(side='left', padx=(5, 5), fill='x', expand=True)

    search_btn = ttk.Button(search_frame, text="搜索", command=lambda: perform_search_async(app, index, search_var.get(), result_tree))
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
    result_tree.bind("<Double-1>", lambda event: select_match(app, event, index, result_tree, match_window))

    # 按钮框架
    button_frame = ttk.Frame(match_window)
    button_frame.pack(pady=10, padx=10, fill='x')

    cancel_btn = ttk.Button(button_frame, text="取消", command=match_window.destroy)
    cancel_btn.pack(side='right', padx=(5, 0))

    select_btn = ttk.Button(button_frame, text="选择", command=lambda: select_match(app, None, index, result_tree, match_window))
    select_btn.pack(side='right')

    # 自动搜索原始文件名
    search_keyword = clean_filename(original_filename)
    # 将&替换为英文逗号
    search_keyword = search_keyword.replace('&', ',')
    search_var.set(search_keyword)
    perform_search_async(app, index, search_var.get(), result_tree)


def select_match(app, event, index, result_tree, window):
    """选择匹配项"""
    logger.debug("新窗口-选择匹配项-双击")
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
    if not hasattr(app, '_search_results_cache') or tree_id not in app._search_results_cache:
        logger.error("搜索结果缓存不存在")
        messagebox.showerror("错误", "搜索结果缓存不存在")
        return

    search_results = app._search_results_cache[tree_id]

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
    app.matched_songs[index] = result

    # 更新状态为手动匹配成功
    if app.status_manager:
        old_status = app.status_manager.get_status(index)
        app.status_manager.set_status(index, MusicStatus.MANUAL_MATCHED)
        logger.debug(f"状态转换: {old_status.value if old_status else 'None'} -> {MusicStatus.MANUAL_MATCHED.value}")

        # 如果之前的歌曲已经下载完成，记录这个重新匹配的行为
        if old_status in [MusicStatus.AUTO_DOWNLOAD_COMPLETE, MusicStatus.MANUAL_DOWNLOAD_COMPLETE]:
            logger.info(f"重新匹配已下载的歌曲: {app.music_files[index].name} (原状态: {old_status.value})")

    # 更新主窗口表格显示
    items = app.tree.get_children()
    if index < len(items):
        item_id = items[index]
        current_values = app.tree.item(item_id, 'values')

        # 从result对象中获取歌曲名和艺术家信息用于显示，与主匹配逻辑保持一致
        name = result.get('name', '未知')
        artist = result.get('artist', ['未知'])[0] if isinstance(result.get('artist'), list) else result.get('artist', '未知')
        display_text = f"{name} - {artist}"
        app.tree.item(item_id, values=(current_values[0], display_text, MusicStatus.MANUAL_MATCHED.value))

    # 关闭窗口
    window.destroy()

    logger.info(f"已选择匹配项: {values[0]}")


def perform_search_async(app, index, keyword, result_tree):
    """异步执行搜索"""
    # 在后台线程中运行异步搜索
    search_thread = threading.Thread(target=_perform_search_async_threaded, args=(app, index, keyword, result_tree))
    search_thread.daemon = True
    search_thread.start()


def _perform_search_async_threaded(app, index, keyword, result_tree):
    """在独立线程中运行异步搜索"""
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_perform_search_async(app, index, keyword, result_tree))
    finally:
        loop.close()


async def _perform_search_async(app, index, keyword, result_tree):
    """执行异步搜索"""
    try:
        # 清空现有结果
        app.root.after(0, lambda: _clear_search_results(result_tree))

        if not keyword:
            return

        # 将&替换为英文逗号
        keyword = keyword.replace('&', ',')
        # 异步执行搜索
        async with AsyncRateLimitedGDAPIClient() as client:
            search_results = await client.search(keyword, source=app.music_source_var.get(), count=20)

        # 在主线程中填充结果到表格
        app.root.after(0, lambda: _populate_search_results(app, search_results, result_tree))

    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        app.root.after(0, lambda: messagebox.showerror("错误", f"搜索失败: {str(e)}"))


def _clear_search_results(result_tree):
    """清空搜索结果"""
    for item in result_tree.get_children():
        result_tree.delete(item)


def _populate_search_results(app, search_results, result_tree):
    """填充搜索结果到表格"""
    # 为每个结果树存储搜索结果
    if not hasattr(app, '_search_results_cache'):
        app._search_results_cache = {}
    # 使用result_tree的id作为键来存储结果
    tree_id = str(result_tree)  # 使用树的字符串表示作为键
    app._search_results_cache[tree_id] = search_results

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
