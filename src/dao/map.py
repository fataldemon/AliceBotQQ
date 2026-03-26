from sqlalchemy import Column, Integer, String, and_
from sqlalchemy.orm import declarative_base, sessionmaker
from src.dao.dbengine import engine


# 创建一个基类，用于声明类定义
Base = declarative_base()


# 世界观
class Field(Base):
    __tablename__ = 't_field'

    field_id = Column(Integer, primary_key=True)
    field_name = Column(String(50), nullable=False)
    description = Column(String(1000), nullable=True)


# 学校自治区
class School(Base):
    __tablename__ = 't_school'

    school_id = Column(Integer, primary_key=True)
    school_name = Column(String(50), nullable=False)
    field = Column(Integer, nullable=False, default=1)
    description = Column(String(1000), nullable=True)
    default_p = Column(Integer, nullable=False)


# 校内区划
class Area(Base):
    __tablename__ = 't_area'

    area_id = Column(Integer, primary_key=True)
    area_name = Column(String(50), nullable=False)
    field = Column(Integer, nullable=False, default=1)
    school = Column(Integer, nullable=False)
    description = Column(String(1000), nullable=True)
    # 是否冒险区域
    adventure = Column(Integer, nullable=False, default=0)
    default_p = Column(Integer, nullable=False)


# 地点
class Position(Base):
    __tablename__ = 't_position'

    position_id = Column(Integer, primary_key=True)
    position_name = Column(String(50), nullable=False)
    description = Column(String(1000), nullable=True)
    field = Column(Integer, nullable=False, default=1)
    school = Column(Integer, nullable=False)
    area = Column(Integer, nullable=False)
    size = Column(Integer, nullable=False, default=1)
    station = Column(Integer, nullable=False, default=0)


# 创建表
Base.metadata.create_all(engine)

# 创建一个用于数据库交互的Session类
Session = sessionmaker(bind=engine)


def get_field(field_id) -> Field:
    session = Session()
    field = session.query(Field).filter_by(field_id=field_id).first()
    session.close()
    return field


def get_school(school_id) -> Field:
    session = Session()
    school = session.query(School).filter_by(school_id=school_id).first()
    session.close()
    return school


def get_area(area_id) -> Area:
    session = Session()
    area = session.query(Area).filter_by(area_id=area_id).first()
    session.close()
    return area


def get_position(position_id) -> Position:
    session = Session()
    position = session.query(Position).filter_by(position_id=position_id).first()
    session.close()
    return position


def get_position_description(position_id: int, spot: int) -> str:
    session = Session()
    position = session.query(Position).filter_by(position_id=position_id).first()
    field = session.query(Field).filter_by(field_id=position.field).first()
    school = session.query(School).filter_by(school_id=position.school).first()
    area = session.query(Area).filter_by(area_id=position.area).first()
    return f"你当前所在的位置：{field.field_name}-{school.school_name}-{area.area_name}-{position.position_name} 的位置{spot}\n" \
           f"场景信息：\n" \
           f"   〖{field.field_name}〗：\n" \
           f"       {field.description}\n" \
           f"   〖{school.school_name}〗：\n" \
           f"       {school.description}\n" \
           f"   〖{area.area_name}〗：\n" \
           f"       {area.description}\n" \
           f"   〖{position.position_name}〗：\n" \
           f"       {position.description}"


def get_size(position_id) -> int:
    session = Session()
    position = session.query(Position).filter_by(position_id=position_id).first()
    session.close()
    return position.size


# 按照当前位置查找所有其他位置
def get_available_position(position_id) -> tuple:
    session = Session()
    position_base = session.query(Position).filter_by(position_id=position_id).first()
    area_base = session.query(Area).filter_by(area_id=position_base.area).first()
    available_positions = session.query(Position).filter(
        and_(Position.area == position_base.area, Position.position_id != position_id)
    ).all()
    available_areas = session.query(Area).filter(
            and_(Area.school == position_base.school, Area.area_id != area_base.area_id)
    ).all()
    session.close()
    available_options = ['E', 'H']
    desc = "可以前往的地点选项（输入选项前的数字或者字母）：\n"
    for position in available_positions:
        desc += f"[{position.position_id}: 前往〖{position.position_name}〗：{position.description}],"
        available_options.append(str(position.position_id))
    desc += f"[E: 往外走，离开〖{area_base.area_name}〗，到〖{area_base.area_name}〗的外面去。可以通往的区域有"
    for area in available_areas:
        desc += f"〖{area.area_name}〗"
    desc += '。]'
    if position_id != 63:
        desc += f",[H: 回到千禧年的〖游戏开发部〗。游戏开发部活动室就像是爱丽丝的家。]"
    if not (1 <= position_id <= 15):
        desc += f",[S: 访问沙勒，找老师玩。沙勒是老师办公和生活的地方，爱丽丝没有值日的平时也喜欢到沙勒找老师玩。]"
    return available_options, desc


