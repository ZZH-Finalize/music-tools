#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LRC歌词时间戳调整工具
该工具可以对LRC格式歌词文件的时间戳进行偏移调整
"""

import argparse
import re
import sys


def parse_timestamp(timestamp_str):
    """
    解析LRC时间戳格式 [mm:ss.xx] 或 [mm:ss.xxx] 并转换为毫秒

    Args:
        timestamp_str (str): 时间戳字符串，如 "01:23.45"

    Returns:
        int: 毫秒数
    """
    # 匹配 mm:ss.xx 或 mm:ss.xxx 格式
    pattern = r'(\d{1,3}):(\d{2})\.(\d{2,3})'
    match = re.match(pattern, timestamp_str)

    if not match:
        raise ValueError(f"无效的时间戳格式: {timestamp_str}")

    minutes = int(match.group(1))
    seconds = int(match.group(2))
    fraction = int(match.group(3))  # 可能是两位数（百分之一秒）或三位数（千分之一秒）

    # 如果是两位小数，则转换为毫秒；如果是三位小数则直接使用
    if len(match.group(3)) == 2:  # 百分之一秒
        milliseconds = fraction * 10
    else:  # 千分之一秒
        milliseconds = fraction

    total_ms = minutes * 60 * 1000 + seconds * 1000 + milliseconds
    return total_ms


def format_timestamp(milliseconds):
    """
    将毫秒数转换为标准LRC时间戳格式 [mm:ss.xx] (两位小数)

    Args:
        milliseconds (int): 毫秒数

    Returns:
        str: 格式化的时间戳字符串，如 "01:23.45"
    """
    if milliseconds < 0:
        milliseconds = 0  # 确保不出现负数时间戳

    minutes = milliseconds // (60 * 1000)
    seconds = (milliseconds % (60 * 1000)) // 1000
    ms = milliseconds % 1000

    # 使用两位小数表示法 (xx)，符合标准LRC格式
    centiseconds = ms // 10  # 将毫秒转换为厘秒（centisecond）
    return f"{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def adjust_lrc_content(content, offset_ms):
    """
    调整LRC歌词内容中的所有时间戳

    Args:
        content (str): 原始LRC内容
        offset_ms (int): 偏移量（毫秒），正数表示延后，负数表示提前

    Returns:
        str: 调整后的内容
    """
    # 匹配LRC时间戳的正则表达式模式
    # 匹配 [mm:ss.xx] 或 [mm:ss.xxx] 格式的时间戳
    timestamp_pattern = r'\[(\d{1,3}:\d{2}\.\d{2,3})\]'

    def replace_timestamp(match):
        original_timestamp = match.group(1)
        try:
            # 解析原时间戳为毫秒
            original_ms = parse_timestamp(original_timestamp)
            # 应用偏移
            adjusted_ms = original_ms + offset_ms
            # 格式化新时间戳
            new_timestamp = format_timestamp(adjusted_ms)
            return f"[{new_timestamp}]"
        except ValueError as e:
            print(f"警告: 无法解析时间戳 '{original_timestamp}': {e}", file=sys.stderr)
            return match.group(0)  # 返回原始匹配项

    # 替换所有时间戳
    adjusted_content = re.sub(timestamp_pattern, replace_timestamp, content)
    return adjusted_content


def main():
    parser = argparse.ArgumentParser(
        description="LRC歌词时间戳调整工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s -i input.lrc -a 100     # 增加100毫秒延迟
  %(prog)s -i input.lrc -a -100    # 提前100毫秒
  %(prog)s -i input.lrc --add 500  # 增加500毫秒延迟
        """
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        help="输入的LRC文件路径"
    )

    parser.add_argument(
        "-a", "--add",
        type=int,
        required=True,
        help="时间偏移量（毫秒），正数表示增加时间（延迟），负数表示减少时间（提前）"
    )

    parser.add_argument(
        "-o", "--output",
        help="输出文件路径，如果不指定则覆盖原文件"
    )

    args = parser.parse_args()

    try:
        # 读取LRC文件
        with open(args.input, 'r', encoding='utf-8') as f:
            original_content = f.read()

        # 调整时间戳
        adjusted_content = adjust_lrc_content(original_content, args.add)

        # 决定输出路径
        output_path = args.output if args.output else args.input

        # 写入调整后的内容
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(adjusted_content)

        print(f"成功调整LRC文件 '{args.input}' 的时间戳")
        print(f"偏移量: {args.add} 毫秒")
        print(f"输出到: {output_path}")

    except FileNotFoundError:
        print(f"错误: 找不到输入文件 '{args.input}'", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
