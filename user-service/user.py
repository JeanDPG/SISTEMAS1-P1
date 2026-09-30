import os
import hashlib
import uuid
from quart import Quart, request

app = QuartName = Quart(__name__)
users = {}

# Se carga el secreto compartido configurado en Docker (o se genera uno si se ejecuta localmente)
env_secret = os.getenv("SHARED_SECRET")
secret_uuid = uuid.UUID(env_secret) if env_secret else uuid.uuid4() 

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def make_token(uid_str: str) -> str:
    # Derivación exacta descrita en el enunciado usando uuid5
    return str(uuid.uuid5(secret_uuid, uid_str))

@app.put("/user")
async def create_user():
    data = await request.get_json()
    
    if not data or not data.get("name") or not data.get("password"):
        return {"error": "Faltan name o password"}, 400
        
    if data["name"] in users:
        return {"error": "El usuario ya existe"}, 409
        
    # Asignar un identificador único aleatorio (UID)[cite: 1]
    uid_str = str(uuid.uuid4())
    
    users[data["name"]] = {
        "uid": uid_str,
        "name": data["name"],
        "password_hash": hash_password(data["password"])
    }
    
    # Devolver el UID junto con el token de acceso[cite: 1]
    return {"uid": uid_str, "token": make_token(uid_str)}, 201


@app.post("/user")
async def login():
    data = await request.get_json()
    if not data or not data.get("name") or not data.get("password"):
        return {"error": "Faltan name o password"}, 400

    user = users.get(data["name"])
    if user is None or user["password_hash"] != hash_password(data["password"]):
        return {"error": "Credenciales incorrectas"}, 401

    # En caso de éxito, devuelve el token de acceso y el UID[cite: 1]
    return {"uid": user["uid"], "token": make_token(user["uid"])}, 200


@app.patch("/user")
async def modify_user():
    # El token se pasa en el campo Authorization indicando que es de tipo Bearer[cite: 1]
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return {"error": "Falta el token"}, 401
    
    token_recibido = auth[len("Bearer "):]
    data = await request.get_json()
    
    if not data or not data.get("password"):
        return {"error": "Falta password"}, 400

    for user in users.values():
        # El servidor verifica fácilmente si el token es válido volviéndolo a generar[cite: 1]
        if make_token(user["uid"]) == token_recibido:
            user["password_hash"] = hash_password(data["password"])
            return {"message": "Contraseña modificada"}, 200

    return {"error": "Token inválido o no autorizado"}, 401


if __name__ == "__main__":
    # El ejemplo de cURL del enunciado utiliza el puerto 5050 para las pruebas[cite: 1]
    app.run(host="0.0.0.0", port=5050)


