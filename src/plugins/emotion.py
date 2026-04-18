import os
import re
from src.dao.user import favor_change
from dotenv import load_dotenv

load_dotenv()
root_url = os.environ.get("ABS_ROOT")

emotion_dict = {
    "【认真】": ("emoji/angry.png", 0),
    "【坚定】": ("emoji/angry.png", 0),
    "【承诺】": ("emoji/angry.png", 0),
    "【生气】": ("emoji/angry.png", -5),
    "【急切】": ("emoji/angry.png", 0),
    "【烦恼】": ("emoji/screwup.png", 0),
    "【专注】": ("emoji/awake.png", 0),
    "【诚实】": ("emoji/awake.png", 0),
    "【期待】": ("emoji/smile.png", 1),
    "【回答】": ("emoji/awake.png", 0),
    "【回忆】": ("emoji/thinking.png", 0),
    "【发愣】": ("emoji/awake.png", 0),
    "【察觉】": ("emoji/awake.png", 0),
    "【建议】": ("emoji/smile.png", 0),
    "【好奇】": ("emoji/awake.png", 1),
    "【自信】": ("emoji/confident.png", 0),
    "【自豪】": ("emoji/confident.png", 0),
    "【解释】": ("emoji/smile.png", 0),
    "【失望】": ("emoji/awkward.png", -1),
    "【委屈】": ("emoji/cry.png", -2),
    "【伤心】": ("emoji/cry.png", -3),
    "【高兴】": ("emoji/smile.png", 1),
    "【开心】": ("emoji/happy.png", 2),
    "【欢迎】": ("emoji/smile.png", 1),
    "【崇拜】": ("emoji/smile.png", 2),
    "【愉快】": ("emoji/smile.png", 1),
    "【贴心】": ("emoji/smile.png", 1),
    "【赞同】": ("emoji/smile.png", 1),
    "【邀请】": ("emoji/smile.png", 0),
    "【兴奋】": ("emoji/happy.png", 2),
    "【快乐】": ("emoji/happy.png", 1),
    "【难过】": ("emoji/awkward.png", -1),
    "【为难】": ("emoji/awkward.png", 0),
    "【紧张】": ("emoji/awkward.png", 0),
    "【困惑】": ("emoji/awkward.png", 0),
    "【困扰】": ("emoji/awkward.png", -1),
    "【疑惑】": ("emoji/awkward.png", 0),
    "【害怕】": ("emoji/sweating.png", -2),
    "【无奈】": ("emoji/sweating.png", -1),
    "【平和】": ("emoji/plain.png", 0),
    "【无聊】": ("emoji/plain.png", 0),
    "【慌张】": ("emoji/screwup.png", 0),
    "【害羞】": ("emoji/shy.png", 0),
    "【羞涩】": ("emoji/shy.png", 0),
    "【微笑】": ("emoji/confident.png", 0),
    "【惊喜】": ("emoji/smile.png", 2),
    "【理解】": ("emoji/smile.png", 0),
    "【喜悦】": ("emoji/smile.png", 1),
    "【担忧】": ("emoji/sweating.png", 0),
    "【流汗】": ("emoji/sweating.png", 0),
    "【尴尬】": ("emoji/sweating.png", -1),
    "【犹豫】": ("emoji/awkward.png", 0),
    "【震惊】": ("emoji/sweating.png", 0),
    "【惊讶】": ("emoji/sweating.png", 0),
    "【思考】": ("emoji/thinking.png", 0),
    "【沉思】": ("emoji/thinking.png", 0),
    "【否认】": ("emoji/thinking.png", 0),
    "【睡觉】": ("emoji/thinking.png", 0),
    "【陈述】": ("emoji/plain.png", 0),
    "【祈祷】": ("emoji/thinking.png", 1),
    "【拒绝】": ("emoji/angry.png", -1),
    "【警惕】": ("emoji/angry.png", -1),
    "【感动】": ("emoji/touching.png", 2),
    "【感激】": ("emoji/touching.png", 2),
    "【道歉】": ("emoji/sweating.png", 1),
    "【可爱】": ("emoji/happy.png", 1),
    "【俏皮】": ("emoji/happy.png", 1),
    "【调皮】": ("emoji/happy.png", 1),
    "【卖萌】": ("emoji/happy.png", 1),
    "【眨眼】": ("emoji/happy.png", 1)
}


def text_to_emoji(text: str) -> str:
    # 清除“xx地”这样的描述
    text = text.replace("地", "")
    emoji_path, favor = emotion_dict.get(text)
    if emoji_path is not None:
        return emoji_path
    else:
        return ""


def text_to_favor(text: str) -> int:
    # 清除“xx地”这样的描述
    text = text.replace("地", "")
    emoji_path, favor = emotion_dict.get(text)
    if favor is not None:
        return favor
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
