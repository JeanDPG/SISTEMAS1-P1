import os

try:
    from pymongo import AsyncMongoClient
except ImportError:
    from motor.motor_asyncio import AsyncIOMotorClient as AsyncMongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/library_db")

_mongo_client: AsyncMongoClient | None = None
_mongo_db = None

def get_client() -> AsyncMongoClient:
    """Retorna o inicializa el cliente asíncrono de MongoDB."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = AsyncMongoClient(MONGO_URI)
    return _mongo_client

def get_db():
    """Retorna la base de datos asíncrona de MongoDB."""
    global _mongo_db
    if _mongo_db is None:
        client = get_client()
        try:
            _mongo_db = client.get_default_database()
        except Exception:
            _mongo_db = client["library_db"]
    return _mongo_db

async def close_client():
    """Cierra la conexión con MongoDB."""
    global _mongo_client, _mongo_db
    if _mongo_client is not None:
        await _mongo_client.close()
        _mongo_client = None
        _mongo_db = None
