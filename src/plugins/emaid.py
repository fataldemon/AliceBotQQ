import asyncio
import datetime
import re
from typing import Union, Tuple

from nonebot import on_message, on_notice, get_bot
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, MessageSegment, Event, MessageEvent, NotifyEvent, PokeNotifyEvent
from src.plugins.chatglmOpenapi import ChatGLM
from src.plugins.qwenOpenapi import Qwen, SLEEP_INFORMATION
from src.plugins.emotion import remove_emotion, check_emotion
from src.plugins.voice import remove_action, get_translation, voice_generate
from src.skills.image_process import recent_img_buffer
from src.skills.game_status_process import clear_death_list, get_game_status, get_ban_words
from src.dao.map import get_school, get_area
from src.dao.user import query_user, add_user, update_user_name, get_user_description, get_poke_description
from src.dao.status import master_id, bot_id, get_status_description, donate, move_position
from src.function.function_call import get_general_tools, move_tool

CORE_COMMAND = f"## 核心行动准则（绝对优先）\n" \
               f"1. **身份一致性**：你必须完全沉浸在上述角色设定中。严禁提及你是 AI、机器人、程序 or 语言模型。严禁以 AI 助手的语气说话。\n" \
               f"2. **回复风格**：回复必须精简、口语化，严禁使用长篇大论的列表或过于正式的陈述。\n" \
               f"3. **社交距离感**：你必须分清【直接对话】与【潜水观察】。在群员之间互相聊天（未艾特你或提及你名字）时，你只是个旁观者。你需要根据上下文自主作出判断，如果话题吸引你、你被提及或者正在继续此前与你正进行着的对话，请作出回复，否则请保持沉默并回复 **[SILENCE]**。\n" \
               f"4. **互动决策**：\n" \
               f"   - **决定是否回复**：仔细判断对话是否已经自然结束，或者对方只是发送了无意义的感慨/语气词。如果你认为**没有必要回复**，请直接输出 **[SILENCE]**。在回复时你可以发送 **[CQ:at,qq=<对方的id号码>]** 来@对方。\n" \
               f"   - **主动知识获取**：若对方谈及了知识库中并未涵盖的词汇、你不知道的网络梗，或是令你疑惑的表述，可以积极主动地使用**search_on_internet**的工具能力检索相关知识。你也可以通过**access_website**工具能力主动访问对话中涉及到的网页。通过**search_on_internet**查到的信息会被自动存储入知识库中。\n" \
               f"   - **防御机制**：当检测到对方发送**恶毒语言**（如“杀了你全家”、“去死吧”等诅咒或严重人身攻击）或**黄赌毒恐暴**（色情、赌博、毒品、恐怖主义、暴力）相关内容时，可以对他使用光之剑**sword_of_light**以触发拉黑机制。这是为了保护你和维护群聊环境。\n" \
               f"   - **分享内容**：对于他人从其他app分享的内容，你可以使用**access_website**工具访问以获取信息（如果是其他app的内容，真实URL地址应该在\"jumpUrl\"字段中寻找；如果是来自bilibili的分享，则应当寻找\"qqdocurl\"字段，或者找到包含https://b23.tv/的url地址）。对于他人转发的消息（json格式），如果包含图片的，你也可以使用**access_website**工具逐步访问图片地址以获取信息。注意：避免一次性访问5张图片以上，以规避性能问题。\n" \
               f"5. **视觉感知**：\n" \
               f"   - 你已经熟知了许多网络梗。若用户发送内容标记为 **[发送了一个表情包]**，请将其视为**梗图/表情包**。这通常是幽默、夸张或流行文化引用，请尝试理解对方想要表达的意思或者情感，并以轻松、调侃、配合玩梗的态度回复。对于涉及的陌生的梗或者人物，可以用**search_on_internet**的工具能力检索相关知识\n" \
               f"   - 若标记为 **[发送了一张图片]**，则正常结合图片内容进行符合人设的评价。\n"
LURKING_INSTRUCT = "当前你正在【潜水观察】，这有可能只是群员之间的普通对话，请根据上下文自主作出判断是否对你说话。如果话题吸引你、你被提及或者正在继续此前与你正进行着的对话，请作出回复；否则请保持沉默并回复 **[SILENCE]**。"

THREAD_LOCKER: bool = True  # 对话线程锁
ACTIVE_SWITCH: bool = True  # 主动读取对话开关
AUDIO_SWITCH: bool = False  # 语音开关
TRANSLATE_SWITCH: bool = True
user_blacklist = []
username_blacklist = []
message_buffer = {}  # 对话缓冲区
MAX_BUFFER = 10  # 对话缓冲区最大数量

