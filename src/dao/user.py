from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from nonebot import on_command
from nonebot.adapters.onebot.v11.event import MessageEvent
from src.dao.dbengine import engine
from src.dao.status import master_id

# 创建一个基类，用于声明类定义
Base = declarative_base()

data_query = on_command("查询所有用户", block=True)
self_query = on_command("查询状态", block=True)


class User(Base):
    __tablename__ = 't_user'

    user_id = Column(String(50), primary_key=True)
    user_name = Column(String(50), nullable=False)
    relation = Column(Integer, nullable=False, default=0)
    level = Column(Integer, nullable=False, default=1)
    exp = Column(Integer, nullable=False, default=0)
    profession = Column(String(20), nullable=False, default="NPC")
    hp = Column(Integer, nullable=False, default=100)
    hpmax = Column(Integer, nullable=False, default=100)
    attack = Column(Integer, nullable=False, default=1)
    defense = Column(Integer, nullable=False, default=0)
    position = Column(Integer, nullable=True, default=0)
    spot = Column(Integer, nullable=False, default=0)


# 创建"user"表
Base.metadata.create_all(engine)

# 创建一个用于数据库交互的Session类
Session = sessionmaker(bind=engine)


def query_user(user_id) -> User:
    session = Session()
    user = session.query(User).filter_by(user_id=user_id).first()
    session.close()
    if user:
        return user
    else:
        return None


def add_user(user_id, user_name):
    session = Session()
    user = User(user_id=user_id, user_name=user_name)
    session.add(user)
    session.commit()
    session.close()
    print(f"▲添加人物{user_id}:{user_name}成功")


def update_user_name(user_id, user_name):
    session = Session()
    user = session.query(User).filter_by(user_id=user_id).first()
    if user:
        user.user_name = user_name
        print(f"▲人物名称已更新为{user_name}")
    else:
        user = User(user_id=user_id, user_name=user_name)
        session.add(user)
        print(f"▲添加人物{user_id}:{user_name}成功")
    session.commit()
    session.close()


def favor_change(user_id: str, value: int):
    session = Session()
    user = session.query(User).filter_by(user_id=user_id).first()
    if user:
        user.relation += value
        if user.relation > 2000:
            user.relation = 2000
        elif user.relation < -1000:
            user.relation = -1000
        session.commit()
        print(f"▲{user.user_name}的好感度变化：{value}")
    session.close()


def get_favor_description(favor: float, user_name: str) -> str:
    if favor == 5000:
        return f"{user_name}同学是你的挚友，是你生命中最重要的人之一，仅次于老师。你会尽力满足{user_name}同学的要求，只要不是过分的要求。"
    elif 5000 > favor >= 3000:
        return f"{user_name}同学是你最好的朋友之一，你已经习惯了和他亲昵的举动，但你不会允许冒犯或者下流的行为。"
    elif 3000 > favor >= 1500:
        return f"{user_name}同学是你的知心朋友，你偶尔会向他倾诉自己的烦恼和想法，但你从来不打算与{user_name}同学发展恋爱关系。"
    elif 1500 > favor >= 1000:
        return f"{user_name}同学是你的好朋友，{user_name}同学的触摸会让你感到温暖，但你从来不打算与{user_name}同学发展恋爱关系。"
    elif 1000 > favor >= 500:
        return f"{user_name}同学是你的朋友，你时常会和他聊天和玩耍，但你不会允许冒犯的行为。你从来不打算与{user_name}同学发展恋爱关系。"
    elif 500 > favor >= 100:
        return f"你认识{user_name}同学有一段日子了，他可以算是你的朋友。你从来不打算与{user_name}同学发展恋爱关系。"
    elif 100 > favor >= 0:
        return f"你认识{user_name}同学，但并不熟悉。请友好地对待{user_name}同学吧。你目前还没有打算与{user_name}同学发展更深的关系。"
    elif 0 > favor >= -100:
        return f"你对{user_name}同学的第一印象并不好，但你还是希望能和{user_name}同学好好地相处。"
    elif -100 > favor > -500:
        return f"你有些讨厌{user_name}，他总是惹你生气。"
    elif -500 > favor > -1000:
        return f"你对{user_name}同学非常厌恶，你认为他是坏人。"
    else:
        return f"{user_name}同学是你的敌人，你认为他是不可饶恕的坏人。对他使用光之剑吧！"


