# services/git_service.py
import asyncio
import subprocess
import shlex
import re
from pathlib import Path

# 从配置导入 WORKSPACE 路径（或直接定义）
from src.skills.game_development import WORKSPACE  # 假设你有这个配置，或者从 interactive_sandbox 导入


def is_safe_git_command(command: str) -> bool:
    """
    检查 git 命令是否安全，忽略引号内的内容（如提交消息）。
    - 允许管道 |、逻辑 && ||、后台 &、输入重定向 <
    - 允许环境变量、git -c 参数
    - 允许只读系统命令（head, grep, cat, echo 等）
    - 禁止引号外的：命令分隔符 ; ；命令替换 ` $() ；输出重定向 > >>
    - 禁止危险写入命令（rm, mv, cp, tee, curl, wget, dd 等）
    """
    def remove_quoted_content(s: str) -> str:
        """将单引号或双引号内的内容替换为空格（保留引号对本身）"""
        result = []
        i = 0
        n = len(s)
        while i < n:
            ch = s[i]
            # 双引号块（支持转义）
            if ch == '"':
                result.append(ch)      # 保留开引号
                i += 1
                while i < n and s[i] != '"':
                    if s[i] == '\\' and i + 1 < n:  # 跳过转义字符
                        result.append(' ')
                        result.append(' ')
                        i += 2
                    else:
                        result.append(' ')
                        i += 1
                if i < n and s[i] == '"':
                    result.append(ch)  # 保留闭引号
                    i += 1
            # 单引号块（不支持转义）
            elif ch == "'":
                result.append(ch)
                i += 1
                while i < n and s[i] != "'":
                    result.append(' ')
                    i += 1
                if i < n and s[i] == "'":
                    result.append(ch)
                    i += 1
            else:
                result.append(ch)
                i += 1
        return ''.join(result)

    cmd = command.strip()
    if not cmd:
        return False

    # 移除了引号内内容后的字符串（保留引号位置，内部替换为空格）
    clean_cmd = remove_quoted_content(cmd)

    # 1. 禁止引号外的命令分隔符和命令替换
    if re.search(r'[;`]|\$\(', clean_cmd):
        return False

    # 2. 禁止引号外的输出重定向 > 或 >>
    if re.search(r'(?<![<>])>(?!>)|>>', clean_cmd):
        return False

    # 3. 禁止引号外的危险写入命令（常见破坏性工具）
    dangerous = re.compile(
        r'\b(rm|mv|cp|dd|tee|chmod|chown|chattr|kill|pkill|killall|'
        r'shutdown|reboot|halt|poweroff|mkfs|fdisk|curl|wget|'
        r'ssh|scp|rsync|nc|telnet|mount|umount|pkg|apt|yum|dnf|pip|npm|gem)\b',
        re.IGNORECASE
    )
    if dangerous.search(clean_cmd):
        return False

    # 通过所有检查
    return True


def run_git_command_sync(command: str, timeout: int = 30):
    """
    同步执行 git 命令，工作目录固定为 WORKSPACE。
    返回 (stdout, stderr, returncode)
    """
    if not is_safe_git_command(command):
        return "", f"不安全的 git 命令：{command}", 1

    try:
        result = subprocess.run(
            shlex.split(command),
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=timeout
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", f"命令执行超时（{timeout}秒）", 124
    except Exception as e:
        return "", f"执行出错：{str(e)}", 1


async def git_command_service(git_command: str, timeout: int = 30) -> str:
    """
    在 WORKSPACE 目录下执行安全的 git 命令，返回结果（AI 友好格式）。
    """
    loop = asyncio.get_running_loop()
    stdout, stderr, retcode = await loop.run_in_executor(
        None, run_git_command_sync, git_command, timeout
    )

    if retcode == 0:
        if stdout:
            return f"（Git 命令执行成功）\n<输出>：\n{stdout}"
        else:
            return f"（Git 命令执行成功，无输出）"
    else:
        error_msg = stderr if stderr else stdout
        return f"（Git 命令执行失败，退出码 {retcode}）\n<错误>：\n{error_msg}"