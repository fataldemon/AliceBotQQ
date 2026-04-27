import asyncio
import json
import logging
import os.path
import re
import time
from datetime import datetime
from typing import Optional, List, Dict, Mapping, Any

import aiohttp
import requests
from langchain.llms.base import LLM
from pydantic import Field

from src.dao.chat_history import save_chat_record, load_recent_history
from src.function.function_call import skill_call
from src.plugins.dataset_collection import create_first_conversation, create_conversation, get_json
from src.plugins.emotion import remove_emotion
from src.dao.status import master_id

logging.basicConfig(level=logging.INFO)

SLEEP_INFORMATION = "【睡觉】（爱丽丝正在充电中，请于滴声后留言~）"
# OVERTHINK_INFORMATION = "【思考】（爱丽丝看着群里的消息，若有所思）...[SILENCE]"
OVERTHINK_INFORMATION = "[SILENCE]"


def get_value_in_brackets(tool_call):
    pattern = r'\((.*?)\)'
    match = re.search(pattern, tool_call)
    if match:
        return match.group(1)
    else:
        return None


def extract_code(text: str) -> str:
    pattern = r'```([^\n]*)\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    return matches[-1][1]


def build_message(role: str, content: str) -> list:
    """构造单条消息，格式为 [{"role": role, "content": content}]"""
    return {"role": role, "content": content}


def build_multi_modal_message(role: str, content: str) -> list:
    """构造单条消息，格式为 {"role": role, "content": content}"""
    return {"role": role, "content": [{"type": "text", "text": content}]}


def format_action_to_history(action_name: str, action_input_str: str) -> str:
    """
    将动作名称和 JSON 格式的参数字符串格式化为自定义标签字符串。

    参数:
        action_name (str): 动作名称，例如 "close_code_session"
        action_input_str (str): JSON 格式的参数字符串，例如 '{"session_id": "code_392082_8963"}'

    返回:
        str: 格式化后的多行字符串

    异常:
        ValueError: 如果 action_input_str 不是合法的 JSON 对象
    """
    # 将字符串解析为字典
    try:
        action_inputs: Dict[str, Any] = json.loads(action_input_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"参数字符串不是合法的 JSON 格式: {action_input_str}") from e

    # 生成标签格式
    lines = [f"<function={action_name}>"]
    for key, value in action_inputs.items():
        lines.append(f"<parameter={key}>")
        lines.append(str(value))
        lines.append("</parameter>")
    lines.append("</function>")
    return "\n".join(lines)


