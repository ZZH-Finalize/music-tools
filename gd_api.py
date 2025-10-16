import requests
from typing import Optional, Dict, Any, List, Union
from urllib.parse import urlencode


class GDAPIClient:
    """
    GD音乐API客户端，封装了搜索、获取歌曲、获取专辑图、获取歌词等功能
    API接口文档参考: https://music-api.gdstudio.xyz/
    """

    def __init__(self, base_url: str = "https://music-api.gdstudio.xyz/api.php"):
        self.base_url = base_url
        self.session = requests.Session()

        # 默认音乐源
        self.default_source = "netease"

        # 支持的音乐源
        self.supported_sources = [
            "netease", "tencent", "tidal", "spotify", "ytmusic",
            "qobuz", "joox", "deezer", "migu", "kugou", "kuwo",
            "ximalaya", "apple"
        ]

    def search(
        self,
        keyword: str,
        source: str = "netease",
        count: int = 20,
        pages: int = 1,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        搜索音乐

        Args:
            keyword: 关键字，可以是曲目名、歌手名、专辑名
            source: 音乐源，默认为netease
            count: 页面长度，默认为20条
            pages: 页码，默认为第1页

        Returns:
            包含搜索结果的字典列表
            [
                {
                    "id": "曲目ID",
                    "name": "歌曲名",
                    "artist": "歌手列表",
                    "album": "专辑名",
                    "pic_id": "专辑图ID",
                    "url_id": "URL ID（废弃）",
                    "lyric_id": "歌词ID",
                    "source": "音乐源"
                }
            ]
        """
        if source not in self.supported_sources:
            raise ValueError(f"不支持的音乐源: {source}")

        params = {
            "types": "search",
            "source": source,
            "name": keyword,
            "count": count,
            "pages": pages
        }

        response = self.session.get(self.base_url, params=params)
        response.raise_for_status()
        return response.json()

    def get_song_url(
        self,
        track_id: str,
        source: str = "netease",
        br: int = 99,
        **kwargs
    ) -> Dict[str, Any]:
        """
        获取歌曲链接

        Args:
            track_id: 曲目ID
            source: 音乐源，默认为netease
            br: 音质，可选128、192、320、740、999（默认），其中740、999为无损音质

        Returns:
            {
                "url": "音乐链接",
                "br": "实际返回音质",
                "size": "文件大小，单位为KB"
            }
        """
        if source not in self.supported_sources:
            raise ValueError(f"不支持的音乐源: {source}")

        if br not in [128, 192, 320, 740, 999]:
            raise ValueError(f"不支持的音质: {br}")

        params = {
            "types": "url",
            "source": source,
            "id": track_id,
            "br": br
        }

        response = self.session.get(self.base_url, params=params)
        response.raise_for_status()
        return response.json()

    def get_album_art(
        self,
        pic_id: str,
        source: str = "netease",
        size: int = 300,
        **kwargs
    ) -> Dict[str, Any]:
        """
        获取专辑图

        Args:
            pic_id: 专辑图ID
            source: 音乐源，默认为netease
            size: 图片尺寸，可选300（默认）、500

        Returns:
            {
                "url": "专辑图链接"
            }
        """
        if source not in self.supported_sources:
            raise ValueError(f"不支持的音乐源: {source}")

        if size not in [300, 500]:
            raise ValueError(f"不支持的图片尺寸: {size}")

        params = {
            "types": "pic",
            "source": source,
            "id": pic_id,
            "size": size
        }

        response = self.session.get(self.base_url, params=params)
        response.raise_for_status()
        return response.json()

    def get_lyrics(
        self,
        lyric_id: str,
        source: str = "netease",
        **kwargs
    ) -> Dict[str, Any]:
        """
        获取歌词

        Args:
            lyric_id: 歌词ID
            source: 音乐源，默认为netease

        Returns:
            {
                "lyric": "LRC格式的原语种歌词",
                "tlyric": "LRC格式的中文翻译歌词（不一定会返回）"
            }
        """
        if source not in self.supported_sources:
            raise ValueError(f"不支持的音乐源: {source}")

        params = {
            "types": "lyric",
            "source": source,
            "id": lyric_id
        }

        response = self.session.get(self.base_url, params=params)
        response.raise_for_status()
        return response.json()

    def search_album_tracks(
        self,
        keyword: str,
        source: str = "netease",
        count: int = 20,
        pages: int = 1,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        搜索专辑中的曲目列表（高级用法）

        Args:
            keyword: 关键字，可以是专辑名
            source: 音乐源，使用_album后缀，如netease_album
            count: 页面长度，默认为20条
            pages: 页码，默认为第1页

        Returns:
            包含专辑曲目列表的字典列表
        """
        # 检查是否为专辑搜索格式
        if not source.endswith("_album"):
            source = f"{source}_album"

        if not any(source.startswith(s) or source.startswith(f"{s}_album") for s in self.supported_sources):
            raise ValueError(f"不支持的音乐源: {source}")

        params = {
            "types": "search",
            "source": source,
            "name": keyword,
            "count": count,
            "pages": pages
        }

        response = self.session.get(self.base_url, params=params)
        response.raise_for_status()
        return response.json()

    def download_song(
        self,
        track_id: str,
        source: str = "netease",
        br: int = 999,
        file_path: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        下载歌曲

        Args:
            track_id: 曲目ID
            source: 音乐源，默认为netease
            br: 音质，可选128、192、320、740、999（默认），其中740、999为无损音质
            file_path: 保存文件路径，如果为None则自动生成

        Returns:
            保存的文件路径
        """
        # 获取歌曲链接
        song_info = self.get_song_url(track_id, source, br)
        song_url = song_info.get('url')

        if not song_url:
            raise ValueError("无法获取歌曲下载链接")

        # 如果没有指定文件路径，则生成默认文件名
        if file_path is None:
            file_path = f"{track_id}.mp3"

        # 下载歌曲
        response = self.session.get(song_url, stream=True)
        response.raise_for_status()

        # 保存文件
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return file_path

    def download_album_art(
        self,
        pic_id: str,
        source: str = "netease",
        size: int = 500,
        file_path: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        下载专辑图

        Args:
            pic_id: 专辑图ID
            source: 音乐源，默认为netease
            size: 图片尺寸，可选300（默认）、500
            file_path: 保存文件路径，如果为None则自动生成

        Returns:
            保存的文件路径
        """
        # 获取专辑图链接
        album_art_info = self.get_album_art(pic_id, source, size)
        album_art_url = album_art_info.get('url')

        if not album_art_url:
            raise ValueError("无法获取专辑图下载链接")

        # 如果没有指定文件路径，则生成默认文件名
        if file_path is None:
            file_path = f"{pic_id}.jpg"

        # 下载专辑图
        response = self.session.get(album_art_url, stream=True)
        response.raise_for_status()

        # 保存文件
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return file_path

    def download_lyrics(
        self,
        lyric_id: str,
        source: str = "netease",
        file_path: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        下载歌词

        Args:
            lyric_id: 歌词ID
            source: 音乐源，默认为netease
            file_path: 保存文件路径，如果为None则自动生成

        Returns:
            保存的文件路径
        """
        # 获取歌词内容
        lyrics_info = self.get_lyrics(lyric_id, source)
        lyric_content = lyrics_info.get('lyric', '')
        tlyric_content = lyrics_info.get('tlyric', '')

        # 如果没有指定文件路径，则生成默认文件名
        if file_path is None:
            file_path = f"{lyric_id}.lrc"

        # 合并歌词和翻译歌词
        full_lyrics = lyric_content
        if tlyric_content:
            full_lyrics += "\n" + tlyric_content

        # 保存歌词到文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(full_lyrics)

        return file_path


# 使用示例
if __name__ == "__main__":
    # 创建API客户端实例
    client = GDAPIClient()

    # 示例1: 搜索音乐
    print("=== 搜索音乐示例 ===")
    try:
        search_result = client.search("青花瓷", source="netease", count=5)
        print(f"搜索结果: {search_result}")
    except Exception as e:
        print(f"搜索失败: {e}")

    # 示例2: 获取歌曲链接 (需要先搜索获取track_id)
    print("\n=== 获取歌曲链接示例 ===")
    try:
        # 从之前的搜索结果中获取一个有效的track_id
        search_result = client.search("青花瓷", source="netease", count=1)
        if isinstance(search_result, list) and len(search_result) > 0:
            track_id = search_result[0]['id']
            song_url = client.get_song_url(track_id, source="netease", br=320)
            print(f"歌曲链接: {song_url}")
        else:
            print("未能获取有效的搜索结果")
    except Exception as e:
        print(f"获取歌曲链接失败: {e}")

    # 示例3: 获取专辑图 (需要先搜索获取pic_id)
    print("\n=== 获取专辑图示例 ===")
    try:
        # 从之前的搜索结果中获取一个有效的pic_id
        search_result = client.search("青花瓷", source="netease", count=1)
        if isinstance(search_result, list) and len(search_result) > 0:
            pic_id = search_result[0]['pic_id']
            album_art = client.get_album_art(pic_id, source="netease", size=500)
            print(f"专辑图链接: {album_art}")
        else:
            print("未能获取有效的搜索结果")
    except Exception as e:
        print(f"获取专辑图失败: {e}")

    # 示例4: 获取歌词 (需要先搜索获取lyric_id)
    print("\n=== 获取歌词示例 ===")
    try:
        # 从之前的搜索结果中获取一个有效的lyric_id
        search_result = client.search("青花瓷", source="netease", count=1)
        if isinstance(search_result, list) and len(search_result) > 0:
            lyric_id = search_result[0]['lyric_id']
            lyrics = client.get_lyrics(lyric_id, source="netease")
            print(f"歌词: {lyrics}")
        else:
            print("未能获取有效的搜索结果")
    except Exception as e:
        print(f"获取歌词失败: {e}")

    # 示例5: 搜索专辑中的曲目
    print("\n=== 搜索专辑曲目示例 ===")
    try:
        album_tracks = client.search_album_tracks("周杰伦", source="netease", count=5)
        print(f"专辑曲目: {album_tracks}")
    except Exception as e:
        print(f"搜索专辑曲目失败: {e}")
