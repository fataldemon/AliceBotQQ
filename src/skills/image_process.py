import base64
import datetime
import json
from nonebot import on_command, on_message
from nonebot.adapters.onebot.v11.event import MessageEvent
import requests
from src.dao.user import query_user
from src.dao.status import master_id, bot_id

ocr_url = "http://127.0.0.1:12345/func/ocr"
glm_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
glm_key = ""
img_url_buffer = {}
# 这是一个字典，key为群组号group_id，value为另外一个字典类，分别有user、url、subtype、description和timestamp四个key，对应用户名、图片url、图片类型、描述和时间戳
recent_img_buffer = {}
model_name = "glm-4v-flash"

img_buffer = on_message(priority=50)
do_ocr = on_command("ocr")
test_glm = on_command("glm")


def image_base64(img_url) -> str:
    response = requests.get(img_url)
    if response.status_code == 200:
        # 将图片转换为Base64格式
        image_base = base64.b64encode(response.content).decode('utf-8')
        return image_base
    else:
        return None


def get_ocr(img_path) -> str:
    _headers = {"Content-Type": "application/json"}
    with requests.session() as sess:
        resp = sess.get(
            f"{ocr_url}?img_path={img_path}",
            headers=_headers,
            timeout=60,
        )
    if resp.status_code == 200:
        return resp.text


@DeprecationWarning
def get_pic_desc(content: str, img_path: str) -> str:
    _headers = {"Authorization": f"Bearer {glm_key}",
                "Content-Type": "application/json"}
    img = None
    if img_path != "":
        img = image_base64(img_path)
    if img is None:
        query = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": content
                        }
                    ]
                }
            ],
            "stream": False,
        }
    else:
        query = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_base64(img_path)
                            }
                        },
                        {
                            "type": "text",
                            "text": content
                        }
                    ]
                }
            ],
            "stream": False,
        }
    with requests.session() as sess:
        resp = sess.post(
            glm_url,
            headers=_headers,
            json=query,
            timeout=60,
        )
    if resp.status_code == 200:
        resp_json = json.loads(resp.text)
        response_content = resp_json['choices'][0]['message']['content'].strip()
        return response_content
    else:
        return "None"


@img_buffer.handle()
def img_checker(event: MessageEvent) -> bool:
    global img_url_buffer
    global recent_img_buffer
    user_id = event.get_user_id()
    group_id = event.group_id
    message = event.get_message()
    urls = []
    recent_save_token = True  # token，仅为纯图时保存缓存（避免将回复表情存入）
    for seg in message:
        if seg.type == "image":
            img_url = seg.data['url']
            img_subtype = seg.data['subType']
            urls.append(img_url)
        else:
            recent_save_token = False  # 发现图片之外的元素就设置token
    if len(urls) != 0:
        img_url_buffer[user_id] = urls
        # 仅为纯图时保存缓存
        if recent_save_token:
            if user_id == bot_id:
                username = "爱丽丝"
            elif user_id == master_id:
                username = "老师"
            else:
                user = query_user(user_id)
                if user is not None:
                    username = f"名叫“{user.user_name}”的同学"
                else:
                    username = "某人"
            recent_img = {
                'user': username,
                'url': urls[-1],
                'description': "",
                'timestamp': datetime.datetime.now(),
                'subType': img_subtype
            }
            recent_img_buffer[group_id] = recent_img
            print(f"******图片缓存地址：{username}发送的[{img_url}]******")


@do_ocr.handle()
async def ocr_function(event: MessageEvent):
    message = event.get_message()
    img_check = False
    for seg in message:
        if seg.type == "img":
            img_check = True
            img_url = seg.data['src']
            result = get_ocr(img_url)
            await do_ocr.send(result)
    if not img_check:
        global img_url_buffer
        user_id = event.get_user_id()
        urls = img_url_buffer.get(user_id)
        if urls is not None:
            for url in urls:
                result = get_ocr(url)
                await do_ocr.send(result)
        else:
            await do_ocr.send("找不到图片。")


@test_glm.handle()
async def send_to_glm(event: MessageEvent):
    message = event.get_message()
    img_url = ""
    for seg in message:
        if seg.type == "img":
            img_url = seg.data['src']
            break
    content = str(event.get_plaintext()).replace("/glm", "").strip()
    if img_url != "":
        await test_glm.send(get_pic_desc(content, img_url))
    else:
        global img_url_buffer
        user_id = event.get_user_id()
        urls = img_url_buffer.get(user_id)
        if urls is not None:
            url = urls[-1]
            await test_glm.send(get_pic_desc(content, url))
        else:
            await test_glm.send(get_pic_desc(content, ""))
