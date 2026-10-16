import os
import json
import hashlib
import uuid
from quart import Quart, request

app = Quart(__name__)

# Ruta al fichero: user-service/data/users.json
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
os.makedirs(DATA_DIR, exist_ok=True)

# Secreto compartido (mismo valor por defecto si no existe .env)[cite: 1, 3]
SHARED_SECRET_STR = os.getenv("SHARED_SECRET", "12345678-1234-5678-1234-567812345678")
SHARED_SECRET = uuid.UUID(SHARED_SECRET_STR)

def load_users() -> dict:
    """Carga los usuarios desde el archivo JSON gestionando errores de E/S."""
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

def save_users(users: dict) -> bool:
    """Guarda el diccionario de usuarios en el archivo JSON."""
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4)
        return True
    except OSError:
        return False

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def make_token(uid_str: str) -> str:
    return str(uuid.uuid5(SHARED_SECRET, uid_str))

@app.put("/user")
async def create_user():
    try:
        data = await request.get_json()
    except Exception:
        return {"error": "JSON mal formado"}, 400

    if not data or not data.get("name") or not data.get("password"):
        return {"error": "Faltan name o password"}, 400

    users = load_users()
    if data["name"] in users:
        return {"error": "El usuario ya existe"}, 409

    uid_str = str(uuid.uuid4())
    users[data["name"]] = {
        "uid": uid_str,
        "name": data["name"],
        "password_hash": hash_password(data["password"])
    }

    if not save_users(users):
        return {"error": "Error al guardar los datos en disco"}, 500

    return {"uid": uid_str, "token": make_token(uid_str)}, 201

@app.post("/user")
async def login():
    try:
        data = await request.get_json()
    except Exception:
        return {"error": "JSON mal formado"}, 400

    if not data or not data.get("name") or not data.get("password"):
        return {"error": "Faltan name o password"}, 400

    users = load_users()
    user = users.get(data["name"])

    if user is None or user["password_hash"] != hash_password(data["password"]):
        return {"error": "Credenciales incorrectas"}, 401

    return {"uid": user["uid"], "token": make_token(user["uid"])}, 200

@app.patch("/user")
async def modify_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return {"error": "Falta el token de autorización"}, 401

    token_recibido = auth[len("Bearer "):]

    try:
        data = await request.get_json()
    except Exception:
        return {"error": "JSON mal formado"}, 400

    if not data or not data.get("password"):
        return {"error": "Falta el campo password"}, 400

    users = load_users()
    for user in users.values():
        if make_token(user["uid"]) == token_recibido:
            user["password_hash"] = hash_password(data["password"])
            if not save_users(users):
                return {"error": "Error al guardar los datos"}, 500
            return {"message": "Contraseña modificada correctamente"}, 200

    return {"error": "Token inválido o no autorizado"}, 401

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)