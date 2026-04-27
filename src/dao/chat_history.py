import datetime
from datetime import timedelta

from sqlalchemy import Column, Integer, String, Text, DateTime, func, Index, inspect, text
from sqlalchemy.orm import sessionmaker

from src.dao.dbengine import engine, Base


class ChatHistory(Base):
    __tablename__ = 't_chat_history'
    __table_args__ = (
        Index('idx_group_summary_time', 'group_id', 'is_summary', 'timestamp'),
        Index('idx_request_id', 'request_id'),          # 可选，便于追踪
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(String(50), nullable=False, index=False)  # 索引由复合索引覆盖，单列索引可省
    timestamp = Column(DateTime, server_default=func.now())
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=True)
    thought = Column(Text, nullable=True)
    action_name = Column(String(50), nullable=True)
    action_input = Column(Text, nullable=True)
    function_output = Column(Text, nullable=True)
    request_id = Column(String(50), nullable=True)
    is_summary = Column(Integer, default=0)


# 创建"user"表
Base.metadata.create_all(engine)

# 创建一个用于数据库交互的Session类
Session = sessionmaker(bind=engine)


def init_fts():
    """
    初始化全文搜索支持 (虚拟表 + 触发器 + 数据同步)
    可重复调用, 安全幂等
    """
    session = Session()
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        # 1. 创建 FTS5 虚拟表 (如果不存在)
        if "t_chat_history_fts" not in existing_tables:
            session.execute(text("""
                CREATE VIRTUAL TABLE t_chat_history_fts 
                USING fts5(content, tokenize = 'unicode61')
            """))
            print("[FTS] 虚拟表 t_chat_history_fts 创建成功")
        else:
            print("[FTS] 虚拟表已存在, 跳过创建")

        # 2. 同步已有数据到 FTS 表 (仅当 FTS 表为空时执行)
        count = session.execute(text("SELECT COUNT(*) FROM t_chat_history_fts")).scalar()
        if count == 0:
            # 将普通表中的所有 content 复制到 FTS 表
            session.execute(text("""
                INSERT INTO t_chat_history_fts(rowid, content)
                SELECT id, content FROM t_chat_history
                WHERE content IS NOT NULL AND content != ''
            """))
            print(f"[FTS] 已同步 {session.execute(text('SELECT COUNT(*) FROM t_chat_history_fts')).scalar()} 条记录到全文索引")
        else:
            print(f"[FTS] 全文索引已有 {count} 条数据, 跳过同步")

        # 3. 创建触发器 (IF NOT EXISTS 保证不重复)
        triggers = [
            """
            CREATE TRIGGER IF NOT EXISTS t_chat_history_ai
            AFTER INSERT ON t_chat_history
            BEGIN
                INSERT INTO t_chat_history_fts(rowid, content)
                VALUES (new.id, new.content);
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS t_chat_history_ad
            AFTER DELETE ON t_chat_history
            BEGIN
                DELETE FROM t_chat_history_fts WHERE rowid = old.id;
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS t_chat_history_au
            AFTER UPDATE OF content ON t_chat_history
            BEGIN
                UPDATE t_chat_history_fts SET content = new.content WHERE rowid = old.id;
            END;
            """
        ]
        for sql in triggers:
            session.execute(text(sql))
        session.commit()
        print("[FTS] 触发器检查/创建完成")

    except Exception as e:
        print(f"[FTS] 初始化失败: {e}")
        session.rollback()
    finally:
        session.close()


def save_chat_record(group_id: str, role: str, content: str = "", thought: str = "",
                     action_name: str = "", action_input: str = "",
                     function_output: str = "", request_id: str = "", is_summary: int = 0):
    session = Session()
    try:
        record = ChatHistory(
            group_id=group_id, role=role, content=content, thought=thought,
            action_name=action_name, action_input=action_input,
            function_output=function_output, request_id=request_id, is_summary=is_summary
        )
        session.add(record)
        session.commit()
    finally:
        session.close()


def load_recent_history(group_id: str, limit: int = 20):
    """加载最近 limit 条非摘要消息 + 最新摘要"""
    session = Session()
    try:
        # 非摘要消息（普通对话）
        logs = session.query(ChatHistory).filter(
            ChatHistory.group_id == group_id,
            ChatHistory.is_summary == 0
        ).order_by(ChatHistory.timestamp.desc()).limit(limit).all()
        logs.reverse()
        history = [{"role": log.role, "content": log.content} for log in logs]

        # 最新摘要
        summary_obj = session.query(ChatHistory).filter(
            ChatHistory.group_id == group_id,
            ChatHistory.is_summary == 1
        ).order_by(ChatHistory.timestamp.desc()).first()
        summary = summary_obj.content if summary_obj else ""
        return history, summary
    finally:
        session.close()


