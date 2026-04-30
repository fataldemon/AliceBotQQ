from contextvars import ContextVar

current_group_id: ContextVar[str] = ContextVar("current_group_id", default="")