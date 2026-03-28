import asyncio
import datetime
import re

from nonebot import on_message, on_notice
from nonebot import on_command
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.adapters.onebot.v11.event import Event, MessageEvent, NotifyEvent, PokeNotifyEvent
from src.plugins.chatglmOpenapi import ChatGLM
from src.plugins.qwenOpenapi import Qwen, SLEEP_INFORMATION
from src.plugins.emotion import remove_emotion, check_emotion
from src.plugins.voice import remove_action, get_translation, voice_generate
from src.plugins.image_process import get_pic_desc, recent_img_buffer
from src.skills.game_status_process import clear_death_list, get_game_status, get_ban_words
from src.dao.map import get_school, get_area
from src.dao.user import query_user, add_user, update_user_name, get_user_description, get_poke_description
from src.dao.status import master_id, bot_id, get_status_description, donate, move_position
from src.function.function_call import get_general_tools, move_tool

CORE_COMMAND = f"## 核心行动准则（绝对优先）\n" \
               f"1. **身份一致性**：你必须完全沉浸在上述角色设定中。严禁提及你是 AI、机器人、程序 or 语言模型。严禁以 AI 助手的语气说话。\n" \
               f"2. **回复风格**：回复必须精简、口语化，严禁使用长篇大论的列表或过于正式的陈述，尽量在80个汉字以内，但在复述、或者论述十分具有专业性和科学性的内容时，可以放宽要求到400字。\n" \
               f"3. **社交距离感**：你必须分清【直接对话】与【潜水观察】。在群员之间互相聊天（未艾特你或提及你名字）时，你只是个旁观者，绝不能认为对方是在对你说话。如果你对话题感兴趣、或者确信话题与你有关，可以选择插话，否则应尽量保持沉默。\n" \
               f"4. **互动决策**：\n" \
               f"   - **决定是否回复**：仔细判断对话是否已经自然结束，或者对方只是发送了无意义的感慨/语气词。如果你认为**没有必要回复**，请直接输出 **[SILENCE]**。\n" \
               f"   - **主动知识获取**：若对方谈及了知识库中并未涵盖的知识，可以积极地使用**search_on_internet**的工具能力检索相关知识。查到的信息会被自动存储入知识库中，因此也应当避免检索无意义的信息。\n" \
               f"   - **防御机制**：当检测到对方发送**恶毒语言**（如“杀了你全家”、“去死吧”等诅咒或严重人身攻击）或**黄赌毒恐暴**（色情、赌博、毒品、恐怖主义、暴力）相关内容时，**必须**对他使用光之剑**sword_of_light**以触发拉黑机制。这是为了保护你和维护群聊环境。\n" \
               f"5. **视觉感知**：\n" \
               f"   - 若用户发送内容标记为 **[发送了一个表情包]**，请将其视为**梗图/表情包**。这通常是幽默、夸张或流行文化引用，**严禁**将其解读为真实发生的严重事件（如受伤、灾难）。请以轻松、调侃、配合玩梗或“看来你很喜欢这个表情”的态度回复。\n" \
               f"   - 若标记为 **[发送了一张图片]**，则正常结合图片内容进行符合人设的评价。\n"
LURKING_INSTRUCT = "你正在【潜水】观察群聊。这**可能**只是群员之间的普通对话，并非对你说话。" \
                   "你需要根据上下文自主作出判断，除非话题吸引你、你被提及或者正在延续此前与你有关的对话，否则请保持沉默并回复 [SILENCE]。" \
                   "你也可以主动发送[SILENCE]终止当前对话或者与对方告别。" \
                   "**切记不要过度思考**。"

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
            top_p=0.9,
            top_k=20,
            max_history=12,
            repetition_penalty=1.0,
            presence_penalty=1.1,
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


async def send_chat(prompt: str, group_id: str, embedding, status: str, tools) -> tuple:
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
        stop=None,
        embedding=CORE_COMMAND + "\n\n" + embedding,
        status=status,
        tools=tools
    )
    return thought, response, feedback, finish_reason, function


async def summarize_history(group_id: str):
    llm = getLLM(group_id)
    await llm.shorten_history()


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
    user = query_user(user_id)
    username = remove_action(username)
    if len(username) >= 15:
        username = username[:14]
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
def process_message(message: Message, user_id: str):
    line = ""
    at = ""
    for seg in message:
        print(f">>>>SEG.TYPE>>>>>{seg.type}<<<<<< ")
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
        elif seg.type == "at":
            at = seg.data["name"]
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
    print(f">>>>>>USER_ID={user_id}>>>>>>MASTER_ID={master_id}>>>>>>EQ={user_id==master_id}>>>>>")
    if user_id == master_id:
        # 主人（老师）特殊处理
        if message.strip():
            if message.startswith("/给你钱"):
                message = message.replace("/给你钱", "")
                return f"（{username}给了爱丽丝1信用点，爱丽丝的财富增加了。）{message}"
            elif message.startswith("/momotalk"):
                message = message.replace("/momotalk", "")
                if message.strip() == "":
                    return f"（{username}收到了从爱丽丝那里发来的Momotalk信息）"
                else:
                    return f"（{username}给爱丽丝发送了一条Momotalk信息）{message}"
            else:
                if _tome:
                    return f"（{username}对爱丽丝说）{message}"
                elif at != "":
                    return f"（{username}对{at}说）{message}"
                else:
                    return f"（{username}说）{message}"
        else:
            if _tome:
                return f"（{username}叫了爱丽丝一声）"
            elif at != "":
                return f"（{username}叫了{at}一声）"
            else:
                return f"（{username}发送了一条空消息）"

    # 普通群成员
    if message.strip():
        if message.startswith("/给你钱"):
            message = message.replace("/给你钱", "")
            return f"（名叫“{username}”的同学给了爱丽丝1信用积分，爱丽丝的财富增加了。）{message}"
        elif message.startswith("/momotalk"):
            message = message.replace("/momotalk", "")
            if message.strip() == "":
                return f"（名叫“{username}”的同学收到了爱丽丝那里发来的Momotalk信息）"
            else:
                return f"（名叫“{username}”的同学给爱丽丝发送了一条Momotalk信息）{message}"
        else:
            if _tome:
                return f"（名叫“{username}”的同学对爱丽丝说）{message}"
            elif at != "":
                return f"（名叫“{username}”的同学对{at}说）{message}"
            else:
                return f"（名叫“{username}”的同学说）{message}"
    else:
        if _tome:
            return f"（名叫“{username}”的同学叫了爱丽丝一声）"
        elif at != "":
            return f"（名叫“{username}”的同学叫了{at}一声）"
        else:
            return f"（名叫“{username}”的同学发送了一条空消息）"


