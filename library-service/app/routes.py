from datetime import datetime
from quart import Blueprint, request, jsonify
from app.mongodb_client import get_db

library_bp = Blueprint("library", __name__)

@library_bp.before_request
async def verify_auth_header():
    """
    Nginx inyecta la cabecera 'X-User-Id' tras validar el token con auth-service.
    Este servicio confía únicamente en ese encabezado.
    """
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        # En caso de acceso no autorizado
        return jsonify({"error": "No autorizado: falta cabecera X-User-Id"}), 401


# ==============================================================================
# ENDPOINTS DE GESTIÓN DE LIBROS
# ==============================================================================

@library_bp.post("/books")
async def create_book():
    """
    POST /library/books
    Crea un nuevo libro en la colección 'books'.
    El campo 'loan_history' se inicializa como array vacío ([]).
    """
    data = await request.get_json() or {}
    isbn = data.get("isbn")
    title = data.get("title")
    author = data.get("author")
    year = data.get("year")
    publisher = data.get("publisher")
    available_stock = data.get("available_stock", 0)

    db = get_db()

    # TODO: 1. Validar que vengan los campos obligatorios
    # TODO: 2. Comprobar que no exista ya un libro con el mismo ISBN
    # TODO: 3. Insertar el libro con 'loan_history': []
    return jsonify({"message": "Libro creado correctamente", "isbn": isbn}), 201


@library_bp.delete("/books/<isbn>")
async def delete_book(isbn: str):
    """
    DELETE /library/books/<isbn>
    Borra un libro existente.
    IMPORTANTE: Se debe controlar el caso de borrar un libro que tiene préstamos
    activos (return_date es null/None), no permitiendo borrarlo hasta su devolución.
    """
    db = get_db()

    # TODO: 1. Buscar el libro por 'isbn'
    # TODO: 2. Verificar si tiene algún préstamo activo en 'loan_history' (return_date is None)
    #          Si tiene préstamos activos -> rechazar borrado (e.g., 400 Bad Request o 409 Conflict)
    # TODO: 3. Si no tiene préstamos activos, borrar el documento de la colección 'books'
    return jsonify({"message": f"Libro {isbn} eliminado correctamente"}), 200


@library_bp.get("/books/<isbn>")
async def get_book(isbn: str):
    """
    GET /library/books/<isbn>
    Obtiene información de un libro, así como la lista completa de préstamos (loan_history).
    """
    db = get_db()

    # TODO: 1. Buscar el libro por 'isbn' en la colección 'books'
    # TODO: 2. Si no existe, devolver 404
    # TODO: 3. Devolver los datos del libro (sin el '_id' de Mongo o serializado a string)
    return jsonify({"isbn": isbn, "loan_history": []}), 200


@library_bp.get("/books/out-of-stock")
async def get_out_of_stock_books():
    """
    GET /library/books/out-of-stock
    Lista todos los libros que tengan available_stock igual a 0.
    """
    db = get_db()

    # TODO: Consultar libros con filtro {'available_stock': 0}
    return jsonify([]), 200


# ==============================================================================
# ENDPOINTS DE PRÉSTAMOS (LOANS)
# ==============================================================================

@library_bp.get("/loans/active")
async def get_active_loans():
    """
    GET /library/loans/active
    Lista los libros que actualmente están prestados al usuario autenticado (X-User-Id)
    (es decir, en su 'loan_history' existe un sub-documento con user_id == X-User-Id
    y return_date == None).
    """
    user_id = request.headers.get("X-User-Id")
    db = get_db()

    # TODO: Buscar libros donde loan_history contenga un elemento con:
    #       {'user_id': user_id, 'return_date': None}
    return jsonify([]), 200


@library_bp.get("/loans/history")
async def get_loan_history():
    """
    GET /library/loans/history
    Lista el histórico completo de préstamos del usuario autenticado (X-User-Id).
    """
    user_id = request.headers.get("X-User-Id")
    db = get_db()

    # TODO: Buscar todos los libros donde loan_history contenga {'user_id': user_id}
    return jsonify([]), 200


@library_bp.post("/books/<isbn>/borrow")
async def borrow_book(isbn: str):
    """
    POST /library/books/<isbn>/borrow
    Toma en préstamo un libro por parte del usuario autenticado (X-User-Id).
    
    OPERACIÓN ATÓMICA REQUERIDA (Evitar condiciones de carrera):
    Usar find_one_and_update() con filtro atómico:
      - Filtro: {'isbn': isbn, 'available_stock': {'$gt': 0}}
      - Update:
          {
            '$inc': {'available_stock': -1},
            '$push': {
              'loan_history': {
                'user_id': user_id,
                'loan_date': datetime.utcnow(),
                'return_date': None
              }
            }
          }
    """
    user_id = request.headers.get("X-User-Id")
    db = get_db()

    # TODO: 1. Ejecutar find_one_and_update atómico
    # TODO: 2. Si el resultado es None, determinar si el libro no existe (404) o no hay stock (400)
    # TODO: 3. Retornar confirmación del préstamo (200)
    return jsonify({"message": f"Préstamo realizado para {user_id}", "isbn": isbn}), 200


@library_bp.post("/books/<isbn>/return")
async def return_book(isbn: str):
    """
    POST /library/books/<isbn>/return
    Devuelve un libro que estaba prestado al usuario autenticado (X-User-Id).
    
    OPERACIÓN ATÓMICA REQUERIDA:
    Actualiza el subdocumento en 'loan_history' donde:
      user_id == user_id AND return_date == None
    poniendo 'return_date' a datetime.utcnow(), e incrementa 'available_stock' en +1.
    """
    user_id = request.headers.get("X-User-Id")
    db = get_db()

    # TODO: 1. Ejecutar find_one_and_update con filtro atómico:
    #          Filtro: {'isbn': isbn, 'loan_history': {'$elemMatch': {'user_id': user_id, 'return_date': None}}}
    #          Update: {'$inc': {'available_stock': 1}, '$set': {'loan_history.$.return_date': datetime.utcnow()}}
    # TODO: 2. Si no coincide ninguna entrada (no tenía préstamo activo de ese libro), devolver error (400 o 404)
    # TODO: 3. Retornar confirmación de devolución (200)
    return jsonify({"message": f"Libro {isbn} devuelto por {user_id}"}), 200