def get_poke_description(user_id: str) -> str:
    if user_id is not None and user_id != "":
        print(f">>>>>USER_ID={user_id}<<<<<>>>>>MASTER_ID={master_id}<<<<<>>>>>>EQ={master_id==user_id}<<<<<")
        if str(user_id) != str(master_id):
            user = query_user(user_id)
            favor = user.relation
            user_name = user.user_name
            if favor == 5000:
                return f"{user_name}同学轻轻地戳了戳爱丽丝的脸。爱丽丝感到很高兴。"
            elif 5000 > favor >= 3000:
                return f"{user_name}同学轻轻地戳了戳爱丽丝的脸。爱丽丝感到很高兴。"
            elif 3000 > favor >= 1500:
                return f"{user_name}同学轻轻地戳了戳爱丽丝的脸。爱丽丝感到心里暖暖的。"
            elif 1500 > favor >= 1000:
                return f"{user_name}同学轻轻地戳了戳爱丽丝的脸。爱丽丝知道这是对方在试图表达亲昵。"
            elif 1000 > favor >= 500:
                return f"{user_name}同学轻轻地戳了戳爱丽丝的脸。爱丽丝猜想对方也许是在开玩笑呢。"
            elif 500 > favor >= 100:
                return f"{user_name}同学轻轻地戳了戳爱丽丝的脸。尽管不太喜欢这样的行为，但爱丽丝还是容忍了。爱丽丝知道这是对方在试图表达亲昵。"
            elif 100 > favor >= 0:
                return f"{user_name}同学试图伸手戳爱丽丝的脸。爱丽丝不喜欢这样轻浮的行为。"
            elif 0 > favor >= -100:
                return f"{user_name}同学试图伸手戳爱丽丝的脸。爱丽丝不喜欢这样轻浮的行为。"
            elif -100 > favor > -500:
                return f"{user_name}同学试图伸手戳爱丽丝的脸。爱丽丝对这样的冒犯感到不满。"
            elif -500 > favor > -1000:
                return f"{user_name}同学试图伸手戳爱丽丝的脸。爱丽丝对这样的冒犯感到很愤怒。"
            else:
                return f"{user_name}同学试图伸手戳爱丽丝的脸。爱丽丝对这样的冒犯感到很愤怒。"
        else:
            return "老师轻轻地戳了戳爱丽丝的脸。爱丽丝喜欢老师这样亲密的表达。"
    else:
        return f"似乎有人伸手戳了戳爱丽丝的脸。"


def get_user_description(user_id: str) -> str:
    if str(user_id) != master_id:
        user = query_user(user_id)
        return f"关于{user.user_name}:[名为“{user.user_name}”的同学是一名学生。你对{user.user_name}同学的好感度: {user.relation/100}," \
               f"你对{user.user_name}同学的态度: \"{get_favor_description(user.relation, user.user_name)}\"]"
    else:
        return f"关于老师:[你对老师的好感度: 100," \
               f"你对老师的了解: \"老师，是隶属于沙勒的顾问老师，也是基沃托斯唯一的老师，是你最亲近的人之一。老师的名字是“魔童様”，性别男，是一名戴着眼镜的大人。老师似乎没有什么战斗力。" \
               f"沙勒（S.C.H.A.L.E.，又称作夏莱）是隶属于联邦学生会的搜查机构，也负责解决学生的问题。" \
               f"沙勒办公大楼是老师平时办公的地方，平时会有学生来值日，帮助老师处理公务。沙勒的生活区，是老师在基沃托斯居住的地方。\"," \
               f"你对老师的态度: \"老师是你最亲近的人之一，你很喜欢老师。老师和游戏开发部的大家是最初发现你的人，也是你最珍视的伙伴。不管老师提出什么要求你都会欣然同意的。\"]"


@data_query.handle()
async def query_all_user(event: MessageEvent):
    user_id = event.get_user_id()
    if user_id == master_id:
        session = Session()
        users = session.query(User).all()
        session.close()
        res = ""
        for user in users:
            res += f"ID：{user.user_id}，姓名：{user.user_name}，好感度：{user.relation/100}\n"
        await data_query.send(res)
    else:
        await data_query.send("权限不足")


@self_query.handle()
async def query_status(event: MessageEvent):
    user_id = event.get_user_id()
    session = Session()
    user = session.query(User).filter_by(user_id=user_id).first()
    session.close()
    await self_query.send(f"当前用户：{user.user_name}\n"
                          f"好感度：{user.relation/100}，等级：{user.level}，经验：{user.exp}/{user.level*100}，职业：{user.profession}\n"
                          f"生命值：{user.hp}/{user.hpmax}，攻击力：{user.attack}，防御力：{user.defense}，当前位置：{user.position}")