def recall_memory(group_id: str, time_range: str = "", keywords: str = "",
                  limit: int = 5, context_lines: int = 1) -> str:
    """
    根据时间和关键词召回历史对话，并附带命中消息的上下文。
    参数：
        group_id: 群组ID
        time_range: 时间范围（自然语言或具体时间）
        keywords: 搜索关键词
        limit: 最多命中多少条消息（锚点数量）
        context_lines: 每条命中消息前后各取多少条消息（默认1）
    返回：
        格式化的对话片段，包含时间和角色。
    """
    session = Session()
    try:
        MAX_SPAN_DAYS = 90
        MAX_LIMIT = 10  # 锚点最大数量
        MAX_CONTEXT = 5  # 上下文最大行数（前后各不超过5）
        MAX_TOTAL_MSGS = 30  # 最终返回的总消息数上限

        limit = min(limit, MAX_LIMIT)
        context_lines = min(context_lines, MAX_CONTEXT)

        # ---------- 1. 解析时间范围 ----------
        start_dt, end_dt = None, None
        if time_range:
            start_dt, end_dt = parse_natural_time(time_range)
            if start_dt is None and end_dt is None:
                start_dt, end_dt = parse_explicit_time(time_range)
            if start_dt is None and end_dt is None:
                return f"时间格式无法识别：'{time_range}'。请使用自然语言或具体时间格式。"
            if start_dt is not None and end_dt is None:
                end_dt = datetime.now()
            if end_dt is not None and start_dt is None:
                start_dt = end_dt - timedelta(days=7)
            if start_dt > end_dt:
                return "开始时间不能晚于结束时间。"
            if (end_dt - start_dt).days > MAX_SPAN_DAYS:
                return f"时间跨度不能超过 {MAX_SPAN_DAYS} 天。"

        # ---------- 2. 获取命中消息的 ID（锚点）----------
        base_query = session.query(ChatHistory.id).filter(ChatHistory.group_id == group_id)
        if start_dt:
            base_query = base_query.filter(ChatHistory.timestamp >= start_dt)
        if end_dt:
            base_query = base_query.filter(ChatHistory.timestamp <= end_dt)

        if keywords:
            # FTS 搜索符合条件的 rowid
            fts_rows = session.execute(
                text("SELECT rowid FROM t_chat_history_fts WHERE content MATCH :kw"),
                {"kw": keywords}
            ).fetchall()
            match_ids = {row[0] for row in fts_rows}
            if not match_ids:
                return "未找到匹配关键词的历史记录。"
            base_query = base_query.filter(ChatHistory.id.in_(match_ids))

        anchor_ids = [row[0] for row in base_query.order_by(ChatHistory.timestamp.desc()).limit(limit).all()]
        if not anchor_ids:
            return "未找到相关历史记录。"

        # ---------- 3. 获取每一条锚点的上下文消息ID ----------
        def get_surrounding_ids(msg_id: int, before: int, after: int) -> set:
            """获取某条消息前后各若干条消息的ID（同一群组，按时间顺序）"""
            # 获取该消息的时间戳和索引位置
            msg = session.query(ChatHistory).filter(ChatHistory.id == msg_id).first()
            if not msg:
                return set()
            # 查询该群组中所有消息的时间戳和ID，按时间升序
            all_msgs = session.query(ChatHistory.id, ChatHistory.timestamp).filter(
                ChatHistory.group_id == group_id
            ).order_by(ChatHistory.timestamp).all()
            # 找到当前消息的索引
            idx = None
            for i, (rid, ts) in enumerate(all_msgs):
                if rid == msg_id:
                    idx = i
                    break
            if idx is None:
                return set()
            start_idx = max(0, idx - before)
            end_idx = min(len(all_msgs), idx + after + 1)
            return {all_msgs[i][0] for i in range(start_idx, end_idx)}

        context_ids = set()
        for aid in anchor_ids:
            context_ids.update(get_surrounding_ids(aid, context_lines, context_lines))
        # 合并锚点本身
        all_ids = context_ids.union(anchor_ids)

        # ---------- 4. 查询完整消息并按时间排序 ----------
        records = session.query(ChatHistory).filter(ChatHistory.id.in_(all_ids)).order_by(ChatHistory.timestamp).all()
        # 如果总消息数超过限制，只保留最新的 MAX_TOTAL_MSGS 条
        if len(records) > MAX_TOTAL_MSGS:
            records = records[-MAX_TOTAL_MSGS:]

        # ---------- 5. 格式化输出 ----------
        lines = []
        for rec in records:
            time_str = rec.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            role_name = {"user": "用户", "assistant": "爱丽丝", "function": "系统"}.get(rec.role, rec.role)
            content_preview = rec.content[:200] + ("..." if len(rec.content) > 200 else "")
            lines.append(f"[{time_str}] {role_name}: {content_preview}")
        return "\n".join(lines)
    finally:
        session.close()


def parse_natural_time(text: str) -> tuple:
    """解析自然语言，返回 (start_dt, end_dt)"""
    now = datetime.now()
    text = text.strip().lower()
    match = re.search(r'最近\s*(\d+)\s*(小时|小时前|天|天前|周|周前)', text)
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        if '小时' in unit:
            return now - timedelta(hours=num), now
        elif '天' in unit:
            return now - timedelta(days=num), now
        elif '周' in unit:
            return now - timedelta(weeks=num), now
    if '今天' in text:
        start = now.replace(hour=0, minute=0, second=0)
        return start, now
    if '昨天' in text:
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=1) - timedelta(seconds=1)
        return start, end
    if '前天' in text:
        start = (now - timedelta(days=2)).replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=1) - timedelta(seconds=1)
        return start, end
    if '本周' in text:
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0)
        return start, now
    if '上周' in text:
        start = now - timedelta(days=now.weekday() + 7)
        start = start.replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=7) - timedelta(seconds=1)
        return start, end
    return None, None


def parse_explicit_time(text: str) -> tuple:
    """解析具体时间范围或单点，返回 (start_dt, end_dt)"""
    if ' to ' in text.lower():
        parts = text.lower().split(' to ')
        if len(parts) == 2:
            start = parse_single_datetime(parts[0].strip())
            end = parse_single_datetime(parts[1].strip())
            if start and end:
                return start, end
    dt = parse_single_datetime(text)
    if dt:
        return dt, None
    return None, None


def parse_single_datetime(dt_str: str):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str.strip(), fmt)
        except ValueError:
            continue
    return None