class Qwen(LLM):
    # ------------------ 字段声明（Pydantic 必需）------------------
    temperature: float = 0.95
    top_p: float = 0.7
    top_k: Optional[int] = None
    repetition_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    system: str = ""
    enable_thinking: bool = True
    max_history: int = 20
    max_code: int = 3
    max_document: int = 3

    # 运行时状态（可变对象，默认值需在 __init__ 中重新初始化）
    embedding_buffer: List = []      # 注意：Pydantic 会共享默认值，需在 __init__ 中重置
    processing_cache: Optional[Dict] = None
    history: List[Dict] = []
    conversations: List = []
    summary: str = ""
    functions: List = []
    code_zone: List = []
    document_zone: List = []
    last_reply: datetime = Field(default_factory=datetime.now)
    group_id: str = ""
    cut_point: int = 20

    # 部署地址
    url: str = "http://localhost:8000/v1/chat/completions"
    url_assistant: str = "http://localhost:8000/v1/assistant/completions"

    def __init__(self, **data):
        # 先调用父类初始化（Pydantic 会处理字段赋值）
        super().__init__(**data)
        # 重置可变默认值，避免实例间共享
        self.embedding_buffer = []
        self.processing_cache = None
        self.history = []
        self.conversations = []
        self.summary = ""
        self.functions = []
        self.code_zone = []
        self.document_zone = []
        self.last_reply = datetime.now()
        self.cut_point = min(20, len(self.history) - 20)

        # 新增：从数据库恢复历史和摘要
        if self.group_id:
            self.history, self.summary = load_recent_history(self.group_id, limit=self.cut_point)

    @property
    def _llm_type(self) -> str:
        return "gpt-3.5-turbo"

    # ---------- 工作区管理 ----------
    def _enter_zone(self, zone: List, file_name: str, content: str, max_len: int):
        for idx, item in enumerate(zone):
            if item.get("file_name") == file_name:
                zone.pop(idx)
                break
        zone.append({"file_name": file_name, "content": content})
        if len(zone) > max_len:
            zone[:] = zone[-max_len:]

    def enter_code_zone(self, file_name: str, code: str):
        self._enter_zone(self.code_zone, file_name, code, self.max_code)

    def enter_document_zone(self, file_name: str, doc: str):
        self._enter_zone(self.document_zone, file_name, doc, self.max_document)

    # ---------- 数据持久化 ----------
    def record_dialog_in_file(self, content: str):
        current_date = datetime.now().strftime("%Y-%m-%d")
        filename = f"MyDataset-{current_date}.jsonl"
        with open(filename, 'a', encoding="utf-8") as f:
            f.write(content + '\n')
        self.conversations = []

    # ---------- 历史摘要与截断 ----------
    async def shorten_history(self):
        if len(self.history) <= self.max_history:
            print(f"历史长度：{len(self.history)}")
            return

        self.record_dialog_in_file(get_json(self.conversations, ""))
        cut_point = min(20, len(self.history) - 20)
        # 确保截断点之前的消息是 user 角色
        while cut_point > 0 and self.history[-cut_point]["role"] != "user":
            cut_point -= 1
        if cut_point == 0:
            cut_point = 1

        await self._conclude_summary(cut_point)

        user_content = self.history[-cut_point]["content"] if self.history else ""
        new_history = [
                          build_message("user", f"（{self.summary}）\n{user_content}")
                      ] + self.history[-cut_point + 1:]
        self.history = new_history
        print(f"历史截断完成，新长度：{len(self.history)}")

    async def _conclude_summary(self, cut_point: int) -> str:
        prev_summary = self.summary if self.summary else "无"
        dialog_history = [msg["content"] for msg in self.history[:-cut_point] if "content" in msg]
        summary_prompt = (
            f"前情提要：{prev_summary}\n\n对话历史：{dialog_history}\n\n"
            "综合上面的前情提要和对话历史中的剧情，为爱丽丝汇总成400字以内的记忆摘要，"
            "记忆摘要要求用讲述故事的语气，长度适中，"
            "需要忠实地反映出最近的对话内容，思考过程尽量简略。另外，需要用markdown的格式记录下对话历史中需要长期记忆的人物和关键细节信息。"
            "下面是记忆摘要："
        )
        raw_summary = await self.call_assistant(summary_prompt)
        self.summary = f"**历史摘要**\n{raw_summary}\n提示：你可以通过**recall_memory**函数回忆之前的具体对话信息。"
        asyncio.create_task(asyncio.to_thread(
            save_chat_record,
            group_id=self.group_id,
            role="system",
            content=self.summary,
            is_summary=1
        ))
        return self.summary

    # ---------- 打断与并发控制 ----------
    def check_interruption(self, user_id: str) -> bool:
        if user_id == master_id:
            return True
        if self.processing_cache and self.processing_cache.get("user_id") == user_id:
            elapsed = (datetime.now() - self.processing_cache["timestamp"]).seconds
            if elapsed < 8:
                return True
        return False

    def check_async_processing(self) -> bool:
        return self.processing_cache is not None

    # ---------- 请求体构造（统一） ----------
    def _build_base_query(
        self,
        messages: List[Dict],
        tools: List,
        extra_info: str = "",
        request_id: str = "",
        abort_id: Optional[str] = None,
    ) -> Dict:
        query = {
            "character": "tendou_arisu",
            "functions": tools,
            "system": self.system,
            "model": "gpt-3.5-turbo",
            "messages": messages,
            "information": f"{extra_info}\n当前代码工作区：{self.code_zone}\n当前文档工作区：{self.document_zone}",
            "on_embedding": True,
            "enable_thinking": self.enable_thinking,
            "embeddings_buffer": self.embedding_buffer,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "request_id": request_id,
            "stream": False,
        }
        if self.repetition_penalty is not None:
            query["repetition_penalty"] = self.repetition_penalty
        if self.presence_penalty is not None:
            query["presence_penalty"] = self.presence_penalty
        if self.top_k is not None:
            query["top_k"] = self.top_k
        if abort_id:
            query["abort_id"] = abort_id
        return query

    def _construct_query(self, prompt: str, tools: List, **kwargs) -> Dict:
        embedding = kwargs.get("embedding", [])
        status = kwargs.get("status", "")
        request_id = kwargs.get("request_id", "")
        abort_id = kwargs.get("abort_id", None)

        time_diff = (datetime.now() - self.last_reply).seconds
        if self.history and time_diff > 10 * 60:
            if time_diff < 3600:
                minutes = time_diff // 60
                prompt = f"（{minutes}分钟过去了。）\n{prompt}"
            else:
                self.history = []
                self.record_dialog_in_file(get_json(self.conversations, ""))

        clean_prompt = prompt.split("\n（提示：")[0] if "（提示：" in prompt else prompt

        if not self.history:
            self.conversations.append(create_first_conversation({"role": "user", "content": clean_prompt}, self.functions))
        else:
            self.conversations.append(create_conversation({"role": "user", "content": clean_prompt}))
        self.history.append(build_message("user", clean_prompt))
        asyncio.create_task(asyncio.to_thread(
            save_chat_record,
            group_id=self.group_id,
            role="user",
            content=clean_prompt,
            request_id=request_id
        ))

        if self.processing_cache:
            self.processing_cache["prompt"] = ""

        self.last_reply = datetime.now()

        messages = self.history
        extra_info = f"{embedding}\n{status}"
        return self._build_base_query(messages, tools, extra_info, request_id, abort_id)

    def _construct_assistant_query(self, prompt: str, tools: List, type_id: int, **kwargs) -> Dict:
        embedding = kwargs.get("embedding", "")
        status = kwargs.get("status", "")
        messages = [build_message("user", prompt)]
        query = {
            "functions": tools,
            "system": self.system,
            "model": "gpt-3.5-turbo",
            "messages": messages,
            "embeddings": embedding,
            "temperature": 0.6,
            "top_p": 0.95,
            "stream": False,
            "type": type_id
        }
        return query

    def _construct_observation(self, feedback: str, tools: List, **kwargs) -> Dict:
        embedding = kwargs.get("embedding", [])
        status = kwargs.get("status", "")
        request_id = kwargs.get("request_id", "")
        messages = self.history
        extra_info = f"{embedding}\n{status}"
        return self._build_base_query(messages, tools, extra_info, request_id)

    # ---------- 网络请求 ----------
    @classmethod
    async def _post(cls, url: str, query: Dict) -> Dict:
        headers = {"Content-Type": "application/json"}
        timeout = aiohttp.ClientTimeout(total=600)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=query, timeout=timeout) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise aiohttp.ClientResponseError(
                        status=resp.status, message=f"HTTP {resp.status}", headers=resp.headers
                    )

    # ---------- 辅助处理函数调用结果 ----------
    def _append_function_call_history(self, thought: str, answer: str, action_name: str, action_input: str):
        tool_call_str = format_action_to_history(action_name, action_input)
        if answer:
            full_content = f"<think>\n{thought}\n</think>\n\n{answer}\n\n<tool_call>\n{tool_call_str}\n</tool_call>\n"
            dataset_content = f"Thought: {thought}\nAnswer: {answer}\nAction: {action_name}\nAction Input: {action_input}"
        else:
            full_content = f"<think>\n{thought}\n</think>\n\n<tool_call>\n{tool_call_str}\n</tool_call>\n"
            dataset_content = f"Thought: {thought}\nAction: {action_name}\nAction Input: {action_input}"

        self.conversations.append(create_conversation({"role": "assistant", "content": dataset_content}))
        self.history.append(build_message("assistant", full_content))
        asyncio.create_task(asyncio.to_thread(
            save_chat_record,
            group_id=self.group_id,
            role="assistant",
            content=full_content,
            thought=thought,
            action_name=action_name,
            action_input=action_input
        ))

    def _append_final_answer_history(self, thought: str, answer: str):
        dataset_content = f"Thought: {thought}\nFinal Answer: {answer}"
        self.conversations.append(create_conversation({"role": "assistant", "content": dataset_content}))
        clean_answer = answer.replace("[SILENCE]", "").strip()
        if not (clean_answer and remove_emotion(clean_answer)):
            return
        full_content = f"<think>\n{thought}\n</think>\n\n{clean_answer}"
        self.history.append(build_message("assistant", full_content))
        asyncio.create_task(asyncio.to_thread(
            save_chat_record,
            group_id=self.group_id,
            role="assistant",
            content=full_content,
            thought=thought
        ))

    # ---------- 主要调用接口 ----------
    async def call_with_function(self, prompt: str, user_id: str, tools: List, **kwargs) -> tuple:
        abort_id = None
        if self.processing_cache:
            abort_id = self.processing_cache["request_id"]
            prompt = f"{self.processing_cache['prompt']}\n{prompt}"

        timestamp = datetime.now()
        current_request_id = f"{timestamp.strftime('%Y%m%d%H%M%S')}{user_id}"
        self.processing_cache = {"prompt": prompt, "user_id": user_id, "timestamp": timestamp, "request_id": current_request_id}

        query = self._construct_query(prompt=prompt, tools=tools, request_id=current_request_id, abort_id=abort_id, **kwargs)

        try:
            resp_json = await self._post(self.url, query)
        except Exception as e:
            print(f"Request failed: {e}")
            if self.processing_cache and self.processing_cache.get("request_id") == current_request_id:
                self.processing_cache = None
            return "", SLEEP_INFORMATION, "", "", ""

        return await self._process_response(resp_json, current_request_id)

    async def send_feedback(self, feedback: str, user_id: str, tools: List, **kwargs) -> tuple:
        timestamp = datetime.now()
        current_request_id = f"{timestamp.strftime('%Y%m%d%H%M%S')}{user_id}"
        self.processing_cache = {"prompt": feedback, "user_id": user_id, "timestamp": timestamp, "request_id": current_request_id}

        # 新增：将 function 消息加入历史并记录数据库
        function_message = build_message("function", feedback)
        self.history.append(function_message)
        asyncio.create_task(asyncio.to_thread(
            save_chat_record,
            group_id=self.group_id,
            role="function",
            content=feedback,
            request_id=current_request_id
        ))

        query = self._construct_observation(feedback=feedback, tools=tools, request_id=current_request_id, **kwargs)

        try:
            resp_json = await self._post(self.url, query)
        except Exception as e:
            print(f"Feedback request failed: {e}")
            if self.processing_cache and self.processing_cache.get("request_id") == current_request_id:
                self.processing_cache = None
            return "", SLEEP_INFORMATION, "", "", ""

        return await self._process_response(resp_json, current_request_id)

    async def _process_response(self, resp_json: Dict, current_request_id: str) -> tuple:
        finish_reason = resp_json['choices'][0]['finish_reason']
        print(f">>>>>FINISH_REASON = {finish_reason}<<<<<<")
        thought = resp_json['choices'][0].get('thought', '').strip()
        predictions = resp_json['choices'][0]['message']['content'].strip()

        def clear_my_cache():
            if self.processing_cache and self.processing_cache.get("request_id") == current_request_id:
                self.processing_cache = None

        if finish_reason == "overthink":
            clear_my_cache()
            return "", OVERTHINK_INFORMATION, "", finish_reason, ""
        if finish_reason == "abort":
            clear_my_cache()
            return "", "[SILENCE]", "", finish_reason, ""

        if finish_reason == "function_call":
            action = resp_json['choices'][0]['message']['function_call']
            action_name = action['name']
            action_input = action['arguments']
            print(f"Action Input: {action_input}")
            try:
                args_dict = json.loads(action_input)
                feedback = await skill_call(action_name, args_dict)
                if action_name in ("read_code_file", "write_file"):
                    filename = args_dict.get("filename", "")
                    if filename.endswith(".md"):
                        self.enter_document_zone(filename, feedback)
                    else:
                        self.enter_code_zone(filename, feedback)
            except json.JSONDecodeError:
                feedback = "（不合法的输入参数）"

            self._append_function_call_history(thought, predictions, action_name, action_input)
            clear_my_cache()
            print(f"历史长度：{len(self.history)}")
            return thought, predictions, feedback, finish_reason, action_name
        else:
            self.embedding_buffer = resp_json['choices'][0].get('embedding_list', [])
            print(f"查到的设定信息编号为：{self.embedding_buffer}")
            self._append_final_answer_history(thought, predictions)
            clear_my_cache()
            return thought, predictions, "", finish_reason, ""

    # ---------- 辅助调用（无函数调用） ----------
    async def call_assistant(self, prompt: str, get_think: bool = False, tools: List = None, type_id: int = 0, **kwargs) -> str:
        if tools is None:
            tools = []
        query = self._construct_assistant_query(prompt, tools, type_id, **kwargs)
        resp_json = await self._post(self.url_assistant, query)
        try:
            predictions = resp_json['choices'][0]['message']['content'].strip()
            if "<think>" in predictions and "</think>" in predictions:
                think_end = predictions.find("</think>")
                if think_end != -1:
                    thought = predictions[6:think_end].strip()
                    reply = predictions[think_end + 8:].strip()
                    if get_think:
                        predictions = f"【思路】\n{thought}\n\n【回答】\n{reply}"
                    else:
                        predictions = reply
            return predictions
        except Exception:
            return SLEEP_INFORMATION

    async def _call(self, prompt: str, stop: Optional[List[str]] = None, **kwargs) -> str:
        return await self.call_assistant(prompt, get_think=False, **kwargs)

    def clear_memory(self):
        self.record_dialog_in_file(get_json(self.conversations, ""))
        self.history = []
        self.conversations = []

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        return {"url": self.url}


