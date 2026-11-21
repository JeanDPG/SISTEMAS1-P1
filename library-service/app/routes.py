from datetime import datetime, timezone
from quart import Blueprint, request, jsonify
from pymongo import ReturnDocument
from app.mongodb_client import get_db

library_bp = Blueprint("library", __name__)


def serialize_mongo_doc(doc: dict | None) -> dict | None:
    """Serializa ObjectIds y datetimes para que sean JSON-serializables."""
    if not doc or not isinstance(doc, dict):
        return doc
    clean = {}
    for k, v in doc.items():
        if k == "_id":
            clean["_id"] = str(v)
        elif isinstance(v, datetime):
            clean[k] = v.isoformat()
        elif isinstance(v, list):
            clean_list = []
            for item in v:
                if isinstance(item, dict):
                    clean_list.append(serialize_mongo_doc(item))
                elif isinstance(item, datetime):
                    clean_list.append(item.isoformat())
                else:
                    clean_list.append(item)
            clean[k] = clean_list
        elif isinstance(v, dict):
            clean[k] = serialize_mongo_doc(v)
        else:
            clean[k] = v
    return clean


@library_bp.before_request
async def verify_auth_header():
    """
    Nginx realiza la autenticación previa e inyecta la cabecera 'X-User-Id'.
    Este microservicio confía únicamente en esa cabecera.
    """
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        return jsonify({"error": "No autorizado: falta cabecera de identidad X-User-Id"}), 401


# ==============================================================================
# ENDPOINTS DE GESTIÓN DE LIBROS
# ==============================================================================

@library_bp.get("/books")
async def list_books():
    """
    GET /library/books
    Lista todos los libros existentes en la colección 'books'.
    """
    db = get_db()
    cursor = db.books.find({})
    books = await cursor.to_list(length=None)
    return jsonify([serialize_mongo_doc(b) for b in books]), 200


@library_bp.post("/books")
async def create_book():
    """
    POST /library/books
    Crea un nuevo libro en la colección 'books'.
    El campo 'loan_history' se inicializa como array vacío ([]).
    """
    data = await request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Payload JSON requerido o malformado"}), 400

    isbn = data.get("isbn")
    title = data.get("title")
    author = data.get("author")
    year = data.get("year")
    publisher = data.get("publisher")
    available_stock = data.get("available_stock", 0)

    # Validación rigurosa de campos obligatorios (evita cadenas vacías o tipos erróneos)
    if (
        not isbn or not isinstance(isbn, (str, int)) or not str(isbn).strip() or
        not title or not isinstance(title, str) or not title.strip() or
        not author or not isinstance(author, str) or not author.strip()
    ):
        return jsonify({"error": "Faltan campos obligatorios: isbn, title y author (deben ser no vacíos)"}), 400

    isbn = str(isbn).strip()
    title = title.strip()
    author = author.strip()

    if year is not None:
        try:
            year = int(year)
        except (ValueError, TypeError):
            return jsonify({"error": "El campo 'year' debe ser un número entero"}), 400

    try:
        available_stock = int(available_stock)
        if available_stock < 0:
            return jsonify({"error": "El stock disponible no puede ser negativo"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "available_stock debe ser un número entero"}), 400

    db = get_db()

    # Comprobar si ya existe un libro con ese ISBN
    existing = await db.books.find_one({"isbn": isbn})
    if existing:
        return jsonify({"error": f"Ya existe un libro con el ISBN '{isbn}'"}), 409

    new_book = {
        "isbn": isbn,
        "title": title,
        "author": author,
        "year": year,
        "publisher": str(publisher).strip() if publisher is not None else "",
        "available_stock": available_stock,
        "loan_history": []
    }

    await db.books.insert_one(new_book)
    return jsonify({
        "message": "Libro creado correctamente",
        "book": serialize_mongo_doc(new_book)
    }), 201


@library_bp.delete("/books/<isbn>")
async def delete_book(isbn: str):
    """
    DELETE /library/books/<isbn>
    Borra un libro existente.
    Controla el caso de borrar un libro que tiene préstamos activos
    (return_date == None), rechazando el borrado hasta su devolución.
    """
    db = get_db()
    book = await db.books.find_one({"isbn": str(isbn)})
    if not book:
        return jsonify({"error": f"No se encontró el libro con ISBN '{isbn}'"}), 404

    # Verificar si hay préstamos activos
    active_loans = [
        loan for loan in book.get("loan_history", [])
        if loan.get("return_date") is None
    ]
    if active_loans:
        return jsonify({
            "error": "No se puede borrar el libro porque tiene préstamos activos pendientes de devolución"
        }), 409

    await db.books.delete_one({"isbn": str(isbn)})
    return jsonify({"message": f"Libro con ISBN '{isbn}' eliminado correctamente"}), 200


@library_bp.get("/books/out-of-stock")
async def get_out_of_stock_books():
    """
    GET /library/books/out-of-stock
    Lista todos los libros que tengan stock igual a 0.
    """
    db = get_db()
    cursor = db.books.find({"available_stock": 0})
    books = await cursor.to_list(length=None)
    return jsonify([serialize_mongo_doc(b) for b in books]), 200


