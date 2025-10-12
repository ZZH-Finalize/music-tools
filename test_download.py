"""
测试GD音乐API的下载功能
"""
from gd_api import GDAPIClient

def test():
    client = GDAPIClient()


def test_download_features():
    client = GDAPIClient()

    print("=== 测试下载功能 ===")

    # 先搜索一首歌曲
    print("\n1. 搜索歌曲...")
    search_results = client.search("青花瓷", source="netease", count=1)

    if search_results:
        track = search_results[0]
        print(f"找到歌曲: {track['name']} - {', '.join(track['artist'])}")

        # 测试下载歌词
        print("\n2. 测试下载歌词...")
        try:
            lrc_path = client.download_lyrics(track['lyric_id'], source="netease", file_path="test_lyrics.lrc")
            print(f"歌词已下载到: {lrc_path}")

            # 读取并显示歌词内容
            with open(lrc_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"歌词内容预览 (前200字符): {content[:200]}...")

        except Exception as e:
            print(f"下载歌词失败: {e}")

        # 测试下载专辑图
        print("\n3. 测试下载专辑图...")
        try:
            img_path = client.download_album_art(track['pic_id'], source="netease", size=500, file_path="test_album_art.jpg")
            print(f"专辑图已下载到: {img_path}")
        except Exception as e:
            print(f"下载专辑图失败: {e}")

        # 测试下载歌曲 (这里只获取链接，不实际下载大文件)
        print("\n4. 测试获取歌曲下载链接...")
        try:
            song_info = client.get_song_url(track['id'], source="netease", br=128)
            print(f"歌曲链接: {song_info.get('url', 'N/A')}")
            print(f"音质: {song_info.get('br', 'N/A')}kbps")
            print(f"文件大小: {round(song_info.get('size', 0) / 1024, 2) if song_info.get('size') else 0} MB")

            # 如果要实际下载歌曲，可以使用以下代码（注释掉以避免下载大文件）
            # mp3_path = client.download_song(track['id'], source="netease", br=128, file_path="test_song.mp3")
            # print(f"歌曲已下载到: {mp3_path}")

        except Exception as e:
            print(f"获取歌曲信息失败: {e}")

    print("\n=== 下载功能测试完成 ===")


if __name__ == "__main__":
    test_download_features()
