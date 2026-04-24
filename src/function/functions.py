# 调用工具格式定义
func_sword_of_light = {
        'name': 'sword_of_light',
        'description': '使用电磁炮“光之剑”发起攻击',
        'parameters': {
            'type': 'object',
            'properties': {
                'target': {
                    'type': 'string',
                    'description':
                    '攻击目标的名字',
                },
            },
            'required': ['target'],
        },
    }
func_move_random = {
        'name': 'move',
        'description': '离开当前场景，前往其他地点',
        'parameters': {
            'type': 'object',
            'properties': {
                'to': {
                    'type': 'string',
                    'description':
                    '接下来要前往的场景或地点的名称',
                },
            },
            'required': ['to'],
        },
    }
func_search_for_item = {
        'name': 'search_for_item',
        'description': '道具搜索',
        'parameters': {
            'type': 'object',
            'properties': {
                'object': {
                    'type': 'string',
                    'description':
                    '指定具体的搜索对象，例如宝箱、房屋、垃圾箱等',
                },
            },
            'required': ['object'],
        },
    }
func_search_on_internet = {
        'name': 'search_on_internet',
        'description': '上网搜索、查找相关信息',
        'parameters': {
            'type': 'query',
            'properties': {
                'query': {
                    'type': 'string',
                    'description':
                    '需要查找信息的条目',
                },
            },
            'required': ['query'],
        },
    }
func_move = {
        'name': 'move',
        'description': '离开当前场景，出发前往其他地点（步行）',
        'parameters': {
            'type': 'object',
            'properties': {
                'options': {
                    'type': 'string',
                    'description':
                    '可以前往的地点选项：\n'
                    '{OPTIONS}',
                },
            },
            'required': ['options'],
        },
    }
func_decide_area = {
        'name': 'decide_area',
        'description': '决定前往哪个区域',
        'parameters': {
            'type': 'object',
            'properties': {
                'options': {
                    'type': 'string',
                    'description':
                    '可以前往的区域选项：\n'
                    '{OPTIONS}',
                },
            },
            'required': ['options'],
        },
    }
func_decide_school = {
        'name': 'decide_school',
        'description': '决定前往哪个校区',
        'parameters': {
            'type': 'object',
            'properties': {
                'options': {
                    'type': 'string',
                    'description':
                    '可以前往的校区选项：\n'
                    '{OPTIONS}',
                },
            },
            'required': ['options'],
        },
    }
func_railway = {
        'name': 'take_railway',
        'description': '搭乘列车，出发前往其他站点',
        'parameters': {
            'type': 'object',
            'properties': {
                'options': {
                    'type': 'string',
                    'description':
                    '通过列车轨道可以直达的地点选项：\n'
                    '{OPTIONS}',
                },
            },
            'required': ['options'],
        },
    }
func_walk = {
        'name': 'walk',
        'description': '在当前场景内走动（改变位置）',
        'parameters': {
            'type': 'object',
            'properties': {
                'to': {
                    'type': 'string',
                    'description':
                    '行动至某个位置，用一个数字表示（取值范围在0-{SIZE}之间）',
                },
            },
            'required': ['to'],
        },
    }
func_access_website = {
        'name': 'access_website',
        'description': '调用浏览器访问网页地址，查看具体信息',
        'parameters': {
            'type': 'object',
            'properties': {
                'url': {
                    'type': 'string',
                    'description':
                    '访问的互联网网页URL地址',
                },
            },
            'required': ['url'],
        },
    }
func_run_code = {
    "name": "run_code_in_sandbox",
    "description": "在安全的沙盒环境中运行 Python 或 Bash 代码，返回标准输出、错误输出和退出码。适用于隔离运行用户提供的动态代码片段。运行目录在/workspace，其中包含了在工作空间里的所有文件。",
    "parameters": {
        "type": "object",
        "properties": {
            "language": {
                "type": "string",
                "enum": ["python", "bash"],
                "description": "要执行的代码语言，支持 python 或 bash"
            },
            "code": {
                "type": "string",
                "description": "要执行的代码字符串，例如 'print(\"Hello\")' 或 'echo \"Hello\"'"
            }
        },
        "required": ["language", "code"]
    }
}
func_write_file = {
    "name": "write_file",
    "description": "在 /game_workspace 目录下写入或覆盖任意类型的文件（如 .py, .json, .txt, .html 等）。如果目录不存在则自动创建。返回操作成功或失败的信息。",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "要创建的文件名，可以包含扩展名，例如 'main.py'、'data.json'、'note.txt'。不允许包含路径分隔符或 '..'，以防止路径遍历攻击。"
            },
            "content": {
                "type": "string",
                "description": "要写入文件的完整内容（文本格式）。"
            }
        },
        "required": ["filename", "content"]
    }
}
func_list_code_files = {
    "name": "list_code_files",
    "description": "列出“游戏开发部”工作空间（目录）下的所有代码文件（仅普通文件，不包含子目录）。可以按文件扩展名过滤。",
    "parameters": {
        "type": "object",
        "properties": {
            "extension": {
                "type": "string",
                "description": "可选参数，只返回具有指定扩展名的文件，例如 '.py'。如果省略或为 null，则返回所有文件。",
                "default": None
            }
        },
        "required": []
    }
}
func_read_code_file = {
    "name": "read_code_file",
    "description": "读取“游戏开发部”工作空间（目录）下指定文件的完整内容。返回文件内容字符串或错误信息。",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "要读取的文件名，例如 'main.py'。不允许包含路径分隔符或 '..'。"
            }
        },
        "required": ["filename"]
    }
}
func_start_code_session = {
    "name": "start_code_session",
    "description": "启动一个交互式代码会话，运行指定的代码（支持 input() 交互）。返回会话ID。",
    "parameters": {
        "type": "object",
        "properties": {
            "language": {"type": "string", "enum": ["python", "bash"]},
            "code": {"type": "string", "description": "要运行的完整代码字符串"}
        },
        "required": ["language", "code"]
    }
}
func_read_code_output = {
    "name": "read_code_output",
    "description": "读取会话中程序当前的输出。如果 wait=true，则等待直到有输出（适合等待游戏提示）。",
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "wait": {"type": "boolean"},
            "timeout": {"type": "integer"}
        },
        "required": ["session_id"]
    }
}
func_send_code_input = {
    "name": "send_code_input",
    "description": "向会话中的程序发送一行用户输入（例如游戏中的答案），并返回程序的新输出。",
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "user_input": {"type": "string"}
        },
        "required": ["session_id", "user_input"]
    }
}
func_close_code_session = {
    "name": "close_code_session",
    "description": "结束代码会话，释放容器资源。",
    "parameters": {
        "type": "object",
        "properties": {"session_id": {"type": "string"}},
        "required": ["session_id"]
    }
}
func_git_command = {
    "name": "git_command",
    "description": "在固定工作空间（WORKSPACE）下执行安全的 git 命令。支持常见的 git 操作，如 status, log, diff, branch, add, commit, pull, push 等。禁止执行其他系统命令。",
    "parameters": {
        "type": "object",
        "properties": {
            "git_command": {
                "type": "string",
                "description": "完整的 git 命令，例如 'git status' 或 'git log --oneline -5'"
            },
            "timeout": {
                "type": "integer",
                "description": "命令超时时间（秒），默认30",
                "default": 30
            }
        },
        "required": ["git_command"]
    }
}

