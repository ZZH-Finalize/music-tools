import os, sys
import pathop

cwd = pathop.get_cwd()

def main():
    for file in pathop.dump_dir(cwd, '.wav'):
        if not os.path.exists(file.removesuffix('.wav') + '.mp3'):
            print(file, 'does not have mp3')

if __name__ == '__main__':
    main()
    print('Done.')
    input()
