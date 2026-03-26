from src.dao.status import find_route, check_railway, get_available_functions, set_available_functions
import src.function.functions as func
import src.function.services as serv


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
        format_move(func.func_move, steps=0, school_id=0, area_id=0)
    ]
    available_actions = "[sword_of_light],[search_on_internet],[move]"
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


async def skill_call(action: str, action_input: dict) -> str:
    print(get_available_functions(), f"=>[{action}]")
    if f"[{action}]" not in get_available_functions():
        return f"当前不存在可使用的技能{action}！"
    if action == "sword_of_light":
        target = action_input.get("target")
        if target is not None:
            call_result = serv.hikari_yo(target)
        else:
            call_result = "光之剑必须指定一个目标！"
    # elif action == "move":
    #     to = action_input.get("to")
    #     if to is not None:
    #         result = move(to)
    #     else:
    #         result = move("")
    elif action == "move":
        options = action_input.get("options")
        if options is not None:
            call_result = serv.move(options)
        else:
            call_result = "必须选择一个希望前往的地点！"
    elif action == "decide_area":
        options = action_input.get("options")
        if options is not None:
            call_result = serv.decide_area(options)
        else:
            call_result = "必须选择一个希望前往的区域！"
    elif action == "decide_school":
        options = action_input.get("options")
        if options is not None:
            call_result = serv.decide_school(options)
        else:
            call_result = "必须选择一个希望前往的校区！"
    elif action == "take_railway":
        options = action_input.get("options")
        if options is not None:
            call_result = serv.take_railway(options)
        else:
            call_result = "必须选择一个希望前往的站点！"
    elif action == "search_for_item":
        call_result = serv.search_for_item()
    elif action == "search_on_internet":
        query = action_input.get("query")
        if query is not None:
            call_result = await serv.search_on_internet(query)
        else:
            call_result = "查询参数不能为空！"
    else:
        call_result = f"当前不存在可使用的技能{action}！"
    return str(call_result)