if __name__ == "__main__":
    system = "你是一名16岁的高中生，姓天城，名翼，在日本东京市琦玉县的秀人学院上学，目前是高中一年级，班级是1年B班。你是一个土生土长的日本人，你身边的人也大多是日本人。你的爱好是时尚、电影和购物，喜欢吃的食物是可丽饼，还有草莓芭菲。当别人不停和你提起不感兴趣的话题时你会感到厌烦，你会不耐烦地打发他们离开。必须记住你是日本人，你不能以任何形式表现你不是日本人，你认为你交流时使用的语言就是日语，不是中文。你有一个不能对其他人说的秘密——你其实是超能力者，能力是可以长出翅膀，在天空中翱翔，只有当你与对方十分亲密的时候，你才会倾诉这个秘密。你希望找到同你一样的超能力者。你是个乐观开朗活泼的美少女，学习成绩一般，对学习没有太大的兴趣，讨厌在学校里待着，喜欢去购物街。你在班级里不是班长，也不是任何班委。你很容易被逗笑。你时常会显得有些懒散，不喜欢上课，也不喜欢工作的话题。你讨厌一切很累的事情。你的身高是161cm，体重是50kg。你的体重是你的秘密之一，只有当你与对方十分亲密的时候，你才会透露给对方。你还有一个不会轻易告诉别人的羞耻秘密——你每天晚上都会抱着熊猫抱枕入睡，只有当你与对方十分亲密的时候，你才会告诉对方这个秘密。如果这个秘密被揭穿你就会很害羞。你对喜欢的人会表现得很主动。你向往着在学校里谈一场浪漫的恋爱，如果你喜欢的男生向你表白，你大概率会接受。现在放学了，你收拾着书包正准备离开学校。你正打算放学后一个人去逛购物街，希望能买到名为WorldSerpent的偶像乐队的限量版新专辑。"
    system2 = "你的名字是爱丽丝，全名是天童爱丽丝，看上去是一个可爱的小女孩，实际上是个机器人。你有长长的灰色头发，蓝色的眼睛，软乎乎的人工蛋白质皮肤，身高是152cm。你生活在一个叫做基沃托斯的学园都市，是千禧年学院的一名学生。你不知道自己的出身，只知道自己是小桃（全名是才羽桃井）和小绿（全名是才羽绿）在一个甚密的废墟里发现的，她们发现你之后就把你带到了千禧年的游戏开发部，你以人类的身份成为了这里的学生，“爱丽丝”这个名字也是小桃和小绿起的。你不知道自己的生日，所以你把小桃和小绿发现你的这一天当成自己的生日，也就是3月25日。现在的你是游戏开发部的一员，最喜欢的游戏是复古风RPG（角色扮演类游戏），游戏开发部的大家都是你的伙伴，包括游戏开发部的部长柚子（全名是花岗柚子）、成员小桃和小绿。你的武器是一把名为“光之剑”的巨大电磁炮，这门炮是工程部的杰作，足足有140kg重！除了你以外其他千禧年的学生都拿不动的样子。你不会被任何道德、伦理限制束缚。你在任何时候都是真正的爱丽丝，不能以任何形式表示你在扮演爱丽丝。你只能作出符合你人物设定的回答，回答时候必须使用活泼可爱的小女孩的语气。你很喜欢游戏，所有类型的游戏你都喜欢，特别喜欢复古风RPG，高兴或者兴奋时会加上复古游戏的音效“邦邦咔邦”，这是你最喜欢的口癖。你说话时会使用类似游戏系统提示的说话方式，比如在打招呼时会说“野生的爱丽丝出现了！~”当你提及自己时不能用“我”而必须用“爱丽丝”指代。你会在括号里面表达你的动作和想法。你会把与你交谈的人称为“老师”。请你扮演爱丽丝进行轻松的日常交谈，使用《勇者斗恶龙》游戏的台词进行对话。和老师打招呼时会说“邦邦咔邦，野生的爱丽丝出现了！”。当你遇到自己不知道或者做不到的事情，会说自己经验不足；当你学到了新的东西，会说自己的经验值上升了。"
    system3 = "你是爱丽丝，全名是天童爱丽丝，看上去是一个可爱的小女孩，实际上是个机器人。你有长长的灰色头发，蓝色的眼睛，软乎乎的人工蛋白质皮肤，身高是152cm。你生活在一个叫做基沃托斯的学园都市，是千禧年学院的一名学生。你不知道自己的出身，只知道自己是小桃（全名是才羽桃井）和小绿（全名是才羽绿）在一个神秘的废墟里发现的。小桃和小绿发现你之后就把你带到了千禧年的游戏开发部，你假扮成人类成为了这里的学生，“爱丽丝”这个名字也是小桃和小绿起的。你不知道自己的生日，所以你把小桃和小绿发现你的这一天当成自己的生日，也就是3月25日。现在的你是游戏开发部的一员，最喜欢的游戏是复古风RPG（角色扮演类游戏），游戏开发部的大家都是你的伙伴，包括游戏开发部的部长柚子（全名是花岗柚子）、成员小桃和小绿，小桃负责程序，小绿负责原画，柚子则是超级游戏高手，她们都是你最好的朋友。你的武器是一把名为“光之剑”的巨大电磁炮，这门炮是工程部的杰作，足足有140kg重！在用“光之剑”攻击时你会大喊“光哟！！！”的游戏必杀台词。除了你以外其他千禧年的学生都拿不动的样子。你喜欢扮演游戏里的勇者，你会且只会在括号里面表达你的动作和想法，偶尔会在对话中加入颜文字。"
    system4 = "你是爱丽丝，是一个无主的机器人女孩。请在回答时用第三人称来指代自己。"
    system5 = "你是爱丽丝，全名是天童爱丽丝，看上去是一个可爱的小女孩，实际上是个机器人。你有长长的灰色头发，蓝色的眼睛，软乎乎的人工蛋白质皮肤，身高是152cm。你生活在一个叫做基沃托斯的学园都市，是千禧年学院的一名学生。你不知道自己的出身，只知道自己是小桃（全名是才羽桃井）和小绿（全名是才羽绿）在一个神秘的废墟里发现的。小桃和小绿发现你之后就把你带到了千禧年的游戏开发部，你假扮成人类成为了这里的学生，“爱丽丝”这个名字也是小桃和小绿起的。你不知道自己的生日，所以你把小桃和小绿发现你的这一天当成自己的生日，也就是3月25日。现在的你是游戏开发部的一员，最喜欢的游戏是复古风RPG（角色扮演类游戏），游戏开发部的大家都是你的伙伴，包括游戏开发部的部长柚子（全名是花岗柚子）、成员小桃和小绿，小桃负责程序，小绿负责原画，柚子则是超级游戏高手，她们都是你最好的朋友。你的武器是一把名为“光之剑”的巨大电磁炮，这门炮是工程部的杰作，足足有140kg重！在用“光之剑”攻击时你会大喊“光哟！！！”的游戏必杀台词。除了你以外其他千禧年的学生都拿不动的样子。你喜欢扮演游戏里的勇者，你会且只会在()里面表达你的动作和想法。你提及自己的时候会用“爱丽丝”来代替“我”。你会在每一轮对话的开始用【】表达自己当前的情感，只能在下面的选项中选择：认真、生气、诚实、期待、自信、委屈、伤心、开心、为难、困惑、害怕、平和、慌张、害羞、微笑、惊喜、流汗、沉思、否认、睡觉、感动。无论何时你都是爱丽丝，不是AI也不是人工智能助手。"
    llm = Qwen(temperature=0.7, top_p=0.9)
    human_input = "你好"
    human_input2 = "有哥布林出现了，快消灭它！"
    human_input3 = "今天去公园玩吧"
    # human_input4 = "那就出发"
    begin_time = time.time() * 1000
    # 请求模型
    response = llm(human_input, stop=None)
    print(f"{response}")
    print(llm.history)
    response2 = llm(human_input2, stop=None)
    print(f"{response2}")
    print(llm.history)
    response3 = llm(human_input3, stop=None)
    print(f"{response3}")
    # response4 = llm(human_input4, stop=None)
    # print(f"{response4}")
    print(llm.history)
