#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI音乐升级工具主入口
功能：读取指定目录下的音乐文件（跳过flac无损格式），使用文件名调用GD API搜索同歌曲，并显示匹配结果，
用户确认后下载无损格式到本地
"""

import tkinter as tk
from main_window import MusicUpgradeGUI


def main():
    root = tk.Tk()
    app = MusicUpgradeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
