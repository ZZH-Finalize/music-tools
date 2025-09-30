import os, sys
import pathop

cwd = pathop.get_cwd()

def do_convert(output: str, input: str, *args: str, bitrate: str = '320k', encoder: str = 'libmp3lame'):
    print('convert {} to {}'.format(input, output))

    cmd = 'ffmpeg'

    for arg in args:
        cmd += ' ' + arg

    cmd += f' -i "{input}" -codec:a {encoder} -b:a {bitrate} "{output}"'

    print('exec: ', cmd)
    os.system(cmd)

def main() -> None:
    if False == os.path.exists(cwd):
        raise RuntimeError('path: {} does not exists!'.format(cwd))
    
    for file in pathop.dump_dir(cwd, '.wav'):
        output_name = file.removesuffix('wav') + 'mp3'
        do_convert(output_name, file)

if __name__ == '__main__':
    main()
