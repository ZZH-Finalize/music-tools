import pathop
import auto_rename
import os
import shutil

def get_file_basename(file_path):
    """获取文件的基础名称（不含扩展名）"""
    return os.path.splitext(os.path.basename(file_path))[0]

class CopyOperation:
    def __init__(self, src_file, dst_file, replaced_files=None):
        self.src_file = src_file
        self.dst_file = dst_file
        self.replaced_files = replaced_files or []

    def __str__(self):
        if self.replaced_files:
            return f"copy {os.path.basename(self.src_file)} (replace {', '.join([os.path.basename(f) for f in self.replaced_files])})\n"
        else:
            return f"copy {os.path.basename(self.src_file)}\n"

    def exec(self):
        print(f"复制文件: {self.src_file} -> {self.dst_file}")
        shutil.copy2(self.src_file, self.dst_file)

class DeleteOperation:
    def __init__(self, file_to_delete):
        self.file_to_delete = file_to_delete

    def __str__(self):
        return f"delete {os.path.basename(self.file_to_delete)}"

    def exec(self):
        print(f"删除文件: {self.file_to_delete}")
        os.remove(self.file_to_delete)

def do_copy(ref_path, mod_path):
    ref_files = list(pathop.dump_dir(ref_path))
    mod_files = list(pathop.dump_dir(mod_path))

    # 过滤音乐文件
    ref_music_files = auto_rename.filter_music_files(ref_files)
    mod_music_files = auto_rename.filter_music_files(mod_files)

    # 创建mod_path下文件名到文件路径的映射
    mod_name_to_path = {}
    for mod_file in mod_music_files:
        basename = get_file_basename(mod_file)
        if basename not in mod_name_to_path:
            mod_name_to_path[basename] = []
        mod_name_to_path[basename].append(mod_file)

    # 第一步：创建操作对象并放入list
    operations = []

    # 遍历参考路径下的音乐文件
    for ref_file in ref_music_files:
        ref_basename = get_file_basename(ref_file)

        # 检查mod_path下是否有相同基础名称的文件
        if ref_basename in mod_name_to_path:
            # 存在相同基础名称的文件，需要替换
            existing_files = mod_name_to_path[ref_basename]
            for existing_file in existing_files:
                # 删除mod_path下相同基础名称的文件
                operations.append(DeleteOperation(existing_file))

            # 复制ref_path下的文件到mod_path
            target_path = os.path.join(mod_path, os.path.basename(ref_file))
            operations.append(CopyOperation(ref_file, target_path, existing_files))
        else:
            # 没有相同基础名称的文件，直接复制
            target_path = os.path.join(mod_path, os.path.basename(ref_file))
            operations.append(CopyOperation(ref_file, target_path))

    # 第二步：遍历list打印操作
    for op in operations:
        print(op)

    # 等待用户确认
    user_input = input("确认执行以上操作? (y/N): ")
    if user_input.lower() != 'y':
        print("操作已取消")
        return

    # 第三步：执行操作
    for op in operations:
        op.exec()

def main():
    ref_path, mod_path, _ = auto_rename.parse_arg()
    do_copy(ref_path, mod_path)

if __name__ == '__main__':
    main()
