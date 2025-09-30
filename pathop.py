import os, sys

def get_cwd():
    return os.path.abspath(os.curdir if len(sys.argv) == 1 else sys.argv[1])

def dump_dir(path: str, suffix: str = ''):
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(suffix):
                yield os.path.join(root, file)
