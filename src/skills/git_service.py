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
    检查命令是否安全的 git 命令。
    只允许 git 开头，且不包含危险符号。
    """
    # 去除首尾空格
    cmd = command.strip()
    # 必须以 'git ' 开头（允许 git 子命令）
    if not cmd.startswith('git '):
        return False

    # 危险字符正则：&& || ; | > < $ ` \ ( ) & (多个命令分隔)
    if re.search(r'[;&|><$`]', cmd):
        return False

    # 禁止使用 -c 参数执行任意代码（git -c user.name='...' 可能被利用）
    if re.search(r'\s+-c\s+', cmd):
        return False

    # 禁止环境变量赋值
    if re.search(r'^[A-Za-z_][A-Za-z0-9_]*=', cmd):
        return False

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