# 按照区域查找所有位置
def get_all_position(area_id) -> tuple:
    session = Session()
    area = session.query(Area).filter_by(area_id=area_id).first()
    positions = session.query(Position).filter_by(area=area_id).all()
    session.close()
    desc = f"在〖{area.area_name}〗区域下，可以前往的地点选项（输入选项前的数字或者字母）：\n"
    available_options = []
    for position in positions:
        desc += f"[{position.position_id}: 前往〖{position.position_name}〗：{position.description}],"
        available_options.append(str(position.position_id))
    return available_options, desc


# 按照当前位置查找所有其他区域
def get_available_area(position_id) -> tuple:
    session = Session()
    position_base = session.query(Position).filter_by(position_id=position_id).first()
    area_base = session.query(Area).filter_by(area_id=position_base.area).first()
    school_base = session.query(School).filter_by(school_id=position_base.school).first()
    available_areas = session.query(Area).filter(
            and_(Area.school == position_base.school, Area.area_id != area_base.area_id)
    ).all()
    available_schools = session.query(School).filter(
        and_(School.school_id != position_base.school)
    ).all()
    session.close()
    desc = "可以前往的区域选项（输入选项前的数字或者字母）：\n"
    available_options = ['E', 'H']
    for area in available_areas:
        desc += f"[{area.area_id}: 前往〖{area.area_name}〗：{area.description}],"
        available_options.append(str(area.area_id))
    desc += f"[E: 往外走，离开〖{school_base.school_name}〗，到〖{school_base.school_name}〗的外面去。可以通往的校区有"
    for school in available_schools:
        desc += f"〖{school.school_name}〗"
    desc += '。],'
    desc += f"[H: 回家，回到千禧年的〖游戏开发部〗。游戏开发部活动室就是爱丽丝的家。]"
    return available_options, desc


# 按照学校查找所有区域
def get_all_area(school_id) -> tuple:
    session = Session()
    school = session.query(School).filter_by(school_id=school_id).first()
    areas = session.query(Area).filter_by(school=school_id).all()
    session.close()
    desc = f"在〖{school.school_name}〗境内，可以前往的区域选项（输入选项前的数字或者字母）：\n"
    available_options = []
    for area in areas:
        desc += f"[{area.area_id}: 前往〖{area.area_name}〗：{area.description}],"
        available_options.append(str(area.area_id))
    return available_options, desc


# 按照当前位置查找所有其他校区
def get_available_school(position_id) -> tuple:
    session = Session()
    position_base = session.query(Position).filter_by(position_id=position_id).first()
    available_schools = session.query(School).filter(School.school_id != position_base.school).all()
    session.close()
    desc = "可以前往的校区选项（输入选项前的数字或者字母）：\n"
    available_options = ['H']
    for school in available_schools:
        desc += f"[{school.school_id}: 前往〖{school.school_name}〗：{school.description}],"
        available_options.append(str(school.school_id))
    desc += f"[H: 回家，回到千禧年的〖游戏开发部〗。游戏开发部活动室就是爱丽丝的家。]"
    return available_options, desc


# 查找所有校区
def get_all_school() -> str:
    session = Session()
    schools = session.query(School).filter_by(field=1).all()
    session.close()
    desc = f"在〖基沃托斯〗市内，可以前往的校区选项（输入选项前的数字或者字母）：\n"
    for school in schools:
        desc += f"[{school.school_id}: 前往〖{school.school_name}〗：{school.description}]"
    return desc


# 按照校区查找所有区域
def get_all_area_by_school(school_id) -> str:
    session = Session()
    school = session.query(School).filter_by(school_id=school_id).first()
    areas = session.query(Area).filter_by(school=school_id).all()
    session.close()
    desc = f"在〖{school.school_name}〗校区内，可以前往的区域选项（输入选项前的数字或者字母）：\n"
    for area in areas:
        desc += f"{area.area_id}: 前往〖{area.area_name}〗：{area.description}\n"
    return desc


# 按照区域查找所有地点
def get_all_position_by_area(area_id) -> str:
    session = Session()
    area = session.query(Area).filter_by(area_id=area_id).first()
    positions = session.query(Position).filter_by(area=area_id).all()
    session.close()
    desc = f"在〖{area.area_name}〗区域内，可以前往的区域选项（输入选项前的数字或者字母）：\n"
    for position in positions:
        desc += f"{position.position_id}: 前往〖{position.position_name}〗：{position.description}\n"
    return desc


# 查询铁路状况
def get_railway_station(position_id) -> tuple:
    session = Session()
    stations = session.query(Position).filter(
        and_(Position.station == 1, Position.position_id != position_id)).all()
    desc = f"通过列车轨道可以直达的站点选项（输入选项前的数字或者字母）：\n"
    available_options = []
    for station in stations:
        area = session.query(Area).filter_by(area_id=station.area).first()
        desc += f"{station.position_id}: 前往〖{area.area_name}〗区域的〖{station.position_name}〗：{station.description}\n"
        available_options.append(str(station.position_id))
    session.close()
    return available_options, desc



