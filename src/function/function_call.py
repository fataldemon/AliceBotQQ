import asyncio
from contextvars import ContextVar
from typing import List, Tuple, Callable, Dict, Union, Any
from langchain.llms.base import LLM

from src.dao.status import find_route, check_railway, get_available_functions, set_available_functions
import src.function.functions as func
import src.function.services as serv
from src.skills.context_params import current_group_id


def format_move(func_move, steps, school_id, area_id):
    desc = find_route(steps, school_id, area_id)
    func_move["parameters"]["properties"]["options"]["description"] = desc
    return func_move


def format_railway(func_railway):
    desc = find_route(5, 0, 0)
    func_railway["parameters"]["properties"]["options"]["description"] = desc
    return func_railway


def get_general_tools():
    functions = [
        func.func_sword_of_light,
        func.func_search_on_internet,
        format_move(func.func_move, steps=0, school_id=0, area_id=0),
        func.func_access_website,
        func.func_run_code,
        func.func_write_file,
        func.func_list_code_files,
        func.func_read_code_file,
        func.func_start_interactive_code,
        func.func_send_interactive_input,
        func.func_close_code_session,
        func.func_git_command,
        func.func_recall_memory
    ]
    available_actions = "[sword_of_light]," \
                        "[search_on_internet]," \
                        "[move],[access_website]," \
                        "[run_code_in_sandbox]," \
                        "[write_file]," \
                        "[read_code_file]," \
                        "[list_code_files]" \
                        "[start_interactive_code]," \
                        "[send_interactive_input]," \
                        "[close_current_session]" \
                        "[git_command]" \
                        "[recall_memory]"
    set_available_functions(available_actions)
    if check_railway():
        functions.append(format_railway(func.func_railway))
        set_available_functions(available_actions + ",[take_railway]")
    return functions


def move_tool(steps, school_id, area_id):
    if steps == 0:
        available_actions = "[move]"
        set_available_functions(available_actions)
        if area_id == 0:
            return [format_move(func.func_move, steps=0, school_id=0, area_id=0)]
        else:
            return [format_move(func.func_move, steps=4, school_id=0, area_id=area_id)]
    elif steps == 1:
        available_actions = "[decide_area]"
        set_available_functions(available_actions)
        if school_id == 0:
            return [format_move(func.func_decide_area, steps=1, school_id=0, area_id=0)]
        else:
            return [format_move(func.func_decide_area, steps=3, school_id=school_id, area_id=0)]
    elif steps == 2:
        available_actions = "[decide_school]"
        set_available_functions(available_actions)
        return [format_move(func.func_decide_school, steps=2, school_id=0, area_id=0)]


def make_handler(
        method_name: str,
        param_specs: List[Tuple[str, str]]  # [(参数名, 缺失时的错误信息), ...]
) -> Callable[[Dict], Union[str, Any]]:
    """
    创建一个技能处理器，每个参数可绑定独立的错误信息。
    :param method_name: serv 对象上的方法名
    :param param_specs: 参数规格列表，每个元素为 (参数名, 缺失错误消息)
    :return: 异步处理器函数 async (action_input) -> str
    """
    param_names = [p[0] for p in param_specs]
    error_msgs = {p[0]: p[1] for p in param_specs}  # 参数名 -> 错误消息

    async def handler(action_input: Dict) -> str:
        method = getattr(serv, method_name)

        # 按顺序提取参数值，遇到缺失立即返回对应的错误消息
        args = []
        for name in param_names:
            value = action_input.get(name)
            if value is None:
                return error_msgs[name]  # 返回该参数绑定的错误信息
            args.append(value)

        # 所有参数都已提供，调用方法（同步或异步）
        if asyncio.iscoroutinefunction(method):
            result = await method(*args)
        else:
            result = method(*args)
        return str(result)

    return handler


# 技能注册表
skill_handlers: Dict[str, Callable] = {
    "sword_of_light": make_handler("hikari_yo", [("target", "光之剑必须指定一个目标！")]),
    "move": make_handler("move", [("options", "必须选择一个希望前往的地点！")]),
    "decide_area": make_handler("decide_area", [("options", "必须选择一个希望前往的区域！")]),
    "decide_school": make_handler("decide_school", [("options", "必须选择一个希望前往的校区！")]),
    "take_railway": make_handler("take_railway", [("options", "必须选择一个希望前往的站点！")]),
    "search_for_item": make_handler("search_for_item", []),  # 无参技能
    "search_on_internet": make_handler("search_on_internet", [("query", "查询参数不能为空！")]),
    "access_website": make_handler("access_website", [("url", "URL地址不能为空！")]),
    "run_code_in_sandbox": make_handler("run_code_in_sandbox", [("language", "代码种类不能为空！"), ("code", "代码不能为空！")]),
    "write_file": make_handler("write_file_service", [("filename", "文件名不能为空！"), ("content", "文件内容不能为空！")]),
    "list_code_files": make_handler("list_code_files_service", []),   # 无必需参数
    "read_code_file": make_handler("read_code_file_service", [("filename", "文件名不能为空！")]),
    "start_interactive_code": make_handler("start_interactive_code", [("language", "语言不能为空"), ("code", "代码不能为空")]),
    "send_interactive_input": make_handler("send_interactive_input", [("user_input", "输入不能为空")]),
    "close_current_session": make_handler("close_current_session", []),
    "git_command": make_handler("git_command_service", [("git_command", "git 命令不能为空！")]),
    "recall_memory": make_handler("recall_memory", []),
}


async def skill_call(action: str, action_input: dict, group_id: str = "") -> str:
    # 设置上下文变量
    token = None
    if group_id:
        token = current_group_id.set(group_id)
    try:
        available = get_available_functions()
        if f"[{action}]" not in available:
            return f"当前不存在可使用的技能{action}！！"
        handler = skill_handlers.get(action)
        if handler is None:
            return f"当前不存在可使用的技能{action}！"
        return await handler(action_input)
    finally:
        if token:
            current_group_id.reset(token)