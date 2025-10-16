#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动音乐下载软件
功能：读取指定目录下的音乐文件（跳过flac无损格式），使用文件名调用GD API搜索同歌曲，并下载无损格式到本地
"""

import os
import sys
import argparse
from music_upgrader_core import upgrade_music_files, logger


def main():
    parser = argparse.ArgumentParser(description='自动音乐下载软件 - 将普通音质音乐升级为无损音质')
    parser.add_argument('directory', nargs='?', help='要处理的音乐文件目录路径')
    parser.add_argument('-s', '--source', default='netease',
                       choices=['netease', 'tencent', 'tidal', 'spotify', 'ytmusic',
                               'qobuz', 'joox', 'deezer', 'migu', 'kugou', 'kuwo',
                               'ximalaya', 'apple'],
                       help='音乐源 (默认: netease)')
    parser.add_argument('-q', '--quality', type=int, default=99,
                       choices=[128, 192, 320, 740, 999],
                       help='音质 (128/192/320/740/99, 默认: 99为无损音质)')
    parser.add_argument('-o', '--output', help='下载文件的输出目录 (默认: 原文件所在目录)')
    parser.add_argument('-l', '--list-sources', action='store_true', help='列出支持的音乐源')
    parser.add_argument('-a', '--match-artist', action='store_true',
                       help='搜索时额外匹配歌手名 (默认: 只匹配歌曲名)')
    parser.add_argument('-r', '--retries', type=int, default=3,
                       help='API调用重试次数 (默认: 3)')
    parser.add_argument('-t', '--timeout', type=int, default=120,
                       help='API调用超时时间(秒) (默认: 120)')

    args = parser.parse_args()

    if args.list_sources:
        print("支持的音乐源:")
        sources = ['netease', 'tencent', 'tidal', 'spotify', 'ytmusic',
                  'qobuz', 'joox', 'deezer', 'migu', 'kugou', 'kuwo',
                  'ximalaya', 'apple']
        for source in sources:
            print(f"  - {source}")
        return

    if not args.directory:
        logger.error("错误: 请指定要处理的目录路径")
        parser.print_help()
        sys.exit(1)

    if not os.path.isdir(args.directory):
        logger.error(f"错误: 目录不存在 - {args.directory}")
        sys.exit(1)

    logger.info(f"开始升级音乐文件...")
    logger.info(f"目录: {args.directory}")
    logger.info(f"音乐源: {args.source}")
    logger.info(f"音质: {args.quality}")
    if args.output:
        logger.info(f"输出目录: {args.output}")

    upgrade_music_files(
        directory=args.directory,
        source=args.source,
        quality=args.quality,
        output_dir=args.output,
        match_artist=args.match_artist,
        retries=args.retries,
        timeout=args.timeout
    )


if __name__ == "__main__":
    main()
