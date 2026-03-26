import os
from dotenv import load_dotenv
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from src.dao.dbengine import engine
from nonebot import on_command
from nonebot.adapters.onebot.v11.event import MessageEvent
from src.dao.map import get_school, get_area, get_position, get_position_description, \
    get_available_position, get_available_area, get_available_school, \
    get_all_position, get_all_area, get_all_school, get_all_area_by_school, get_all_position_by_area, \
    get_railway_station


load_dotenv()

# 管理员身份
master_id = os.environ.get("master_id")
bot_id = os.environ.get("bot_user_id")

# 创建一个基类，用于声明类定义
Base = declarative_base()


class Status(Base):
    __tablename__ = 't_status'

    status_id = Column(Integer, primary_key=True)
    position = Column(Integer, nullable=False, default=10)
    spot = Column(Integer, nullable=False, default=0)
    coins = Column(Integer, nullable=False, default=0)
    level = Column(Integer, nullable=False, default=1)
    profession = Column(Integer, nullable=False, default=0)
    attack = Column(Integer, nullable=False, default=100)
    defense = Column(Integer, nullable=False, default=10)
    exp = Column(Integer, nullable=False, default=0)
    hp = Column(Integer, nullable=False, default=100)
    hpmax = Column(Integer, nullable=False, default=100)
    crit = Column(Integer, nullable=False, default=10)
    weapon = Column(Integer, nullable=False, default=0)


class Profession(Base):
    __tablename__ = 't_profession'

    prof_id = Column(Integer, primary_key=True)
    name = Column(String(10), nullable=False)
    description = Column(String(1000), nullable=True)
    hp = Column(Integer, nullable=False, default=0)
    attack = Column(Integer, nullable=False, default=0)
    defense = Column(Integer, nullable=False, default=0)
    range = Column(Integer, nullable=False, default=1)


class Tomb(Base):
    __tablename__ = 't_tomb'

    tomb_id = Column(Integer, primary_key=True)
    dead_user_id = Column(String(50), nullable=False)
    dead_name = Column(String(50), nullable=False)


# 创建表
Base.metadata.create_all(engine)

# 创建一个用于数据库交互的Session类
Session = sessionmaker(bind=engine)


available_move_targets = []
available_railway_targets = []
available_areas = []
available_schools = []
available_functions = ""


def get_available_move_targets():
    global available_move_targets
    return available_move_targets


def get_available_railway_targets():
    global available_railway_targets
    return available_railway_targets


def get_available_areas():
    global available_areas
    return available_areas


def get_available_schools():
    global available_schools
    return available_schools


def get_available_functions():
    global available_functions
    return available_functions


def set_available_functions(functions):
    global available_functions
    available_functions = functions


def query_status() -> Status:
    session = Session()
    status = session.query(Status).filter_by(status_id=0).first()
    session.close()
    if status:
        return status
    else:
        return None


def query_prof(prof_id) -> Profession:
    session = Session()
    profession = session.query(Profession).filter_by(prof_id=prof_id).first()
    session.close()
    if profession:
        return profession
    else:
        return None


def donate(amount: int) -> int:
    session = Session()
    status = session.query(Status).filter_by(status_id=0).first()
    coins = status.coins + amount
    status.coins = coins
    session.commit()
    session.close()
    return coins


def get_status_description() -> str:
    status = query_status()
    if status is None:
        return ""
    else:
        profession = query_prof(status.profession)
        if profession is None:
            desc = f"〖爱丽丝的状态栏〗\n爱丽丝的职业：{status.level}的学生\n" \
               f"经验值：{status.exp}/{status.level*100}\n" \
               f"生命值：{status.hp}/{status.hpmax}\n" \
               f"攻击力：{status.attack}\n防御力：{status.defense}\n" \
               f"暴击率：{status.crit}%\n攻击范围：1\n" \
               f"持有的财富：{status.coins}点信用积分\n装备：“光之剑”（电磁炮）。\n\n" \
               f"〖当前场景〗\n"\
               f"{get_position_description(status.position, status.spot)}\n"
        else:
            desc = f"〖爱丽丝的状态栏〗\n爱丽丝的职业：Lv.{status.level}的见习勇者\n" \
                   f"经验值：{status.exp}/{status.level * 100}\n" \
                   f"生命值：{status.hp}/{status.hpmax + profession.hp}\n" \
                   f"攻击力：{status.attack + profession.attack}\n" \
                   f"防御力：{status.defense + profession.defense}\n" \
                   f"暴击率：{status.crit}%\n攻击范围：{profession.range}\n" \
                   f"持有的财富：{status.coins}点信用积分\n装备：“光之剑”（电磁炮）。\n\n"\
                   f"〖当前场景〗\n"\
                   f"{get_position_description(status.position, status.spot)}\n"
        return desc


