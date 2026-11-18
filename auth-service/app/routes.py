import hashlib
import uuid
from quart import Blueprint, request, jsonify, make_response
from app.redis_client import get_redis

auth_bp = Blueprint("auth", __name__)

# ==============================================================================
# UTILIDADES AUXILIARES (Estructura base)
# ==============================================================================
def hash_password(password: str) -> str:
    """Calcula el hash de la contraseña (e.g. SHA-256)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def extract_bearer_token() -> str | None:
    """Extrae el token Bearer del encabezado Authorization."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header[len("Bearer "):].strip()


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@auth_bp.post("/register")
async def register():
    """
    POST /auth/register
    Registra usuarios (username, password y email).
    Modelo en Redis:
      Clave: user:{username} (HASH)
      Campos: password_hash, email
      Sin TTL (persistente por directiva AOF).
    """
    data = await request.get_json()
    if not data:
        return jsonify({"error": "Payload JSON requerido"}), 400

    username = data.get("username")
    password = data.get("password")
    email = data.get("email")

    if not username or not password or not email:
        return jsonify({"error": "Faltan campos obligatorios"}), 400

    redis = await get_redis()

    # TODO: 1. Comprobar si el usuario ya existe en Redis (user:{username})
    # TODO: 2. Hashear la contraseña (usando hash_password)
    # TODO: 3. Guardar en Redis como HASH bajo 'user:{username}' los campos password_hash y email (sin TTL)

    return jsonify({"message": "Usuario registrado exitosamente"}), 201


@auth_bp.post("/login")
async def login():
    """
    POST /auth/login
    Inicia la sesión de un usuario registrado (username, password).
    Devuelve su token correspondiente.
    Modelo en Redis:
      Clave: session:{token} (STRING o HASH vinculando al usuario)
      TTL: 5 minutos (300 segundos).
    """
    data = await request.get_json()
    if not data:
        return jsonify({"error": "Payload JSON requerido"}), 400

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Credenciales incompletas"}), 400

    redis = await get_redis()

    # TODO: 1. Verificar si existe user:{username} en Redis y comprobar su password_hash
    # TODO: 2. Generar un nuevo token de sesión único (e.g. uuid.uuid4().hex)
    # TODO: 3. Guardar en Redis 'session:{token}' apuntando al username/user_id con TTL de 5 minutos (300s)

    session_token = str(uuid.uuid4())
    return jsonify({"token": session_token}), 200


@auth_bp.get("/validate")
async def validate():
    """
    GET /auth/validate
    Llamado internamente por nginx auth_request.
    Busca 'session:{token}' en Redis.
    Respuesta:
      - 200 + encabezado X-User-Id si el token es válido.
      - 401 si falta la cabecera, es desconocido o ha caducado.
    """
    token = extract_bearer_token()
    if not token:
        return jsonify({"error": "Falta o es inválido el encabezado de autorización"}), 401

    redis = await get_redis()

    # TODO: 1. Buscar la clave 'session:{token}' en Redis
    # TODO: 2. Si no existe (o expiró por TTL), retornar ("", 401)
    # TODO: 3. Si existe, obtener el username/user_id asociado y retornar:
    #          response = await make_response("", 200)
    #          response.headers["X-User-Id"] = username
    #          return response

    return ("", 401)


@auth_bp.post("/logout")
async def logout():
    """
    POST /auth/logout
    Cierra la sesión del usuario e invalida el token actual.
    Elimina 'session:{token}' en Redis de inmediato.
    Respuesta:
      - 200 si la operación es exitosa.
      - 401 si falta cabecera, token desconocido/caducado o ya cerrado.
    """
    token = extract_bearer_token()
    if not token:
        return jsonify({"error": "Falta o es inválido el encabezado de autorización"}), 401

    redis = await get_redis()

    # TODO: 1. Verificar si 'session:{token}' existe en Redis
    # TODO: 2. Si no existe, retornar ("", 401)
    # TODO: 3. Si existe, eliminar la clave de Redis inmediatamente (retornar 200)

    return jsonify({"message": "Sesión cerrada exitosamente"}), 200
