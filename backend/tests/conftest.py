import os

# 必须在导入 app.* 之前：app.database 在模块导入时即按 settings.database_url 建引擎，
# 测试环境没有 psycopg2 / PG，统一落到 sqlite（夹具各用各的 StaticPool 内存库）。
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SEED_ON_EMPTY", "false")
