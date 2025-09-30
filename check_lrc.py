import os, sys

check_path = 'Z:/shared/music/zzh'
# check_path = 'D:/Profiles/Downloads/music'

class FileMarker:
    MUSIC_EXT = set(['mp3', 'flac', 'aac', 'ogg', 'wav', 'm4a', 'm4s'])
    LYRIC_EXT = 'lrc'

    def __init__(self) -> None:
        self.lyric_files: set[str] = set()
        self.music_files: set[str] = set()

    def mark(self, fn: str):
        fn_part = fn.rsplit('.', 1)
        if len(fn_part) < 2:
            print('unsupported file: {}'.format(fn))
            return

        file_name, file_ext = fn_part
        
        if file_ext in self.MUSIC_EXT:
            self.music_files.add(file_name)
        elif file_ext == self.LYRIC_EXT:
            self.lyric_files.add(file_name)
        else:
            print('unsupported file: {}, ext: {}'.format(fn, file_ext))

    def get_res(self):
        return self.music_files - self.lyric_files, self.lyric_files - self.music_files
    
    def get_music(self):
        return self.music_files
    
    def get_lyric(self):
        return self.lyric_files
    
def name_hd(name: str):
    name = name.replace('-', ' ')
    return name + '\n'

def main():
    marker = FileMarker()
    for fn in os.listdir(check_path):
        marker.mark(fn)

    music_no_lrc, lrc_no_music = marker.get_res()
    music_has_lrc = marker.get_music() - music_no_lrc

    with open('music_no_lrc.txt', 'w', encoding='utf-8') as f:
        f.writelines(map(name_hd, music_no_lrc))

    with open('lrc_no_music.txt', 'w', encoding='utf-8') as f:
        f.writelines(map(name_hd, lrc_no_music))

    with open('music_has_lrc.txt', 'w', encoding='utf-8') as f:
        f.writelines(map(name_hd, music_has_lrc))

    with open('all_music.txt', 'w', encoding='utf-8') as f:
        f.writelines(map(name_hd, music_has_lrc))
        f.writelines(map(name_hd, music_no_lrc))

    # print('music_no_lrc:', music_no_lrc)
    # print('lrc_no_music:', lrc_no_music)
    # print('music_has_lrc:', music_has_lrc)
        


if __name__ == '__main__':
    main()
