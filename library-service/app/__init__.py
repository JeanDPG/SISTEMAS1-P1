import json
import os
import copy
from quart import Quart
from app.routes import library_bp
from app.mongodb_client import get_db

app = Quart(__name__)
app.register_blueprint(library_bp, url_prefix="/library")

@app.before_serving
async def startup():
    """
    Se ejecuta al iniciar el servidor ASGI:
    1. Abre la conexión asíncrona a MongoDB.
    2. Ejecuta la rutina de poblado desde populate.json si la colección 'books' está vacía.
    """
    db = get_db()

    populate_path = os.path.join(os.path.dirname(__file__), "populate.json")
    if os.path.exists(populate_path):
        try:
            count = await db.books.count_documents({})
            if count == 0:
                with open(populate_path, "r", encoding="utf-8") as f:
                    books_data = json.load(f)
                if books_data:
                    await db.books.insert_many(copy.deepcopy(books_data))
                    print(f"Base de datos poblada con {len(books_data)} libros.")
        except Exception as e:
            print(f"Advertencia al poblar la base de datos: {e}")
