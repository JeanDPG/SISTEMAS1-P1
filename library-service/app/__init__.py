import json
import os
import copy
import asyncio
from quart import Quart, jsonify
from app.routes import library_bp
from app.mongodb_client import get_db, close_client

# Compatibilidad con Flask 3.1+ en Quart
Quart.default_config = {**Quart.default_config, "PROVIDE_AUTOMATIC_OPTIONS": True}

app = Quart(__name__)
app.register_blueprint(library_bp, url_prefix="/library")

@app.errorhandler(400)
async def bad_request(e):
    return jsonify({"error": "Solicitud incorrecta"}), 400

@app.errorhandler(404)
async def not_found(e):
    return jsonify({"error": "Recurso no encontrado"}), 404

@app.errorhandler(405)
async def method_not_allowed(e):
    return jsonify({"error": "Método HTTP no permitido"}), 405

@app.errorhandler(500)
async def internal_error(e):
    return jsonify({"error": "Error interno del servidor"}), 500

@app.before_serving
async def startup():
    """
    Se ejecuta al iniciar el servidor ASGI:
    1. Abre la conexión asíncrona a MongoDB con reintentos para asegurar disponibilidad.
    2. Ejecuta la rutina de poblado desde populate.json si la colección 'books' está vacía.
    """
    db = get_db()
    populate_path = os.path.join(os.path.dirname(__file__), "populate.json")

    max_retries = 15
    for attempt in range(1, max_retries + 1):
        try:
            count = await db.books.count_documents({})
            if count == 0 and os.path.exists(populate_path):
                with open(populate_path, "r", encoding="utf-8") as f:
                    books_data = json.load(f)
                if books_data:
                    await db.books.insert_many(copy.deepcopy(books_data))
                    print(f"Base de datos poblada con {len(books_data)} libros.")
            break
        except Exception as e:
            if attempt == max_retries:
                print(f"Error definitivo al conectar/poblar MongoDB tras {max_retries} intentos: {e}")
            else:
                print(f"Intento {attempt}/{max_retries}: esperando a MongoDB ({e})...")
                await asyncio.sleep(1)

@app.after_serving
async def shutdown():
    """Cierra la conexión asíncrona con MongoDB."""
    await close_client()
