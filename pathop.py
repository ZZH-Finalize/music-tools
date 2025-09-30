import os, sys

def get_cwd():
    return os.path.abspath(os.curdir if len(sys.argv) == 1 else sys.argv[1])

def dump_dir(path: str, suffix: str = ''):
    """
    遍历指定路径下的所有文件，返回文件的完整路径
    :param path: 目录路径
    :param suffix: 文件后缀过滤器，为空则返回所有文件
    :return: 生成器，产生文件的完整路径
    """
    for root, _, files in os.walk(path):
        for file in files:
            if suffix == '' or file.endswith(suffix):
                yield os.path.join(root, file)
