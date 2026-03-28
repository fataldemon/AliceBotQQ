import os
import re
from src.dao.user import favor_change
from dotenv import load_dotenv

load_dotenv()
root_url = os.environ.get("ABS_ROOT")


def text_to_emoji(text: str) -> str:
    # 清除“xx地”这样的描述
    text = text.replace("地", "")
    emojis = {
        "【认真】": "emoji/angry.png",
        "【坚定】": "emoji/angry.png",
        "【承诺】": "emoji/angry.png",
        "【生气】": "emoji/angry.png",
        "【急切】": "emoji/angry.png",
        "【烦恼】": "emoji/screwup.png",
        "【专注】": "emoji/awake.png",
        "【诚实】": "emoji/awake.png",
        "【期待】": "emoji/smile.png",
        "【回答】": "emoji/awake.png",
        "【回忆】": "emoji/thinking.png",
        "【发愣】": "emoji/awake.png",
        "【察觉】": "emoji/awake.png",
        "【建议】": "emoji/smile.png",
        "【好奇】": "emoji/awake.png",
        "【自信】": "emoji/confident.png",
        "【自豪】": "emoji/confident.png",
        "【解释】": "emoji/smile.png",
        "【失望】": "emoji/awkward.png",
        "【委屈】": "emoji/cry.png",
        "【伤心】": "emoji/cry.png",
        "【高兴】": "emoji/smile.png",
        "【开心】": "emoji/happy.png",
        "【欢迎】": "emoji/smile.png",
        "【崇拜】": "emoji/smile.png",
        "【愉快】": "emoji/smile.png",
        "【贴心】": "emoji/smile.png",
        "【赞同】": "emoji/smile.png",
        "【邀请】": "emoji/smile.png",
        "【兴奋】": "emoji/happy.png",
        "【快乐】": "emoji/happy.png",
        "【难过】": "emoji/awkward.png",
        "【为难】": "emoji/awkward.png",
        "【紧张】": "emoji/awkward.png",
        "【困惑】": "emoji/awkward.png",
        "【困扰】": "emoji/awkward.png",
        "【疑惑】": "emoji/awkward.png",
        "【害怕】": "emoji/sweating.png",
        "【平和】": "emoji/plain.png",
        "【无聊】": "emoji/plain.png",
        "【慌张】": "emoji/screwup.png",
        "【害羞】": "emoji/shy.png",
        "【羞涩】": "emoji/shy.png",
        "【微笑】": "emoji/confident.png",
        "【惊喜】": "emoji/smile.png",
        "【理解】": "emoji/smile.png",
        "【喜悦】": "emoji/smile.png",
        "【担忧】": "emoji/sweating.png",
        "【流汗】": "emoji/sweating.png",
        "【尴尬】": "emoji/sweating.png",
        "【犹豫】": "emoji/awkward.png",
        "【震惊】": "emoji/sweating.png",
        "【惊讶】": "emoji/sweating.png",
        "【思考】": "emoji/thinking.png",
        "【沉思】": "emoji/thinking.png",
        "【否认】": "emoji/thinking.png",
        "【睡觉】": "emoji/thinking.png",
        "【陈述】": "emoji/plain.png",
        "【祈祷】": "emoji/thinking.png",
        "【拒绝】": "emoji/angry.png",
        "【警惕】": "emoji/angry.png",
        "【感动】": "emoji/touching.png",
        "【感激】": "emoji/touching.png",
        "【道歉】": "emoji/sweating.png",
        "【可爱】": "emoji/happy.png",
        "【俏皮】": "emoji/happy.png",
        "【调皮】": "emoji/happy.png",
        "【卖萌】": "emoji/happy.png",
        "【眨眼】": "emoji/happy.png"
    }
    if emojis.get(text) is not None:
        return emojis.get(text)
    else:
        return ""


def text_to_favor(text: str) -> int:
    # 清除“xx地”这样的描述
    text = text.replace("地", "")
    favor_list = {
        "【认真】": 0,
        "【坚定】": 0,
        "【承诺】": 0,
        "【生气】": -5,
        "【急切】": 0,
        "【烦恼】": 0,
        "【专注】": 0,
        "【诚实】": 0,
        "【期待】": 1,
        "【回答】": 0,
        "【回忆】": 0,
        "【发愣】": 0,
        "【察觉】": 0,
        "【建议】": 0,
        "【好奇】": 1,
        "【自信】": 0,
        "【自豪】": 0,
        "【解释】": 0,
        "【失望】": -1,
        "【委屈】": -2,
        "【伤心】": -3,
        "【高兴】": 1,
        "【开心】": 2,
        "【欢迎】": 1,
        "【崇拜】": 2,
        "【愉快】": 1,
        "【贴心】": 1,
        "【赞同】": 1,
        "【邀请】": 0,
        "【兴奋】": 2,
        "【快乐】": 1,
        "【难过】": -1,
        "【为难】": 0,
        "【紧张】": 0,
        "【困惑】": 0,
        "【困扰】": -1,
        "【疑惑】": 0,
        "【害怕】": -2,
        "【平和】": 0,
        "【无聊】": 0,
        "【慌张】": 0,
        "【害羞】": 0,
        "【羞涩】": 0,
        "【微笑】": 0,
        "【惊喜】": 2,
        "【理解】": 0,
        "【喜悦】": 1,
        "【担忧】": 0,
        "【流汗】": 0,
        "【尴尬】": -1,
        "【犹豫】": 0,
        "【震惊】": 0,
        "【惊讶】": 0,
        "【思考】": 0,
        "【沉思】": 0,
        "【否认】": 0,
        "【睡觉】": 0,
        "【陈述】": 0,
        "【祈祷】": 1,
        "【拒绝】": -1,
        "【警惕】": -1,
        "【感动】": 2,
        "【感激】": 2,
        "【道歉】": 1,
        "【可爱】": 1,
        "【俏皮】": 1,
        "【调皮】": 1,
        "【卖萌】": 1,
        "【眨眼】": 1
    }
    if favor_list.get(text) is not None:
        return favor_list.get(text)
    else:
        return 0


def remove_emotion(message: str) -> str:
    pattern = r'\【[^\】^\]]*[\]\】]'
    match = re.findall(pattern, message)
    if not len(match) == 0:
        print(match)
        print(f"emotion:{match[0]}")
        return message.replace(match[0], "")
    else:
        return message


def check_emotion(user_id: str, message: str) -> str:
    """
    检查情绪（在对话中以【】格式表示）
    :param user_id: 用户ID
    :param message: 待处理的消息内容
    :return: 从中提取情绪对应的表情，并进行好感度变化
    """
    pattern = r'\【[^\】^\]]*[\]\】]'
    match = re.findall(pattern, message)
    if not len(match) == 0:
        print(match)
        print(f"emotion:{match[0]}")
        emoji = text_to_emoji(match[0].replace("]", "】"))
        favor = text_to_favor(match[0].replace("]", "】"))
        favor_change(user_id=user_id, value=favor)
        return f"{root_url}\{emoji}"
    else:
        return ""
