#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修改后的相似度匹配算法
"""

import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from music_upgrade import find_best_match


def test_similarity_match():
    """测试相似度匹配功能"""
    print("测试相似度匹配功能:")

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
            'expected_id': '1',  # 应该匹配到周杰伦的青花瓷
            'description': '测试标准格式匹配'
        },
        {
            'filename': 'Jay Chou - 青花瓷.mp3',
            'expected_id': '3',  # 应该匹配到Jay Chou的青花瓷
            'description': '测试英文名匹配'
        },
        {
            'filename': '青花瓷.mp3',
            'expected_id': '1',  # 应该匹配到青花瓷，优先匹配歌曲名
            'description': '测试仅有歌曲名匹配'
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n  测试 {i}: {test_case['description']}")
        print(f"    输入文件名: {test_case['filename']}")

        best_match = find_best_match(search_results, test_case['filename'])

        if best_match:
            print(f"    匹配结果: {best_match['name']} - {best_match['artist']}")
            print(f"    ID: {best_match['id']}")

            if best_match['id'] == test_case['expected_id']:
                print("    ✓ 匹配正确")
            else:
                print(f"    ✗ 匹配错误，期望ID: {test_case['expected_id']}")
        else:
            print("    ✗ 未找到匹配结果")

    print("\n相似度匹配功能测试完成!\n")


def main():
    """运行测试"""
    print("开始测试修改后的相似度匹配算法...\n")

    test_similarity_match()

    print("所有测试完成!")


if __name__ == "__main__":
    main()
