import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.db import Base

# 데이터베이스 URL (실제 운영 시에는 .env 파일에서 관리 권장)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/unipass")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # 테이블 생성 (기존 테이블이 없으면 생성)
    Base.metadata.create_all(bind=engine)
