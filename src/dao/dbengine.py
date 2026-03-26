import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

sqlconn = os.environ.get("SQLALCHEMY_DATABASE_URL")
engine = create_engine(sqlconn, echo=False)
