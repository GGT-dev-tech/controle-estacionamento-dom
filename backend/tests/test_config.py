from app.config import Settings


def test_normaliza_postgres_curto_para_asyncpg():
    s = Settings(database_url="postgres://user:pass@host:5432/db")
    assert s.database_url == "postgresql+asyncpg://user:pass@host:5432/db"


def test_normaliza_postgresql_para_asyncpg():
    s = Settings(database_url="postgresql://user:pass@host:5432/db")
    assert s.database_url == "postgresql+asyncpg://user:pass@host:5432/db"


def test_normaliza_mysql_para_aiomysql():
    s = Settings(database_url="mysql://user:pass@host:3306/db")
    assert s.database_url == "mysql+aiomysql://user:pass@host:3306/db"


def test_mantem_url_ja_com_driver_explicito():
    assert Settings(database_url="postgresql+asyncpg://u:p@h/d").database_url == "postgresql+asyncpg://u:p@h/d"
    assert Settings(database_url="mysql+aiomysql://u:p@h/d").database_url == "mysql+aiomysql://u:p@h/d"