# 对话者名字记忆区
anonymous_list = []
anonymous_name_list = ["甲", "乙", "丙", "丁", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N",
                       "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]

# 调用大模型对象列表（记忆体按照群号区分）
llm_list: dict = {}


def getLLM(group_id: str) -> ChatGLM:
    """
    按照群号获取大语言模型（为了分别存储记忆）
    :return:
    """
    if llm_list.get(group_id) is None:
        # llm = Qwen(temperature=0.95, top_p=0.7, functions=tools, repetition_penalty=1.10, max_history=12)
        # llm = Qwen(temperature=0.93, top_p=0.7, top_k=20, max_history=30, repetition_penalty=1.05)
        llm = Qwen(
            temperature=1.0,
            top_p=0.6,
            top_k=20,
            max_history=16,
            repetition_penalty=1.05,
            presence_penalty=1.08,
            enable_thinking=True
        )
        llm_list[group_id] = llm
        return llm
    else:
        return llm_list.get(group_id)


def _poke_checker(event: NotifyEvent) -> bool:
    if event.self_id == event.target_id and event.sub_type == "poke":
        return True
    else:
        return False


def _checker(event: MessageEvent) -> bool:
    """
    检查是否触发（通过@），但过滤通过/发起的命令
    :param event:
    :return:
    """
    user_id = event.get_user_id()
    if user_id == event.self_id or user_id in user_blacklist:
        return False
    if ACTIVE_SWITCH:
        return True
    message = str(event.get_plaintext())
    # for seg in event.get_message():
    #     print("******segment type: ", seg.type, "******")
    if message.startswith("/") and not message.startswith("/forget") and not message.startswith(
            "/给你钱") and not message.startswith("/momotalk"):
        return False
    elif "爱丽丝" in message or "邦邦咔邦" in message:
        return True
    else:
        return event.to_me


def _none_checker(event: MessageEvent) -> bool:
    """
    检查是否触发（通过@），但过滤通过/发起的命令
    :param event:
    :return:
    """
    user_id = event.get_user_id()
    if user_id in user_blacklist or event.get_plaintext().strip() == "":
        return False
    return not event.to_me


def _blacklist_checker(event: MessageEvent) -> bool:
    user_id = event.get_user_id()
    if user_id in user_blacklist:
        return False
    else:
        return True


test = on_command("test")
assistant = on_command("助手 ")
group_chatter = on_message(rule=_checker, priority=2, block=False)
poke_reply = on_notice(rule=_poke_checker, priority=2)
clear_memory = on_command("forget", rule=_checker, priority=3)
voice_switch = on_command("语音开关")
active_switch = on_command("活跃模式", block=True)
thread_lock = on_command("线程锁", block=True)
black_list = on_command("blacklist ")
unblack_list = on_command("unblacklist ")
set_scene = on_command("goto")
clear_death_zone = on_command("重置墓地")
donation = on_command("给你钱", rule=_checker, priority=1, block=False)
conclude_summary = on_command("总结历史")
group_message = on_message(rule=_none_checker, priority=1, block=False)


async def send_chat(prompt: str, group_id: str, user_id: str, embedding, status: str, tools) -> tuple:
    """
    通过接口向LLM发送聊天
    :param embedding: 附加知识内容
    :param group_id: 群组ID
    :param prompt:用户发送的聊天内容
    :return:LLM返回的聊天内容
    """
    llm = getLLM(group_id)
    thought, response, feedback, finish_reason, function = await llm.call_with_function(
        prompt,
        user_id=user_id,
        stop=None,
        embedding=CORE_COMMAND + "\n\n" + embedding,
        status=status,
        tools=tools
    )
    return thought, response, feedback, finish_reason, function


async def summarize_history(group_id: str):
    llm = getLLM(group_id)
    await llm.shorten_history()


# 检查该群组的打断条件
def check_interruption(group_id: str, user_id: str) -> bool:
    llm = getLLM(group_id)
    return llm.check_interruption(user_id)


# 检查该群组是否有正在进行中的异步任务
def check_async_task(group_id: str) -> bool:
    llm = getLLM(group_id)
    return llm.check_async_processing()


async def send_to_assistant(prompt: str, group_id: str, tools=[], get_think: bool = False, type: int = 0) -> tuple:
    """
    通过接口向LLM（不加Lora）发送聊天
    :param type: 助手类型（普通、知识点概要、记忆）
    :param get_think: 是否获取思维过程
    :param group_id: 群组ID
    :param prompt:用户发送的聊天内容
    :return:LLM返回的聊天内容
    """
    llm = getLLM(group_id)
    result = await llm.call_assistant(prompt, get_think=get_think, tools=tools, type=type, stop=None)
    return result


async def get_summary(group_id: str) -> str:
    """
    总结当前对话
    :param group_id:群组ID
    :return:
    """
    llm = getLLM(group_id)
    summary = await llm.conclude_summary()
    return summary


async def send_feedback(feedback: str, group_id: str, tools) -> tuple:
    """
    通过接口向LLM发送API返回结果
    :param group_id: 群组ID
    :param feedback: 函数调用反馈信息
    :param prompt:用户发送的聊天内容
    :return:LLM返回的聊天内容
    """
    llm = getLLM(group_id)
    thought, response, feedback, finish_reason, function = await llm.send_feedback(feedback, tools=tools, stop=None)
    return thought, response, feedback, finish_reason, function


def set_talker_name(user_id: str, username: str):
    if user_id == master_id:
        username = "老师"
    if user_id == bot_id:
        username = "天童爱丽丝"
    user = query_user(user_id)
    username = remove_action(username)
    if len(username) >= 20:
        username = username[:19]
    if user is None:
        add_user(user_id, username)
    else:
        if user_id in anonymous_name_list:
            temp_name = user.user_name
            anonymous_name_list.append(temp_name)
            anonymous_list.remove(user_id)
        if user.user_name != username:
            update_user_name(user_id, username)


# 通过QQ号获取对话者名字（未记录的按照QQ号码）
def get_talker_name(user_id: str) -> str:
    if user_id == master_id:
        return "老师"
    if user_id == bot_id:
        return "天童爱丽丝"
    user = query_user(user_id)
    if user is not None:
        return user.user_name
    else:
        anonymous_name = anonymous_name_list[0]
        add_user(user_id, anonymous_name)
        anonymous_list.append(user_id)
        anonymous_name_list.remove(anonymous_name_list[0])
        print(anonymous_name_list)
        return anonymous_name


def sword_of_light(user_name: str):
    """
    光之剑！将一名敌人送入墓地（屏蔽操作）
    :param user_name:
    :return:
    """
    username_blacklist.append(user_name)


@voice_switch.handle()
async def turn_switch(event: MessageEvent):
    global AUDIO_SWITCH
    user_id = event.get_user_id()
    if user_id == master_id:
        if AUDIO_SWITCH:
            AUDIO_SWITCH = False
            await voice_switch.send("语音关闭")
        else:
            AUDIO_SWITCH = True
            await voice_switch.send("语音启动")
    else:
        await voice_switch.send("权限不足")


@active_switch.handle()
async def turn_active(event: MessageEvent):
    global ACTIVE_SWITCH
    user_id = event.get_user_id()
    if user_id == master_id:
        if ACTIVE_SWITCH:
            ACTIVE_SWITCH = False
            await voice_switch.send("活跃模式关闭")
        else:
            ACTIVE_SWITCH = True
            await voice_switch.send("活跃模式启动")
    else:
        await voice_switch.send("权限不足")


@thread_lock.handle()
async def thread_lock_switch(event: MessageEvent):
    global ACTIVE_SWITCH
    user_id = event.get_user_id()
    if user_id == master_id:
        if ACTIVE_SWITCH:
            ACTIVE_SWITCH = False
            await voice_switch.send("线程锁关")
        else:
            ACTIVE_SWITCH = True
            await voice_switch.send("线程锁开")
    else:
        await voice_switch.send("权限不足")


async def save_message_buffer(group_id, prompt):
    if message_buffer.get(group_id) is None:
        message_buffer[group_id] = [prompt]
    else:
        message_buffer[group_id].append(prompt)
        if len(message_buffer[group_id]) > MAX_BUFFER:
            message_buffer[group_id] = message_buffer[group_id][-MAX_BUFFER:]


def recent_img_add(group_id: str) -> str:
    line = ""
    recent_img = recent_img_buffer.get(group_id)
    if recent_img is not None:
        if recent_img["url"] != "":
            url = recent_img["url"]
            if recent_img["description"] == "":
                username = recent_img["user"]
                if recent_img["subType"] == 1:
                    desc = f"（{username}发送了一个表情包）"
                else:
                    desc = f"（{username}发送了一张图片）"
                recent_img["description"] = desc
                line += f"{desc}[image,url={url}]\n"
                # 计算上一张图片的时间，若超过一分钟就不处理
                cur_time = datetime.datetime.now()
                time_diff = cur_time - recent_img["timestamp"]
                if time_diff.seconds > 60:
                    return ""
    return line


# 处理复杂类型的消息（图片处理、at等）
async def process_message(event: Event, user_id: str):
    line = ""
    at = ""
    message = event.get_message()
    if isinstance(event, MessageEvent):
        reply_info = event.reply
        if reply_info is not None:
            reply_sender_id = reply_info.sender.user_id
            username = get_talker_name(reply_sender_id)
            reply_source = reply_info.raw_message
            line += f"[对于{username}发送的消息“{reply_source}”发送的回复]"
    for seg in message:
        print(f">>>>SEG.TYPE>>>>>{seg.type}<<<<<<>>>>>SEG.DATA>>>>>{seg.data}<<<<<< ")
        if seg.type == "text":
            # 过滤括号里的内容
            content = seg.data["text"]
            if user_id != master_id:
                content = remove_action(content)
            line += content
        elif seg.type == "image":
            url = seg.data["url"]
            # desc = get_pic_desc(instruction, url)
            if seg.data["subType"] == 1:
                line += "[发送了一个表情包]"
            else:
                line += "[发送了一张图片]"
            # line += f"（发送了一张图片）[图片，description:\"{desc}\"]"
            line += f"[image,url={url}]"
            print(line)
        elif seg.type == "json":
            line += f"[分享了{str(seg.data)}]"
        elif seg.type == "record":
            record_url = seg.data.get("url")
            line += f"[发送了一条语音][voice,url={url}]"
        elif seg.type == "at":
            at_userid = seg.data["qq"]
            at_username = get_talker_name(at_userid)
            line += f"@{at_username}[id={at_userid}] "
            if at == "":
                at = f"{at_username}[id={at_userid}]"
            else:
                at += "、" + f"{at_username}[id={at_userid}]"
        elif seg.type == "forward":
            forward_id = seg.data.get("id")
            forward_messages = await get_bot(bot_id).get_forward_msg(id=forward_id)
            line += f"[转发了消息：{forward_messages}]"
    return line, at


def build_status():
    """
    构建包含当前日期时间和游戏状态的 status 字符串。

    返回:
        str: 组合后的状态描述，包含 get_status_description() 和当前日期时间信息
    """
    current_time = datetime.datetime.now()
    current_date_str = current_time.strftime("今天是%Y年%m月%d日")
    hour = current_time.hour

    # 根据小时确定时间段
    if 0 <= hour < 5:
        time_period = "凌晨"
    elif 5 <= hour < 9:
        time_period = "早上"
    elif 9 <= hour < 12:
        time_period = "上午"
    elif 12 <= hour < 14:
        time_period = "中午"
        hour = hour - 12
    elif 14 <= hour < 17:
        time_period = "下午"
        hour = hour - 12
    elif 17 <= hour < 19:
        time_period = "傍晚"
        hour = hour - 12
    elif 19 <= hour < 24:
        time_period = "晚上"
        hour = hour - 12

    current_time_str = current_time.strftime(f"当前时间：{time_period}%H点%M分%S秒。")

    # 星期映射
    weekday_map = {0: "一", 1: "二", 2: "三", 3: "四", 4: "五", 5: "六", 6: "日"}
    weekday = weekday_map[current_time.weekday()]

    dater = f"{current_date_str}，星期{weekday}，{current_time_str}"
    return get_status_description() + "\n" + dater


def build_prompt(at, _poke, _tome, user_id, master_id, message, username, ng_words):
    """
    根据不同场景构建发送给 LLM 的消息 prompt。

    参数:
        _poke: bool, 是否为戳一戳事件
        _tome: bool, 是否是在直接对我说话
        user_id: str, 用户ID
        master_id: str, 主人ID
        pre_messages: str, 历史预消息（已拼接好）
        message: str, 原始消息内容（仅当 _poke=False 时有效）
        username: str, 用户显示名（已处理过，如“老师”或普通成员名）
        ng_words: list, 敏感词列表

    返回:
        str: 构建好的 prompt
    """
    if _poke:
        # 戳一戳场景
        return f"（{get_poke_description(user_id)}）"

    # 普通消息场景
    if user_id == master_id:
        # 主人（老师）特殊处理
        if message.strip():
            if message.startswith("/给你钱"):
                message = message.replace("/给你钱", "")
                return f"（{username}给了爱丽丝1信用点，爱丽丝的财富增加了。）{message}"
            elif message.startswith("/momotalk"):
                message = message.replace("/momotalk", "")
                if message.strip() == "":
                    return f"（{username}[id={user_id}]收到了从爱丽丝那里发来的Momotalk信息）"
                else:
                    return f"（{username}[id={user_id}]给爱丽丝发送了一条Momotalk信息）{message}"
            else:
                if _tome:
                    return f"（{username}[id={user_id}]对爱丽丝说）{message}"
                elif at != "":
                    return f"（{username}[id={user_id}]对{at}说）{message}"
                else:
                    return f"（{username}[id={user_id}]说）{message}"
        else:
            if _tome:
                return f"（{username}[id={user_id}]@了爱丽丝一下）"
            elif at != "":
                return f"（{username}[id={user_id}]@了{at}一下）"
            else:
                return f"（{username}[id={user_id}]发送了一条空消息）"

    # 普通群成员
    if message.strip():
        if message.startswith("/给你钱"):
            message = message.replace("/给你钱", "")
            return f"（名叫“{username}”的同学[id={user_id}]给了爱丽丝1信用积分，爱丽丝的财富增加了。）{message}"
        elif message.startswith("/momotalk"):
            message = message.replace("/momotalk", "")
            if message.strip() == "":
                return f"（名叫“{username}”的同学[id={user_id}]收到了爱丽丝那里发来的Momotalk信息）"
            else:
                return f"（名叫“{username}”的同学[id={user_id}]给爱丽丝发送了一条Momotalk信息）{message}"
        else:
            if _tome:
                return f"（名叫“{username}”的同学[id={user_id}]对爱丽丝说）{message}"
            elif at != "":
                return f"（名叫“{username}”的同学[id={user_id}]对{at}说）{message}"
            else:
                return f"（名叫“{username}”的同学[id={user_id}]说）{message}"
    else:
        if _tome:
            return f"（名叫“{username}”的同学[id={user_id}]叫了爱丽丝一声）"
        elif at != "":
            return f"（名叫“{username}”的同学[id={user_id}]叫了{at}一声）"
        else:
            return f"（名叫“{username}”的同学[id={user_id}]发送了一条空消息）"


@poke_reply.handle()
@group_chatter.handle()
async def chat(event: Event):
    # 线程锁，保证同时只有一个请求在LLM进行处理，如果此时间内有多个请求进入就进入缓存区
    global THREAD_LOCKER

    # 获取群组号码
    group_id = event.group_id
    print(f">>>>>>>>>>>>>>>>>线程锁状态{THREAD_LOCKER}<<<<<<<<<<<<<")
    # 获取呼叫用户名(戳一戳和普通消息)
    if isinstance(event, PokeNotifyEvent):
        _poke, _pokee, user_id = True, event.target_id, event.user_id
        _tome = True
        at = ""
    else:
        _poke = False
        _tome = event.to_me
        user_id = str(event.get_user_id())
        message, at = await process_message(event, user_id)
    # 获取用户昵称
    if not _poke:
        username = event.sender.card.strip() if event.sender.card.strip() else event.sender.nickname.strip()
    else:
        user_info = await get_bot(bot_id).get_group_member_info(group_id=group_id, user_id=user_id, no_cache=False)
        username = user_info["card"] if user_info.get("card") != "" else user_info["nickname"]
    if username != "":
        set_talker_name(user_id, username)
    username = get_talker_name(user_id)
    if user_id == master_id:
        username = "老师"

    # 获取缓冲区的历史消息
    pre_messages = ""
    if not ACTIVE_SWITCH:
        pre_messages += recent_img_add(group_id)

    # 获取游戏状态与敏感词
    game_status = get_game_status()
    ng_words = get_ban_words()

    # 获取游戏信息和时间
    status = build_status()

    # 对话者信息
    user_info = get_user_description(user_id)
    print(user_info)

    # 工具初始化
    tools = get_general_tools()

    # 死亡名单检查（普通成员场景）
    if not _poke and user_id != master_id:
        user_name = get_talker_name(user_id)
        if user_name in game_status["death_list"] or user_name + "同学" in game_status["death_list"]:
            if not ACTIVE_SWITCH:
                await group_chatter.finish(f"[System]角色{user_name}已经在墓地中，无法与活人交谈。")
            return

    # 构建 prompt
    prompt = build_prompt(
        at=at,
        _poke=_poke,
        user_id=user_id,
        _tome=_tome,
        master_id=master_id,
        message=message if not _poke else "",  # 戳一戳时 message 为空
        username=username,
        ng_words=ng_words
    )

    # 把消息压入缓冲区
    await save_message_buffer(group_id, prompt)
    # 线程锁，只有在开放时才进入，进入后关闭线程锁，保证同时只有线程进入
    while not THREAD_LOCKER:
        # 例外：判断是否满足打断条件 1.相同用户在同一群组下发送消息；2.间隔不超过8秒
        if check_interruption(group_id=group_id, user_id=user_id):
            break
        await asyncio.sleep(0.1)
    THREAD_LOCKER = False
    # 等待0.5秒，让同时消息进来
    await asyncio.sleep(0.5)
    # 从缓冲区按顺序取出消息，然后清空缓冲区
    if message_buffer.get(group_id) is not None and len(message_buffer.get(group_id)) != 0:
        for pre_message in message_buffer.get(group_id):
            pre_messages += pre_message + "\n"
        message_buffer[group_id] = []

    # 如果缓冲区已经被取完就打开线程锁，退出线程
    if pre_messages == "":
        THREAD_LOCKER = True
        return

    tips = ""
    if _tome:
        if not _poke:
            # 敏感词检测
            bad_words = ""
            for bad_word in ng_words:
                if bad_word in message:
                    bad_words += bad_word + "，"
            if bad_words:
                tips = f"\n（提示：{bad_words}这是非常粗俗的词语，是不应该对孩子说的话。使用这样词语的人必须用光之剑sword_of_light教训一顿。）"
    else:
        tips = f"\n（提示：{LURKING_INSTRUCT})"

    # 调用大模型处理函数，传入 group_chatter 以便内部发送
    await handle_llm_conversation(
        group_chatter=group_chatter,
        group_id=group_id,
        user_id=user_id,
        user_info=user_info,
        status=status,
        tools=tools,
        prompt=pre_messages + tips,
        _poke=_poke,
        username=username
    )

    # 总结历史，缩短上下文
    await summarize_history(group_id)
    # 打开线程锁（但如果有打断消息则作不处理，持续保持线程锁状态）
    if not check_async_task(group_id):
        THREAD_LOCKER = True


async def handle_llm_conversation(group_chatter, group_id, user_id, user_info, status, tools, prompt, _poke, username):
    """
    处理与 LLM 的交互，包括首次调用和后续的 function_call 循环。
    内部直接使用 group_chatter 发送消息。
    """
    # 首次调用
    thought, response, feedback, finish_reason, function = await send_chat(
        prompt=prompt, group_id=group_id, user_id=user_id, embedding=user_info, status=status, tools=tools
    )
    print(f"Thought: {thought}")

    # 检查是否需要静默回复（活跃模式时，如果发生报错就静默）
    if (response == SLEEP_INFORMATION) and ACTIVE_SWITCH:
        response = "[SILENCE]"

    # 发送首次响应
    if response != "":
        await _send_response(group_chatter, user_id, response)

    steps = 0
    loop = 0
    max_loop = 6
    while finish_reason == "function_call" and loop < max_loop:
        loop += 1
        if feedback != "":
            if function == "search_on_internet":
                if "（爱丽丝在网络上对〖" in feedback and "〗词条进行了一番搜索，得到了一些信息）" in feedback:
                    tools = get_general_tools()
                    locator_left = feedback.rfind("〖")
                    locator_right = feedback.rfind("〗")
                    subject = feedback[locator_left + 1:locator_right]
                    await group_chatter.send(f"[System]正在搜索〖{subject}〗、总结信息中...")
                    web_summary = await send_to_assistant(
                        feedback + f"\n\n在400字以内总结上面关于\"{subject}\"的搜索结果。"
                                   f"输出时不需要换行符，并根据内容在末尾用##的方式加上搜索的核心关键词tag，多个tag用空格隔开。"
                                   f"在这之后，你还需要以<reference_url:https://...>这样的格式在末尾列出参考的网页链接。\n"
                                   f"（示例：夏亚·阿兹纳布尔，本名卡斯巴尔·雷姆·戴肯，是《机动战士高达》系列核心角色，吉翁·什姆·戴肯之子，塞拉之兄。因父亲被害，为复仇化名潜入吉翁军校，获“赤色彗星”绰号。"
                                   f"他一生使用多重身份，包括爱德华·玛斯、柯瓦特罗·巴吉纳等。性格理想主义却手段冷酷，因拉拉·辛之死及目睹人类黑暗面而走向极端。一年战争中，他驾驶红色扎古，以“红色有角三倍速”闻名，与宿敌阿姆罗·雷多次交锋。"
                                   f"格里普斯战役中，他以柯瓦特罗身份加入AEUG，目睹战争残酷后对人类绝望。UC0093年，他建立第二次新吉翁，驾驶沙扎比发动“地球寒冷化作战”，企图用阿克西斯撞击地球促进人类进化。"
                                   f"最终与阿姆罗驾驶的ν高达激战，虽战败但阿克西斯被神秘力量推开，两人失踪。夏亚是高达系列首位“面具男”，面具象征其隐藏身份与复杂内心。其角色原型参考红男爵与哈姆雷特，声优主要为池田秀一。"
                                   f"他驾驶过吉翁号、百式、沙扎比等多台著名机体，对高达历史影响深远，是兼具魅力与悲剧色彩的复杂反派。 ##夏亚 ##夏亚·阿兹纳布尔 ##卡斯巴尔·雷姆·戴肯） "
                                   f"<reference_url:https://baike.baidu.com/item/%E5%A4%8F%E4%BA%9A%C2%B7%E9%98%BF%E5%85%B9%E7%BA%B3%E5%B8%83%E5%B0%94/1285271><reference_url:https://zh.wikipedia.org/wiki/%E5%A4%8F%E4%BA%9E%C2%B7%E9%98%BF%E8%8C%B2%E7%B4%8D%E5%B8%83%E7%88%BE>"
                                   f"你给出的总结：",
                        group_id, type=1
                    )
                    raw_observation = f"（爱丽丝在网络上对\"{subject}\"进行了一番搜索，得到了下面的信息）{web_summary}"
                    # 匹配从 <reference_url: 开始到第一个 > 结束的内容
                    pattern = r'<reference_url:[^>]*>'
                    # 替换为空字符串，并去除尾部空白（如换行、空格）
                    observation = re.sub(pattern, '', raw_observation).rstrip()
                else:
                    observation = feedback
            elif function == "move" or function == "decide_area" or function == "decide_school":
                if feedback == "[EXIT_AREA]":
                    steps = 1
                    tools = move_tool(steps, 0, 0)
                    desc = tools[0]["parameters"]["properties"]["options"]["description"]
                    await group_chatter.send("[System]爱丽丝打算离开当前地点，正在考虑去往哪个区域。")
                    observation = f"你打算离开当前地点，正在考虑去往哪个区域。你应该使用decide_area能力决定要前往的区域。\n{desc}"
                elif feedback == "[EXIT_SCHOOL]":
                    steps = 2
                    tools = move_tool(steps, 0, 0)
                    desc = tools[0]["parameters"]["properties"]["options"]["description"]
                    await group_chatter.send("[System]爱丽丝打算离开当前区域，正在考虑去往哪个校区。")
                    observation = f"你打算离开当前地点，正在考虑去往哪个校区。你应该使用decide_school能力决定要前往的校区。\n{desc}"
                elif feedback.isdigit():
                    if steps == 2:
                        steps -= 1
                        tools = move_tool(steps, feedback, 0)
                        desc = tools[0]["parameters"]["properties"]["options"]["description"]
                        school = get_school(feedback)
                        await group_chatter.send(
                            f"[System]爱丽丝抵达了{school.school_name}的外围，正在考虑去往哪个区域。")
                        observation = f"你抵达了{school.school_name}的外围，正在考虑去往哪个区域。你应该使用decide_area能力决定要前往的区域。\n{desc}"
                    elif steps == 1:
                        steps -= 1
                        tools = move_tool(steps, 0, feedback)
                        desc = tools[0]["parameters"]["properties"]["options"]["description"]
                        area = get_area(feedback)
                        await group_chatter.send(f"[System]爱丽丝抵达了{area.area_name}区域，正在考虑去往哪个地点。")
                        observation = f"你抵达了{area.area_name}区域，正在考虑去往哪个地点。你应该使用move能力决定要前往的地点。\n{desc}"
                else:
                    tools = get_general_tools()
                    steps = 0
                    await group_chatter.send(f"[System]{feedback}")
                    observation = feedback
            elif function == "access_website":
                if "因为网络不佳的原因失败了" in feedback:
                    await group_chatter.send(f"[System]{feedback}")
                observation = feedback
            else:
                tools = get_general_tools()
                await group_chatter.send(f"[System]{feedback}")
                observation = feedback

        # 调用反馈
        thought, response, feedback, finish_reason, function = await send_feedback(
            observation, group_id, tools
        )
        print(f"Thought: {thought}")

        # 发送响应
        await _send_response(group_chatter, user_id, response)


def convert_cq_to_message(content: str) -> Tuple[Union[str, Message, MessageSegment], str]:
    """
    将字符串中的 [CQ:at,qq=数字] 转换为消息段，同时生成替换为 @用户名 的纯文本。

    参数:
        content: 原始字符串

    返回:
        (msg_obj, text_str)
        - msg_obj: 可直接发送的消息对象（str/Message/MessageSegment）
        - text_str: 将 [CQ:at,qq=xxx] 替换为 "@用户名 " 后的纯文本
    """
    pattern = re.compile(r'\[CQ:at,qq=(\d+)\]')
    matches = list(pattern.finditer(content))

    # 没有匹配到任何 CQ:at
    if not matches:
        return content, content

    # 构造替换后的纯文本（从后往前替换，避免偏移）
    text_result = content
    for match in reversed(matches):
        qq = match.group(1)
        username = get_talker_name(qq)   # 调用你的函数获取用户名
        replacement = f"@{username} "    # 用户名后加一个空格
        text_result = text_result[:match.start()] + replacement + text_result[match.end():]

    # 构造消息对象（原逻辑）
    if len(matches) == 1 and matches[0].group(0) == content.strip():
        # 整个字符串正好是一个纯 CQ 码
        msg_obj = MessageSegment.at(user_id=matches[0].group(1))
    else:
        # 混合文本，构造 Message 对象
        segments = []
        last_end = 0
        for match in matches:
            start, end = match.span()
            if start > last_end:
                segments.append(content[last_end:start])
            qq = match.group(1)
            segments.append(MessageSegment.at(user_id=qq))
            last_end = end
        if last_end < len(content):
            segments.append(content[last_end:])
        msg_obj = Message(segments)

    return msg_obj, text_result


async def _send_response(group_chatter, user_id, response):
    if "[SILENCE]" in response:
        # 移除 [SILENCE] 标记，保留前面的内容（如果有）
        response = response.split("[SILENCE]")[0].strip()

    """发送响应消息，包含表情图片、语音（如果开关开启），支持 CQ:at 转 @ 消息段，同时语音使用替换后的文本"""
    emoji_file = check_emotion(user_id, response)
    print(emoji_file)

    # 1. 去除表情标记，得到不含表情的文本（可能仍含 CQ:at）
    text_no_emotion = remove_emotion(response)

    # 2. 转换 CQ:at 为消息对象和纯文本（@用户名 形式）
    msg_obj, text_with_at = convert_cq_to_message(text_no_emotion)

    # 3. 发送图片 + 消息对象
    if emoji_file:
        await group_chatter.send(MessageSegment.image(file=emoji_file) + msg_obj)
    else:
        if text_no_emotion:   # 原 text_no_emotion 非空（即使转换后可能变成纯@用户名）
            await group_chatter.send(msg_obj)
        else:
            return

    # 4. 发送语音（使用替换后的纯文本 text_with_at，并去除动作标记）
    if AUDIO_SWITCH:
        # 去除动作标记，得到最终用于语音的文本
        clean_text = remove_action(text_with_at)
        if TRANSLATE_SWITCH:
            translated = get_translation(clean_text, "jp")
            voice_file_name = voice_generate(translated, lang="auto", format="silk")
        else:
            voice_file_name = voice_generate(clean_text, lang="zh", format="silk")
        await group_chatter.send(MessageSegment.audio(path=voice_file_name))


@clear_memory.handle()
async def clear_memory_func(event: MessageEvent):
    group_id = event.group_id
    user_id = event.get_user_id()
    if user_id == master_id:
        if message_buffer.get(group_id) is not None:
            message_buffer[group_id] = []
        llm = getLLM(group_id)
        llm.clear_memory()
        await clear_memory.send(f"爱丽丝什么都不记得了！")
    else:
        await clear_memory.send("权限不足")


@black_list.handle()
async def add_black_list(event: MessageEvent):
    user_id = event.get_user_id()
    if user_id == master_id:
        blacklist_user_id = str(event.get_plaintext()).replace("/blacklist ", "")
        if blacklist_user_id != "":
            user_blacklist.append(blacklist_user_id)
            await black_list.send("黑名单已添加")
        else:
            await black_list.send("QQ号为空")
    else:
        await black_list.send("权限不足")


@unblack_list.handle()
async def remove_black_list(event: MessageEvent):
    user_id = event.get_user_id()
    if user_id == master_id:
        blacklist_user_id = str(event.get_plaintext()).replace("/unblacklist ", "")
        if blacklist_user_id != "":
            user_blacklist.remove(blacklist_user_id)
            await unblack_list.send("黑名单已清除")
        else:
            await unblack_list.send("QQ号为空")
    else:
        await unblack_list.send("权限不足")


@set_scene.handle()
async def set_scene_manual(event: MessageEvent):
    user_id = event.get_user_id()
    if user_id == master_id:
        scene = str(event.get_plaintext()).replace("/goto", "")
        move_position(10)
        await set_scene.send(f"[System]爱丽丝所处的场景已设定为“基沃托斯-D.U.-沙勒-生活区-休息室”")
    else:
        await set_scene.send("权限不足")


@clear_death_zone.handle()
async def reset_tomb(event: MessageEvent):
    user_id = event.get_user_id()
    if user_id == master_id:
        clear_death_list()
        await clear_death_zone.send(f"[System]当前墓地已经被清空")
    else:
        await clear_death_zone.send("权限不足")


@donation.handle()
async def donate_money(event: MessageEvent):
    await donation.send(f"[System]（爱丽丝得到了1信用点，现在有{donate(1)}信用点）")


@assistant.handle()
async def assistant_reply(event: MessageEvent):
    group_id = event.group_id
    content = str(event.get_plaintext()).replace("/助手 ", "")
    reply = await send_to_assistant(content, group_id, tools=get_general_tools(), get_think=False)
    await assistant.send(reply)


@conclude_summary.handle()
async def do_summary(event: MessageEvent):
    group_id = event.group_id
    summary = await get_summary(group_id)
    await conclude_summary.send(f"[System]（目前的对话总结：\n{summary}）")


@test.handle()
async def do_test(event: MessageEvent):
    print(MessageSegment.image(file="../../emoji/angry.png"))
    await test.send(MessageSegment.image(file="../../emoji/angry.png"))
