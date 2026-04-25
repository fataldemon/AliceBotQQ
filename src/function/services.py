import asyncio
from typing import Optional

import src.skills.game_status_process as game
from src.dao.status import move_position, move_default_position, \
    get_available_move_targets, get_available_railway_targets, get_available_areas, get_available_schools
from src.skills.code_running import run_in_sandbox
from src.skills.game_development import read_code_file, write_file, list_code_files
from src.skills.interactive_sandbox import InteractiveCodeSandbox, _sessions
from src.skills.online_search import online_search_func, access_page_func
from src.skills.git_service import git_command_service


def hikari_yo(target: str) -> str:
    game.add_death_list(target)
    return f"（“光之剑”发射出耀眼的光芒，{target}受到了100点伤害，{target}被打倒了。）"


# def move_random(to: str) -> str:
#     if to != "":
#         game.set_field(to)
#         return f"（爱丽丝现在来到了“{to}”场景。）"
#     else:
#         game.set_field("千禧年校园")
#         return f"（爱丽丝现在来到了“千禧年校园”场景。）"

# 移动场景
def move(option: str) -> str:
    if option == 'E' or option == 'H' or option == 'S' or option.isdigit():
        if option == 'E':
            result_info = move_position(-1)
        elif option == 'H':
            result_info = move_position(-2)
        elif option == 'S':
            result_info = move_position(-3)
        else:
            print(f'option={option}, available={get_available_move_targets()}, ',
                  option in get_available_move_targets())
            if option not in get_available_move_targets():
                return "从当前地点没有去往目标地点的道路，请选择其他选项！"
            option_id = int(option)
            result_info = move_position(option_id)
    else:
        result_info = "不存在的地点。选项参数必须是一个整数数字或者E或者H！"
    return result_info


# 铁道直达
def take_railway(option: str) -> str:
    if option.isdigit():
        if option not in get_available_railway_targets():
            return "从当前站点无法通向目标地点，请选择其他选项！"
        option_id = int(option)
        result_info = f"通过搭乘列车，{move_position(option_id)}"
    else:
        result_info = "不存在的站点。选项参数必须是一个整数数字！"
    return result_info


def decide_area(option: str) -> str:
    if option == 'E' or option == 'H' or option == 'S' or option.isdigit():
        if option == 'E':
            return "[EXIT_SCHOOL]"
        elif option == 'H':
            result_info = move_position(-2)
            return result_info
        elif option == 'S':
            result_info = move_position(-3)
            return result_info
        else:
            if option not in get_available_areas():
                return "从当前地点没有去往目标区域的道路！"
            warning = move_default_position(0, option)
            if warning == "[System]该地点目前无法进入。":
                return warning
            else:
                return option
    else:
        return "不存在的区域。选项参数必须是一个整数数字或者E或者H！"


def decide_school(option: str) -> str:
    if option == 'H' or option == 'S' or option.isdigit():
        if option == 'H':
            result_info = move_position(-2)
            return result_info
        elif option == 'S':
            result_info = move_position(-3)
            return result_info
        else:
            if option not in get_available_schools():
                return "从当前地点没有去往目标校区的道路！"
            warning = move_default_position(option, 0)
            if warning == "该地点目前无法进入。":
                return warning
            else:
                return option
    else:
        return "不存在的校区。选项参数必须是一个整数数字或者H！"


def search_for_item() -> str:
    return f"（爱丽丝花费时间进行了一番搜索，但是一无所获。或许这里应该暂且放弃。）"


async def search_on_internet(item: str) -> str:
    raw_info, url_list = await online_search_func(item)
    info = f"（爱丽丝在网络上对〖{item}〗词条进行了一番搜索，得到了一些信息）{raw_info}"
    if raw_info != "" and raw_info != "ERROR" and raw_info != "其他网站的摘要信息：\n":
        print(raw_info)
        return info
    elif raw_info == "ERROR" or raw_info == "其他网站的摘要信息：\n":
        print(raw_info)
        return f"（爱丽丝在网络上对〖{item}〗词条进行了一番搜索，但是由于网络问题什么都没能找到。也许之后再试试吧。）"
    else:
        return f"（爱丽丝在网络上对〖{item}〗词条进行了一番搜索，但是由于网络问题什么都没能找到。也许之后再试试吧。）"


async def access_website(url: str):
    page_text, page_links, page_image = await access_page_func(url)
    if page_image is not None:
        return f"（爱丽丝访问了网页{url}，得到了以下内容）\n网页截图：[image,base64={page_image}]\n网页链接：{page_links}"
    else:
        return f"（爱丽丝对{url}的访问似乎因为网络不佳的原因失败了...）"


