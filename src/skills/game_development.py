import os

WORKSPACE = "/game_workspace"


def ensure_workspace():
    """确保工作目录存在，若不存在则创建"""
    os.makedirs(WORKSPACE, exist_ok=True)


def write_file(filename: str, content: str) -> dict:
    """
    在 game_workspace 目录下写入（或覆盖）任意类型的文件。
    参数:
        filename: 文件名（可包含扩展名，如 'script.py', 'data.json', 'config.txt'），不允许包含路径分隔符或 '..'
        content: 文件内容字符串
    返回:
        dict: {"success": bool, "message": str}
    """
    if not filename or not isinstance(filename, str):
        return {"success": False, "message": "文件名无效"}
    if os.path.sep in filename or (os.path.altsep and os.path.altsep in filename) or ".." in filename:
        return {"success": False, "message": "文件名包含非法字符，不能包含路径分隔符或 '..'"}

    try:
        ensure_workspace()
        file_path = os.path.join(WORKSPACE, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"success": True, "message": f"文件 '{filename}' 写入成功"}
    except Exception as e:
        return {"success": False, "message": f"写入文件失败: {str(e)}"}


def list_code_files(extension: str = None) -> dict:
    """
    列出 /game_workspace 下的代码文件（普通文件，不包含子目录）。
    参数:
        extension: 可选，文件扩展名过滤，例如 '.py' 只返回 Python 文件，默认 None 返回所有文件
    返回:
        dict: {"success": bool, "data": list, "message": str}
    """
    try:
        ensure_workspace()
        all_items = os.listdir(WORKSPACE)
        files = []
        for item in all_items:
            item_path = os.path.join(WORKSPACE, item)
            if os.path.isfile(item_path):
                if extension is None or item.endswith(extension):
                    files.append(item)
        return {"success": True, "data": files, "message": f"成功获取 {len(files)} 个文件"}
    except Exception as e:
        return {"success": False, "data": [], "message": f"列出文件失败: {str(e)}"}


def read_code_file(filename: str) -> dict:
    """
    读取 /game_workspace 下指定文件的内容。
    参数:
        filename: 文件名（不允许包含路径分隔符或 '..'）
    返回:
        dict: {"success": bool, "data": str, "message": str}
    """
    if not filename or not isinstance(filename, str):
        return {"success": False, "data": "", "message": "文件名无效"}
    if os.path.sep in filename or (os.path.altsep and os.path.altsep in filename) or ".." in filename:
        return {"success": False, "data": "", "message": "文件名包含非法字符"}

    try:
        ensure_workspace()
        file_path = os.path.join(WORKSPACE, filename)
        if not os.path.exists(file_path):
            return {"success": False, "data": "", "message": f"文件 '{filename}' 不存在"}
        if not os.path.isfile(file_path):
            return {"success": False, "data": "", "message": f"'{filename}' 不是一个文件"}
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"success": True, "data": content, "message": "读取成功"}
    except Exception as e:
        return {"success": False, "data": "", "message": f"读取文件失败: {str(e)}"}


# ---------- 使用示例 ----------
if __name__ == "__main__":
    # 1. 写入 Python 文件
    result_write = write_file("hello.py", "print('Hello from AI!')\nprint('Workspace ready.')")
    print(result_write)

    # 2. 列出所有代码文件
    result_list = list_code_files()
    print(result_list)

    # 3. 查看文件内容
    result_read = read_code_file("hello.py")
    if result_read["success"]:
        print("文件内容:\n", result_read["data"])
    else:
        print("读取失败:", result_read["message"])