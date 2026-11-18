import os

try:
    from pymongo import AsyncMongoClient
except ImportError:
    from motor.motor_asyncio import AsyncIOMotorClient as AsyncMongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/library_db")

mongo_client: AsyncMongoClient | None = None
mongo_db = None

def get_client() -> AsyncMongoClient:
    """Retorna o inicializa el cliente asíncrono de MongoDB."""
    global mongo_client
    if mongo_client is None:
        mongo_client = AsyncMongoClient(MONGO_URI)
    return mongo_client

def get_db():
    """Retorna la base de datos asíncrona de MongoDB."""
    global mongo_db
    if mongo_db is None:
        client = get_client()
        mongo_db = client.get_default_database()
    return mongo_db
