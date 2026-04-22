import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 加载项目根目录的 .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
env_path = PROJECT_ROOT / '.env'
if env_path.exists():
	load_dotenv(env_path)
else:
	# 也允许在根目录之外由环境提供变量
	load_dotenv()

# 从环境变量读取 DATABASE_URL
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
	raise RuntimeError('Missing DATABASE_URL environment variable')

# 为 MySQL 创建 SQLAlchemy 引擎（不要使用 sqlite 的 check_same_thread 参数）
engine = create_engine(
	DATABASE_URL,
	pool_pre_ping=True,
	pool_recycle=3600,
)

# 会话本地工厂
SessionLocal = sessionmaker(
	autocommit=False,
	autoflush=False,
	bind=engine,
)

# 基类，用于声明模型
Base = declarative_base()


def get_db():
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()


def init_db():
	# 延迟导入模型以避免循环导入
	try:
		import backend.database.models  # noqa: F401
	except Exception:
		# 不要吞掉异常，让调用方看到错误
		raise
	Base.metadata.create_all(bind=engine)

__all__ = ['engine', 'SessionLocal', 'Base', 'DATABASE_URL', 'get_db', 'init_db']

