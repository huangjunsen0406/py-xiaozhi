import os

# 需要排除的目录 & 文件（你可以自定义）
EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".venv",
    "build",
    "dist",
    "__pycache__",
    "desktop",
    "logs",
    "models",
    "documents",
}
EXCLUDED_FILES = {".DS_Store", "Thumbs.db"}


def print_directory_tree(start_path=".", indent=""):
    try:
        files = sorted(os.listdir(start_path))
    except PermissionError:
        return

    files = [f for f in files if f not in EXCLUDED_FILES]  # 过滤不需要的文件
    dirs = [
        d
        for d in files
        if os.path.isdir(os.path.join(start_path, d)) and d not in EXCLUDED_DIRS
    ]
    files = [f for f in files if os.path.isfile(os.path.join(start_path, f))]

    for index, file in enumerate(dirs + files):
        path = os.path.join(start_path, file)
        is_last = index == len(dirs + files) - 1
        prefix = "└── " if is_last else "├── "
        print(indent + prefix + file)

        if os.path.isdir(path):
            next_indent = indent + ("    " if is_last else "│   ")
            print_directory_tree(path, next_indent)


if __name__ == "__main__":
    print_directory_tree("..")
