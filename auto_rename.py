import pathop
from argparse import ArgumentParser
import os
import re
import difflib

parser = ArgumentParser('auto-rename')

MUSIC_EXT = set(['mp3', 'flac', 'wav', 'm4a', 'ogg'])

def get_file_extension(fn: str):
    """获取文件扩展名（不包含点号）"""
    return os.path.splitext(fn)[1][1:].lower()  # 去掉点号并转为小写

def filter_music_files(file_list):
    """过滤音乐文件，只保留MUSIC_EXT中的文件"""
    filtered_files = []
    for file_path in file_list:
        ext = get_file_extension(file_path)
        if ext in MUSIC_EXT:
            filtered_files.append(file_path)  # 只保留MUSIC_EXT中的文件
    return filtered_files

def parse_arg():
    parser.add_argument('ref_path', help='Reference path containing files to match against')
    parser.add_argument('mod_path', help='Path containing files to be renamed')
    parser.add_argument('-t', '--threshold', type=float, default=0.7, help='Similarity threshold for matching files (default: 0.7)')
    args = parser.parse_args()
    return args.ref_path, args.mod_path, args.threshold

def extract_song_parts(fn: str):
    """从文件名中提取歌曲相关部分，处理常见的分隔符"""
    name = os.path.splitext(fn)[0]

    # 处理常见的分隔符，如 "歌手 - 歌曲名" 或 "歌曲名 (歌手)"
    # 首先尝试按连字符分割
    if '-' in name:
        parts = name.split('-')
        if len(parts) >= 2:
            # 假设第一部分是艺术家，第二部分及以后是歌曲名
            artist = parts[0].strip()
            song_title = ' '.join(parts[1:]).strip()
            return artist, song_title

    # 尝试其他分隔符模式
    if ',' in name:
        parts = name.split(',')
        if len(parts) >= 2:
            # 可能是 "歌曲名, 艺术家" 或其他格式
            return '', name  # 暂时返回整个名称作为歌曲标题

    # 如果没有明显分隔符，则返回整个名称作为歌曲标题
    return '', name

def clean_filename_for_comparison(fn: str):
    """清理文件名用于比较，移除特殊字符和空格，保留中文和全角字符"""
    # 提取歌曲部分
    artist, song_title = extract_song_parts(fn)

    # 合并并清理名称 - 移除所有空白字符和特殊字符
    combined = artist + ' ' + song_title

    # 替换全角字符为半角字符
    import unicodedata
    normalized = unicodedata.normalize('NFKC', combined)

    # 移除标点符号和空格，保留字母、数字、中文字符
    cleaned = re.sub(r'[^\w\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', '', normalized).lower()

    return cleaned

def calculate_similarity(name1, name2):
    """计算两个字符串的相似度"""
    return difflib.SequenceMatcher(None, name1, name2).ratio()

def find_matching_file(ref_files, mod_file, threshold):
    """在参考文件列表中找到与修改文件匹配的文件，使用相似度算法"""
    mod_name = os.path.basename(mod_file)
    cleaned_mod_name = clean_filename_for_comparison(mod_name)

    best_match = None
    best_similarity = 0

    for ref_file in ref_files:
        ref_name = os.path.basename(ref_file)
        cleaned_ref_name = clean_filename_for_comparison(ref_name)

        similarity = calculate_similarity(cleaned_ref_name, cleaned_mod_name)

        if similarity > best_similarity and similarity >= threshold:
            best_similarity = similarity
            best_match = ref_file

    return best_match, best_similarity

def do_rename(ref_path, mod_path, threshold):
    # 获取参考路径和修改路径中的所有文件
    all_ref_files = list(pathop.dump_dir(ref_path))
    all_mod_files = list(pathop.dump_dir(mod_path))

    # 过滤音乐文件
    ref_files = filter_music_files(all_ref_files)
    mod_files = filter_music_files(all_mod_files)

    matched_files = []
    unmatched_files = []

    for mod_file in mod_files:
        print(f"matching {os.path.basename(mod_file)}")
        matching_ref_file, similarity = find_matching_file(ref_files, mod_file, threshold)

        if matching_ref_file:
            # 获取参考文件的名称和扩展名
            ref_name = os.path.basename(matching_ref_file)
            ref_basename = os.path.splitext(ref_name)[0]

            # 获取待修改文件的扩展名（保持原始扩展名）
            mod_ext = os.path.splitext(mod_file)[1]

            # 获取待修改文件的目录
            mod_dir = os.path.dirname(mod_file)

            # 构建新的文件名（使用参考文件的名称 + 原始文件的扩展名）
            new_file_path = os.path.join(mod_dir, ref_basename + mod_ext)

            # 重命名文件
            print(f"matched {os.path.basename(mod_file)} with {os.path.basename(matching_ref_file)}")
            os.rename(mod_file, new_file_path)
            matched_files.append((mod_file, new_file_path))
        else:
            print(f"no match found for {os.path.basename(mod_file)}")
            unmatched_files.append(mod_file)

        # 两次匹配信息打印之间的换行
        print()

    # 输出重命名总结 - 使用过滤后的文件总数
    total_files = len(mod_files)
    renamed_count = len(matched_files)
    print(f"rename done, renamed file({renamed_count}/{total_files})")

    if unmatched_files:
        print("unable to match files:")
        for i, file_path in enumerate(unmatched_files, 1):
            print(f"{i}.{os.path.basename(file_path)}")

def main():
    ref_path, mod_path, threshold = parse_arg()
    do_rename(ref_path, mod_path, threshold)


if __name__ == '__main__':
    main()
