import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base

load_dotenv()

sqlconn = os.environ.get("SQLALCHEMY_DATABASE_URL")
engine = create_engine(sqlconn, echo=False)

# 创建一个基类，用于声明类定义
Base = declarative_base()