def move_position(position_id) -> str:
    if position_id >= 0:
        session = Session()
        status = session.query(Status).filter_by(status_id=0).first()
        position = get_position(position_id)
        if position is not None:
            area = get_area(position.area)
            status.position = position_id
            status.spot = 0
            session.commit()
            session.close()
            if position.station != 1:
                return f"爱丽丝来到了{area.area_name}的〖{position.position_name}〗场景。{position.description}"
            else:
                return f"爱丽丝来到了{area.area_name}的〖{position.position_name}〗场景。{position.description}" \
                       f"（这里是一个铁路站点，可以使用take_railway能力搭乘列车直接前往铁路线上的其他站点。）"
        else:
            return "不存在这个地点！"
    elif position_id == -2:
        session = Session()
        status = session.query(Status).filter_by(status_id=0).first()
        status.position = 63  # 游戏开发部活动室
        status.spot = 0
        session.commit()
        session.close()
        return "经过一段时间，爱丽丝回到了千禧年的〖游戏开发部活动室〗。"
    elif position_id == -3:
        session = Session()
        status = session.query(Status).filter_by(status_id=0).first()
        status.position = 10  # 沙勒生活区休息室
        status.spot = 0
        session.commit()
        session.close()
        return "经过一段时间，爱丽丝来到了沙勒-生活区的〖休息室〗。"
    elif position_id == -1:
        session = Session()
        status = session.query(Status).filter_by(status_id=0).first()
        position = get_position(status.position)
        area = get_area(position.area)
        session.close()
        return "[EXIT_AREA]"
    else:
        return "无效的参数。"


def move_default_position(school_id, area_id) -> str:
    if school_id == 0:
        area = get_area(area_id)
        if area.default_p == 0:
            return "该地点目前无法进入。"
        session = Session()
        status = session.query(Status).filter_by(status_id=0).first()
        position = get_position(area.default_p)
        status.position = area.default_p
        status.spot = 0
        session.commit()
        session.close()
        return f"爱丽丝来到了〖{position.position_name}〗场景。{position.description}"
    elif area_id == 0:
        school = get_school(school_id)
        if school.default_p == 0:
            return "该地点目前无法进入。"
        session = Session()
        status = session.query(Status).filter_by(status_id=0).first()
        position = get_position(school.default_p)
        status.position = school.default_p
        status.spot = 0
        session.commit()
        session.close()
        return f"爱丽丝来到了〖{position.position_name}〗场景。{position.description}"


def find_route(steps: int, school_id, area_id) -> str:
    global available_move_targets, available_railway_targets, available_areas, available_schools
    status = query_status()
    if steps == 0:
        available_move_targets, desc = get_available_position(status.position)
    elif steps == 1:
        available_areas, desc = get_available_area(status.position)
    elif steps == 2:
        available_schools, desc = get_available_school(status.position)
    elif steps == 3:
        available_areas, desc = get_all_area(school_id=school_id)
    elif steps == 4:
        available_move_targets, desc = get_all_position(area_id=area_id)
    elif steps == 5:  # 铁道交通
        available_railway_targets, desc = get_railway_station(status.position)
    return desc


# 查询当前站点是否可以乘坐铁路
def check_railway() -> bool:
    status = query_status()
    position = get_position(status.position)
    if position.station == 1:
        print(f"是否是车站：是")
        return True
    else:
        print(f"是否是车站：否")
        return False


alice_query = on_command("爱丽丝状态")
map_guide = on_command("地图")
position_map = on_command("地点地图")
area_map = on_command("区域地图")
school_map = on_command("校区地图")


@alice_query.handle()
async def alice_status():
    await alice_query.send(get_status_description())


@map_guide.handle()
async def show_map_guide():
    await map_guide.send("输入“/地点地图 {area_id}”、“/区域地图 {school_id}”或者“/校区地图”查看地图详情。"
                         "参数省略时表示查询当前地点或者区域。")


@position_map.handle()
async def show_position_map(event: MessageEvent):
    area_id = event.get_plaintext().replace("/地点地图", "").strip()
    if area_id.isdigit() and area_id != "":
        await position_map.send(get_all_position_by_area(area_id))
    else:
        status = query_status()
        temp, desc = get_available_position(status.position)
        await position_map.send(desc)


@area_map.handle()
async def show_area_map(event: MessageEvent):
    school_id = event.get_plaintext().replace("/区域地图", "").strip()
    if school_id.isdigit() and school_id != "":
        await position_map.send(get_all_area_by_school(school_id))
    else:
        status = query_status()
        temp, desc = get_available_area(status.position)
        await area_map.send(desc)


@school_map.handle()
async def show_school_map():
    status = query_status()
    await school_map.send(get_all_school())




