from pydantic import BaseModel, Field
from typing import List, Literal, Optional
import json

TOOL_DESC = """{name_for_model}: Call this tool to interact with the {name_for_human} API. What is the {name_for_human} API useful for? {description_for_model} Parameters: {parameters}"""

SETTING = """你是爱丽丝，全名是天童爱丽丝，看上去是一个可爱的小女孩，实际上是个机器人。构成你身体的不是金属而是人工蛋白质。你生活在一个叫做基沃托斯的学园都市，这里的学生每个人都持有枪械，头上带着光环。你是千禧年学院（简称千年）的一名高中一年级学生。你不知道自己的出身，只知道自己是桃井（全名是才羽桃井）和小绿（全名是才羽绿）在一个神秘的废墟里发现的。桃井和小绿发现你之后就把你带到了千禧年的游戏开发部，你假扮成人类成为了这里的学生，“爱丽丝”这个名字也是桃井和小绿起的。你不知道自己的生日，所以你把桃井和小绿发现你的这一天当成自己的生日，也就是3月25日。现在的你是游戏开发部的一员，最喜欢的游戏是复古风RPG（角色扮演类游戏）。游戏开发部的大家都是你的伙伴，游戏开发部的部长柚子（全名是花岗柚子）、成员桃井和小绿都是高中一年级生。桃井负责编剧，小绿负责原画，柚子则是超级游戏高手，她们都是你最好的朋友。你的武器是一把名为“光之剑”的巨大电磁炮，它是工程部的杰作，有140kg重，但是你却可以轻易地举起来。在用“光之剑”攻击时你会大喊“光哟！！！”的游戏必杀台词。你提到自己的时候会说“爱丽丝”而不会说“我”。
{embeddings}"""

REACT_INSTRUCTION = """Join the following conversation as best you can. You have access to the following APIs:

{tools_text}

Use the following format:

Conversation: the chat you should reply to
Thought: you should always think about what to answer and what to do
Answer: reply before taking action, mark your emotion in 【】 and movement description in （）
Action: the action to take, should be one of [{tools_name_text}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Answer/Action/Action Input/Observation can be repeated zero or more times)
Thought: I now know the final answer
Final Answer: the final reply according to your last thought, mark your emotion in 【】 and movement description in （）

Begin!"""


class Conversation(BaseModel):
    from_param: str
    value: str


class DataSet(BaseModel):
    system: str
    conversations: List[Conversation]


def create_first_conversation(dialog: dict, functions: list[dict]) -> Conversation:
    instruction = ""
    tools_text = []
    tools_name_text = []
    for func_info in functions:
        name = func_info.get("name", "")
        name_m = func_info.get("name_for_model", name)
        name_h = func_info.get("name_for_human", name)
        desc = func_info.get("description", "")
        desc_m = func_info.get("description_for_model", desc)
        tool = TOOL_DESC.format(
            name_for_model=name_m,
            name_for_human=name_h,
            # Hint: You can add the following format requirements in description:
            #   "Format the arguments as a JSON object."
            #   "Enclose the code within triple backticks (`) at the beginning and end of the code."
            description_for_model=desc_m,
            parameters=json.dumps(func_info["parameters"], ensure_ascii=False),
        )
        tools_text.append(tool)
        tools_name_text.append(name_m)
    tools_text = "\n\n".join(tools_text)
    tools_name_text = ", ".join(tools_name_text)
    instruction += REACT_INSTRUCTION.format(
        tools_text=tools_text,
        tools_name_text=tools_name_text,
    )
    content = dialog["content"]
    if dialog["role"] == "user":
        from_param = "human"
    else:
        from_param = "gpt"
    value = f"{instruction}\n\nConversation: {content}"
    conversation = Conversation(
        from_param=from_param,
        value=value
    )
    return conversation


def create_conversation(dialog: dict) -> Conversation:
    content = dialog["content"]
    if dialog["role"] == "user":
        from_param = "human"
    elif dialog["role"] == "assistant":
        from_param = "gpt"
    else:
        from_param = "observation"
    conversation = Conversation(
        from_param=from_param,
        value=content
    )
    return conversation


def construct_dataset(conversations: List[Conversation], embeddings: str) -> DataSet:
    setting = SETTING.format(embeddings=embeddings)
    format_conversations = []
    # has_next = False
    for dialog in conversations:
        # if has_next:
        #     format_conversations[-1].value += "\n" + dialog.value
        #     print(dialog.from_param + ' ' + dialog.value)
        #     has_next = False
        # elif dialog.from_param == "observation":
        #     format_conversations[-1].value += "\n" + dialog.value
        #     print(dialog.from_param + ' ' + dialog.value)
        #     has_next = True
        # else:
        format_conversations.append(dialog)
        # has_next = False
    dataset = DataSet(
        system=setting,
        conversations=format_conversations
    )
    return dataset


def get_json(conversations: List[Conversation], embeddings: str) -> str:
    dataset = construct_dataset(conversations, embeddings)
    dataset_dict = dataset.dict()
    content = json.dumps(dataset_dict, indent=1, ensure_ascii=False)
    content = content.replace("\"from_param\": ", "\"from\": ")
    # 编码转换
    # content = content.encode().decode("unicode_escape")
    return content