@library_bp.get("/books/<isbn>")
async def get_book(isbn: str):
    """
    GET /library/books/<isbn>
    Obtiene información de un libro, así como la lista completa de préstamos.
    """
    db = get_db()
    book = await db.books.find_one({"isbn": str(isbn)})
    if not book:
        return jsonify({"error": f"No se encontró el libro con ISBN '{isbn}'"}), 404

    return jsonify(serialize_mongo_doc(book)), 200


# ==============================================================================
# ENDPOINTS DE PRÉSTAMOS (LOANS)
# ==============================================================================

@library_bp.get("/loans/active")
async def get_active_loans():
    """
    GET /library/loans/active
    Lista los libros que están actualmente prestados al usuario autenticado (X-User-Id).
    """
    user_id = request.headers.get("X-User-Id")
    db = get_db()

    cursor = db.books.find({
        "loan_history": {
            "$elemMatch": {
                "user_id": user_id,
                "return_date": None
            }
        }
    })
    books = await cursor.to_list(length=None)
    return jsonify([serialize_mongo_doc(b) for b in books]), 200


@library_bp.get("/loans/history")
async def get_loan_history():
    """
    GET /library/loans/history
    Lista el histórico completo de préstamos del usuario autenticado (X-User-Id).
    Garantiza que no se puede acceder al historial de otro usuario.
    """
    user_id = request.headers.get("X-User-Id")
    db = get_db()

    cursor = db.books.find({"loan_history.user_id": user_id})
    books = await cursor.to_list(length=None)

    history = []
    for book in books:
        for loan in book.get("loan_history", []):
            if loan.get("user_id") == user_id:
                loan_date = loan.get("loan_date")
                if isinstance(loan_date, datetime):
                    loan_date = loan_date.isoformat()
                return_date = loan.get("return_date")
                if isinstance(return_date, datetime):
                    return_date = return_date.isoformat()
                history.append({
                    "isbn": book.get("isbn"),
                    "title": book.get("title"),
                    "author": book.get("author"),
                    "loan_date": loan_date,
                    "return_date": return_date
                })

    return jsonify(history), 200


@library_bp.post("/books/<isbn>/borrow")
async def borrow_book(isbn: str):
    """
    POST /library/books/<isbn>/borrow
    Toma en préstamo un libro por parte del usuario autenticado (X-User-Id).
    
    OPERACIÓN ATÓMICA DE MONGODB (Evita condiciones de carrera en stock):
    Utiliza find_one_and_update() con filtro atómico 'available_stock > 0'.
    """
    user_id = request.headers.get("X-User-Id")
    db = get_db()

    now_iso = datetime.now(timezone.utc).isoformat()
    new_loan = {
        "user_id": user_id,
        "loan_date": now_iso,
        "return_date": None
    }

    # Operación atómica de MongoDB
    updated_book = await db.books.find_one_and_update(
        {
            "isbn": str(isbn),
            "available_stock": {"$gt": 0}
        },
        {
            "$inc": {"available_stock": -1},
            "$push": {"loan_history": new_loan}
        },
        return_document=ReturnDocument.AFTER
    )

    if not updated_book:
        # Verificar si no existía el libro o no quedaba stock disponible
        exists = await db.books.find_one({"isbn": str(isbn)})
        if not exists:
            return jsonify({"error": f"No se encontró el libro con ISBN '{isbn}'"}), 404
        return jsonify({"error": f"No hay stock disponible para el libro con ISBN '{isbn}'"}), 400

    return jsonify({
        "message": f"Préstamo realizado con éxito para el usuario '{user_id}'",
        "book": serialize_mongo_doc(updated_book)
    }), 200


@library_bp.post("/books/<isbn>/return")
async def return_book(isbn: str):
    """
    POST /library/books/<isbn>/return
    Devuelve un libro que estaba prestado al usuario autenticado (X-User-Id).
    
    OPERACIÓN ATÓMICA DE MONGODB:
    Actualiza el préstamo activo en loan_history fijando return_date e incrementa available_stock.
    """
    user_id = request.headers.get("X-User-Id")
    db = get_db()

    now_iso = datetime.now(timezone.utc).isoformat()

    # Operación atómica: busca el libro que tenga un préstamo activo de este usuario
    updated_book = await db.books.find_one_and_update(
        {
            "isbn": str(isbn),
            "loan_history": {
                "$elemMatch": {
                    "user_id": user_id,
                    "return_date": None
                }
            }
        },
        {
            "$inc": {"available_stock": 1},
            "$set": {
                "loan_history.$.return_date": now_iso
            }
        },
        return_document=ReturnDocument.AFTER
    )

    if not updated_book:
        exists = await db.books.find_one({"isbn": str(isbn)})
        if not exists:
            return jsonify({"error": f"No se encontró el libro con ISBN '{isbn}'"}), 404
        return jsonify({
            "error": f"El usuario '{user_id}' no tiene ningún préstamo activo del libro '{isbn}'"
        }), 400

    return jsonify({
        "message": f"Libro con ISBN '{isbn}' devuelto correctamente",
        "book": serialize_mongo_doc(updated_book)
    }), 200