async def run_code_in_sandbox(language: str, code: str):
    """
    在安全沙盒中执行 Python 或 Bash 代码，返回执行结果。

    参数:
        language: "python" 或 "bash"
        code: 要执行的代码字符串
    """
    # 因为 run_in_sandbox 是同步函数，在异步环境中需要用线程池执行
    loop = asyncio.get_running_loop()
    stdout, stderr, exit_code = await loop.run_in_executor(
        None, run_in_sandbox, language, code
    )

    # 根据执行结果构造返回消息
    if exit_code == 0:
        # 成功执行：返回标准输出和可能的错误输出（如果有）
        if stdout and stderr:
            return f"（爱丽丝的代码执行成功了！）\n<标准输出>：\n{stdout}\n<标准错误>：\n{stderr}"
        elif stdout:
            return f"（爱丽丝的代码执行成功了！）\n<标准输出>：\n{stdout}"
        elif stderr:
            return f"（爱丽丝的代码执行成功了！）\n<标准错误>：\n{stderr}"
        else:
            return "（爱丽丝的代码执行成功了，只是没有任何输出）"
    elif exit_code is None:
        # 超时或被强制终止
        return f"（爱丽丝的代码执行超时或因异常终止了！）\n<错误信息>：\n{stderr}"
    else:
        # 执行失败（非零退出码）
        return f"（爱丽丝的代码执行失败了！退出码 {exit_code}）\n<标准输出>：{stdout}\n<标准错误>：{stderr}"


async def write_file_service(filename: str, content: str) -> str:
    """
    异步写入/覆盖任意类型的文件到 ./game_workspace 目录
    """
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, write_file, filename, content)

    if result["success"]:
        return f"（成功写入文件）\n{result['message']}"
    else:
        return f"（写入文件失败）\n{result['message']}"


async def list_code_files_service(extension: Optional[str] = None) -> str:
    """
    异步列出 ./game_workspace 目录下的代码文件列表
    """
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, list_code_files, extension)

    if result["success"]:
        files = result["data"]
        if files:
            file_list = "\n".join(f"  - {f}" for f in files)
            return f"（成功获取文件列表，共 {len(files)} 个文件）\n<文件列表>：\n{file_list}"
        else:
            return f"（成功获取文件列表，但目录为空）\n<文件列表>：\n（无文件）"
    else:
        return f"（列出文件失败）\n{result['message']}"


async def read_code_file_service(filename: str) -> str:
    """
    异步读取 ./game_workspace 目录下指定文件的内容
    """
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, read_code_file, filename)

    if result["success"]:
        content = result["data"]
        # 如果内容过长可以截断，这里直接返回
        return f"（成功读取文件 '{filename}'）\n<文件内容>：\n{content}"
    else:
        return f"（读取文件失败）\n{result['message']}"


# 单例：当前活动的会话
_current_session = None
_current_session_id = None


async def start_interactive_code(language: str, code: str) -> str:
    """
    启动一个交互式代码会话（会关闭之前的会话），并返回初始输出。
    """
    global _current_session, _current_session_id
    loop = asyncio.get_running_loop()

    # 关闭已有会话
    if _current_session:
        try:
            await loop.run_in_executor(None, _current_session.close)
        except:
            pass
        _current_session = None
        _current_session_id = None

    try:
        session_id = f"code_{int(asyncio.get_event_loop().time())}_{hash(code) % 10000}"
        sandbox = InteractiveCodeSandbox(language=language, code=code)
        await loop.run_in_executor(None, sandbox.start)
        _current_session = sandbox
        _current_session_id = session_id

        # 等待并获取初始输出
        output = await loop.run_in_executor(None, sandbox.wait_for_output, 10)
        if output:
            return f"（成功启动交互式代码会话，会话ID: {session_id}）\n<初始输出>：\n{output}"
        else:
            return f"（成功启动交互式代码会话，会话ID: {session_id}）\n（程序暂无输出，可能等待输入）"
    except Exception as e:
        _current_session = None
        _current_session_id = None
        return f"（启动交互式代码会话失败）\n错误信息：{str(e)}"


async def send_interactive_input(user_input: str) -> str:
    """
    向当前活动会话发送输入，并返回程序的新输出。
    如果没有活动会话，返回错误提示。
    """
    global _current_session
    loop = asyncio.get_running_loop()

    if not _current_session:
        return "（发送输入失败）\n当前没有运行中的会话，请先调用 start_interactive_code 启动会话。"

    try:
        await loop.run_in_executor(None, _current_session.send_input, user_input)
        await asyncio.sleep(0.3)  # 等待程序处理
        output = await loop.run_in_executor(None, _current_session.read_output)
        if output:
            return f"（成功发送输入）\n输入内容：{user_input}\n<程序输出>：\n{output}"
        else:
            return f"（成功发送输入）\n输入内容：{user_input}\n（程序没有产生输出，可能已结束或仍在处理）"
    except Exception as e:
        return f"（发送输入失败）\n错误信息：{str(e)}"


async def close_current_session() -> str:
    """关闭当前活动会话并释放资源"""
    global _current_session, _current_session_id
    if not _current_session:
        return "（关闭会话）\n当前没有活动会话。"

    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, _current_session.close)
        _current_session = None
        _current_session_id = None
        return "（已关闭当前交互式会话，资源已清理）"
    except Exception as e:
        return f"（关闭会话时出错）\n错误信息：{str(e)}"


