#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试music_upgrade.py功能
"""

import os
import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from music_upgrade import clean_filename, is_music_file, scan_music_files

def test_clean_filename():
    """测试文件名清理功能"""
    print("测试文件名清理功能:")

    test_cases = [
        "青花瓷.mp3",
        "周杰伦 - 青花瓷.mp3",
        "青花瓷 320k.mp3",
        "青花瓷 (无损).mp3",
        "青花瓷 FLAC.mp3",
        "青花瓷 MP3.mp3"
    ]

    for test_case in test_cases:
        cleaned = clean_filename(test_case)
        print(f"  {test_case} -> {cleaned}")

    print("文件名清理功能测试完成!\n")

def test_is_music_file():
    """测试音乐文件判断功能"""
    print("测试音乐文件判断功能:")

    test_cases = [
        ("test.mp3", True),
        ("test.wav", True),
        ("test.flac", False),  # flac被排除
        ("test.txt", False),
        ("test.jpg", False),
        ("test.m4a", True)
    ]

    for file_path, expected in test_cases:
        result = is_music_file(Path(file_path))
        status = "✓" if result == expected else "✗"
        print(f" {status} {file_path}: {result} (期望: {expected})")

    print("音乐文件判断功能测试完成!\n")

def test_scan_music_files():
    """测试音乐文件扫描功能"""
    print("测试音乐文件扫描功能:")

    # 创建临时测试目录
    test_dir = Path("test_music_dir")
    test_dir.mkdir(exist_ok=True)

    # 创建测试文件
    test_files = [
        "test1.mp3",
        "test2.wav",
        "test3.flac",  # 这个应该被跳过
        "test4.txt",   # 这个应该被跳过
        "test5.m4a"
    ]

    for file_name in test_files:
        (test_dir / file_name).touch()

    # 扫描音乐文件
    music_files = scan_music_files(str(test_dir))
    print(f"扫描到 {len(music_files)} 个音乐文件:")
    for file_path in music_files:
        print(f"  - {file_path.name}")

    # 验证结果
    expected_music_files = {"test1.mp3", "test2.wav", "test5.m4a"}
    actual_music_files = {file_path.name for file_path in music_files}

    if expected_music_files == actual_music_files:
        print("✓ 扫描结果正确")
    else:
        print(f"✗ 扫描结果错误。期望: {expected_music_files}, 实际: {actual_music_files}")

    # 清理测试目录
    for file_path in (test_dir).iterdir():
        file_path.unlink()
    test_dir.rmdir()

    print("音乐文件扫描功能测试完成!\n")

def main():
    """运行所有测试"""
    print("开始测试music_upgrade.py功能...\n")

    test_clean_filename()
    test_is_music_file()
    test_scan_music_files()

    print("所有测试完成!")

if __name__ == "__main__":
    main()
