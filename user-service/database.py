import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Se obtiene la URL desde las variables de entorno o usa la por defecto
# Nota: En Docker se usa host "postgres-db", localmente se puede usar "localhost:9999"
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://alumnodb:1234@localhost:9999/si1"
)

# Engine asíncrono
engine = create_async_engine(
    DATABASE_URL, 
    echo=False,           # Cambiar a True para ver las sentencias SQL en consola
    future=True
)

# Generador de sesiones asíncronas
async_session = sessionmaker(
    engine, 
    expire_on_commit=False, 
    class_=AsyncSession
)

async def get_db():
    """
    Generador de contexto/sesión para ejecutar consultas asíncronas con SQLAlchemy.
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()