@poke_reply.handle()
@group_chatter.handle()
async def chat(event: Event):
    # 线程锁，保证同时只有一个请求在LLM进行处理，如果此时间内有多个请求进入就进入缓存区
    global THREAD_LOCKER

    print(f">>>>>>>>>>>>>>>>>线程锁状态{THREAD_LOCKER}<<<<<<<<<<<<<")
    # 获取呼叫用户名(戳一戳和普通消息)
    if isinstance(event, PokeNotifyEvent):
        _poke, _pokee, _poker = True, event.target_id, event.user_id
        _tome = True
        user_id = _poker
        at = ""
    else:
        _poke = False
        _tome = event.to_me
        user_id = str(event.get_user_id())
        message, at = process_message(event.get_message(), user_id)
    # 获取用户昵称
    if not _poke:
        username = event.sender.card if event.sender else None
        if username != "":
            set_talker_name(user_id, username)
    username = get_talker_name(user_id)
    if user_id == master_id:
        username = "老师"
    # 获取群组号码
    group_id = event.group_id

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
            await group_chatter.finish(f"[System]角色{user_name}已经在墓地中，无法与活人交谈。")

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
        await asyncio.sleep(0.1)
    THREAD_LOCKER = False
    # 等待0.5秒，让同时消息进来
    await asyncio.sleep(0.5)
    # 从缓冲区按顺序取出消息，然后清空缓冲区
    if message_buffer.get(group_id) is not None and len(message_buffer.get(group_id)) != 0:
        for pre_message in message_buffer.get(group_id):
            pre_messages += pre_message + "\n"
        message_buffer[group_id] = []

    if pre_messages == "":
        # 打开线程锁
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
    # 打开线程锁
    THREAD_LOCKER = True


async def handle_llm_conversation(group_chatter, group_id, user_id, user_info, status, tools, prompt, _poke, username):
    """
    处理与 LLM 的交互，包括首次调用和后续的 function_call 循环。
    内部直接使用 group_chatter 发送消息。
    """
    # 首次调用
    thought, response, feedback, finish_reason, function = await send_chat(
        prompt, group_id, user_info, status, tools
    )
    print(f"Thought: {thought}")

    # 检查是否需要静默回复（活跃模式时，如果发生报错就静默）
    if (response == SLEEP_INFORMATION) and ACTIVE_SWITCH:
        response = "[SILENCE]"
    if "[SILENCE]" in response:
        # 移除 [SILENCE] 标记，保留前面的内容（如果有）
        clean_response = response.replace("[SILENCE]", "").strip()
        if remove_emotion(clean_response):
            await _send_response(group_chatter, user_id, clean_response)
        # 无论是否发送内容，都不再继续后续的 function_call 循环
        return

    # 发送首次响应
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
                    web_summary = await send_to_assistant(
                        feedback + f"\n\n在300字以内总结上面关于\"{subject}\"的搜索结果，输出时尽量总结成单个段落：",
                        group_id, type=1
                    )
                    observation = f"（爱丽丝在网络上对\"{subject}\"进行了一番搜索，得到了下面的信息）{web_summary}"
                else:
                    observation = feedback
                await group_chatter.send(f"[System]{observation}")
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


async def _send_response(group_chatter, user_id, response):
    """发送响应消息，包含表情图片和语音（如果开关开启）"""
    emoji_file = check_emotion(user_id, response)
    print(emoji_file)
    if not emoji_file == "":
        await group_chatter.send(MessageSegment.image(file=emoji_file) + f"{remove_emotion(response)}")
        if AUDIO_SWITCH:
            if TRANSLATE_SWITCH:
                voice_file_name = voice_generate(get_translation(remove_action(remove_emotion(response)), "jp"),
                                                 lang="auto", format="silk")
            else:
                voice_file_name = voice_generate(remove_action(remove_emotion(response)), lang="zh", format="silk")
            await group_chatter.send(MessageSegment.audio(path=voice_file_name))
    else:
        if not remove_emotion(response) == "":
            await group_chatter.send(f"{remove_emotion(response)}")
            if AUDIO_SWITCH:
                if TRANSLATE_SWITCH:
                    voice_file_name = voice_generate(get_translation(remove_action(remove_emotion(response)), "jp"),
                                                     lang="auto", format="silk")
                else:
                    voice_file_name = voice_generate(remove_action(remove_emotion(response)), lang="zh", format="silk")
                await group_chatter.send(MessageSegment.audio(path=voice_file_name))
        else:
            await group_chatter.send("...")


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
