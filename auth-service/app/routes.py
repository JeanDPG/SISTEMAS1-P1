import hashlib
import uuid
from quart import Blueprint, request, jsonify, make_response
from app.redis_client import get_redis

auth_bp = Blueprint("auth", __name__)

# ==============================================================================
# UTILIDADES AUXILIARES
# ==============================================================================
def hash_password(password: str) -> str:
    """Calcula el hash SHA-256 de la contraseña."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def extract_bearer_token() -> str | None:
    """Extrae el token Bearer del encabezado Authorization."""
    auth_header = request.headers.get("Authorization", "")
    parts = auth_header.strip().split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None


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
      Sin TTL (persistente en disco mediante directiva AOF).
    """
    data = await request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Payload JSON requerido o malformado"}), 400

    username = data.get("username")
    password = data.get("password")
    email = data.get("email")

    if (
        not username or not isinstance(username, str) or not username.strip() or
        not password or not isinstance(password, str) or not password.strip() or
        not email or not isinstance(email, str) or not email.strip()
    ):
        return jsonify({"error": "Faltan campos obligatorios o vacíos: username, password, email"}), 400

    username = username.strip()
    email = email.strip()

    redis = await get_redis()

    # 1. Comprobar si el usuario ya existe en Redis
    user_key = f"user:{username}"
    if await redis.exists(user_key):
        return jsonify({"error": f"El usuario '{username}' ya existe"}), 409

    # 2. Hashear la contraseña y almacenar el perfil permanente en Redis (HASH sin TTL)
    pwd_hash = hash_password(password)
    await redis.hset(user_key, mapping={
        "username": username,
        "password_hash": pwd_hash,
        "email": email
    })

    return jsonify({
        "message": "Usuario registrado exitosamente",
        "username": username
    }), 201


@auth_bp.post("/login")
async def login():
    """
    POST /auth/login
    Inicia la sesión de un usuario registrado (username, password).
    Devuelve su token correspondiente.
    Modelo en Redis:
      Clave: session:{token}
      Valor: username
      TTL: 5 minutos (300 segundos).
    """
    data = await request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Payload JSON requerido o malformado"}), 400

    username = data.get("username")
    password = data.get("password")

    if (
        not username or not isinstance(username, str) or not username.strip() or
        not password or not isinstance(password, str) or not password.strip()
    ):
        return jsonify({"error": "Credenciales incompletas: se requieren username y password"}), 400

    username = username.strip()
    redis = await get_redis()

    # 1. Verificar si existe user:{username} y validar contraseña
    user_key = f"user:{username}"
    stored_hash = await redis.hget(user_key, "password_hash")
    if not stored_hash or stored_hash != hash_password(password):
        return jsonify({"error": "Credenciales inválidas"}), 401

    # 2. Generar un nuevo token de sesión único (UUID)
    session_token = str(uuid.uuid4())

    # 3. Guardar en Redis con TTL de 5 minutos (300 segundos)
    session_key = f"session:{session_token}"
    await redis.set(session_key, username, ex=300)

    return jsonify({
        "message": "Login exitoso",
        "token": session_token,
        "username": username
    }), 200


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

    # 1. Buscar la sesión en Redis
    session_key = f"session:{token}"
    username = await redis.get(session_key)

    if not username:
        return jsonify({"error": "Token desconocido, caducado o no autorizado"}), 401

    # 2. Devolver 200 OK con la cabecera X-User-Id requerida por Nginx
    response = await make_response(jsonify({"valid": True, "username": username}), 200)
    response.headers["X-User-Id"] = username
    return response


@auth_bp.post("/logout")
async def logout():
    """
    POST /auth/logout
    Cierra la sesión del usuario e invalida el token actual.
    Elimina 'session:{token}' en Redis de inmediato de forma atómica.
    Respuesta:
      - 200 si la operación es exitosa.
      - 401 si falta cabecera, token desconocido/caducado o ya cerrado.
    """
    token = extract_bearer_token()
    if not token:
        return jsonify({"error": "Falta o es inválido el encabezado de autorización"}), 401

    redis = await get_redis()

    session_key = f"session:{token}"
    # Eliminación atómica: delete() retorna 1 si la clave existía y fue borrada, 0 si no existía
    deleted = await redis.delete(session_key)
    if not deleted:
        return jsonify({"error": "Sesión desconocida, expirada o previamente cerrada"}), 401

    return jsonify({"message": "Sesión cerrada e invalidada exitosamente"}), 200
