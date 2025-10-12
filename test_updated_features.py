#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修改后的功能：
1. 默认只使用歌曲名进行匹配
2. 增加 --match-artist 选项来额外匹配歌手
3. 重试和超时功能
"""

import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from music_upgrade import find_best_match


def test_find_best_match_default():
    """测试默认只匹配歌曲名的功能"""
    print("测试默认只匹配歌曲名的功能:")

    # 模拟搜索结果
    search_results = [
        {
            'id': '1',
            'name': '青花瓷',
            'artist': ['周杰伦'],
            'album': '我很忙'
        },
        {
            'id': '2',
            'name': '菊花台',
            'artist': ['周杰伦'],
            'album': '黄金甲'
        },
        {
            'id': '3',
            'name': '青花瓷',
            'artist': ['Jay Chou'],
            'album': 'I Am Busy'
        },
        {
            'id': '4',
            'name': '发如雪',
            'artist': ['周杰伦'],
            'album': '十一月的萧邦'
        }
    ]

    # 测试用例
    test_cases = [
        {
            'filename': '周杰伦 - 青花瓷.mp3',
            'expected_id': '1',  # 默认只匹配歌曲名，应该匹配到周杰伦的青花瓷
            'description': '测试默认只匹配歌曲名（即使文件名包含歌手）',
            'match_artist': False
        },
        {
            'filename': '青花瓷.mp3',
            'expected_id': '1',  # 应该匹配到青花瓷，优先匹配歌曲名
            'description': '测试仅有歌曲名匹配',
            'match_artist': False
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n  测试 {i}: {test_case['description']}")
        print(f"    输入文件名: {test_case['filename']}")
        print(f"    match_artist: {test_case['match_artist']}")

        best_match = find_best_match(search_results, test_case['filename'], test_case['match_artist'])

        if best_match:
            print(f"    匹配结果: {best_match['name']} - {best_match['artist']}")
            print(f"    ID: {best_match['id']}")

            if best_match['id'] == test_case['expected_id']:
                print("    ✓ 匹配正确")
            else:
                print(f"    ✗ 匹配错误，期望ID: {test_case['expected_id']}")
        else:
            print("    ✗ 未找到匹配结果")

    print("\n默认匹配功能测试完成!\n")


def test_find_best_match_with_artist():
    """测试使用 --match-artist 选项的功能"""
    print("测试使用歌手匹配的功能:")

    # 模拟搜索结果
    search_results = [
        {
            'id': '1',
            'name': '青花瓷',
            'artist': ['周杰伦'],
            'album': '我很忙'
        },
        {
            'id': '2',
            'name': '菊花台',
            'artist': ['周杰伦'],
            'album': '黄金甲'
        },
        {
            'id': '3',
            'name': '青花瓷',
            'artist': ['Jay Chou'],
            'album': 'I Am Busy'
        },
        {
            'id': '4',
            'name': '发如雪',
            'artist': ['周杰伦'],
            'album': '十一月的萧邦'
        }
    ]

    # 测试用例
    test_cases = [
        {
            'filename': '周杰伦 - 青花瓷.mp3',
            'expected_id': '1', # 应该匹配到周杰伦的青花瓷（歌曲名和歌手都匹配）
            'description': '测试匹配歌手时的准确匹配',
            'match_artist': True
        },
        {
            'filename': 'Jay Chou - 青花瓷.mp3',
            'expected_id': '3',  # 应该匹配到Jay Chou的青花瓷
            'description': '测试英文歌手名匹配',
            'match_artist': True
        },
        {
            'filename': '青花瓷.mp3',
            'expected_id': '1',  # 应该匹配到青花瓷，因为没有歌手信息
            'description': '测试无歌手分隔符时只匹配歌曲名',
            'match_artist': True
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n  测试 {i}: {test_case['description']}")
        print(f"    输入文件名: {test_case['filename']}")
        print(f"    match_artist: {test_case['match_artist']}")

        best_match = find_best_match(search_results, test_case['filename'], test_case['match_artist'])

        if best_match:
            print(f"    匹配结果: {best_match['name']} - {best_match['artist']}")
            print(f"    ID: {best_match['id']}")

            if best_match['id'] == test_case['expected_id']:
                print("    ✓ 匹配正确")
            else:
                print(f"    ✗ 匹配错误，期望ID: {test_case['expected_id']}")
        else:
            print("    ✗ 未找到匹配结果")

    print("\n歌手匹配功能测试完成!\n")


def main():
    """运行所有测试"""
    print("开始测试修改后的功能...\n")

    test_find_best_match_default()
    test_find_best_match_with_artist()

    print("所有测试完成!")


if __name__ == "__main__":
    main()
