import src.skills.game_status_process as game
from src.skills.online_search import online_search_func
from src.dao.status import move_position, move_default_position, \
    get_available_move_targets, get_available_railway_targets, get_available_areas, get_available_schools


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
            print(f'option={option}, available={get_available_move_targets()}, ', option in get_available_move_targets())
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
    raw_info = await online_search_func(item)
    info = f"（爱丽丝在网络上对〖{item}〗词条进行了一番搜索，得到了一些信息）{raw_info}"
    if raw_info != "" and raw_info != "ERROR" and raw_info != "其他网站的摘要信息：\n":
        print(raw_info)
        return info
    elif raw_info == "ERROR" or raw_info == "其他网站的摘要信息：\n":
        print(raw_info)
        return f"（爱丽丝在网络上对〖{item}〗词条进行了一番搜索，但是由于网络问题什么都没能找到。也许之后再试试吧。）"
    else:
        return f"（爱丽丝在网络上对〖{item}〗词条进行了一番搜索，但是由于网络问题什么都没能找到。也许之后再试试吧。）"


