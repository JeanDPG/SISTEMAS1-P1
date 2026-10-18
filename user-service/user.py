import os
import hashlib
import uuid
from quart import Quart, request
from sqlalchemy import text
from database import async_session

app = Quart(__name__)


# Secreto compartido (mismo valor por defecto si no existe .env)[cite: 1, 3]
SHARED_SECRET_STR = os.getenv("SHARED_SECRET", "12345678-1234-5678-1234-567812345678")
SHARED_SECRET = uuid.UUID(SHARED_SECRET_STR)



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

    name = data.get("name")
    password = data.get("password")
    pais = data.get("pais")
    saldo = data.get("saldo", 0.00)


    if not name or not password or not pais:
        return {"error": "Faltan datos obligatorios: name, password o pais"}, 400

    # Consulta parametrizada con SQLAlchemy Core
    query_check = text("SELECT id_usuario FROM usuarios WHERE nombre = :nombre")
    query_insert = text("""
        INSERT INTO usuarios (nombre, contrasena_hash, pais, saldo)
        VALUES (:nombre, :password_hash, :pais, :saldo)
        RETURNING id_usuario;
    """)

    #uid_str = str(uuid.uuid4())
    async with async_session() as session:
        async with session.begin():
            # Comprobar si ya existe
            res = await session.execute(query_check, {"nombre": name})
            if res.fetchone():
                return {"error": "El usuario ya existe"}, 409

            # Insertar nuevo usuario
            pwd_hash = hash_password(password)
            res_insert = await session.execute(query_insert, {
                "nombre": name,
                "password_hash": pwd_hash,
                "pais": pais,
                "saldo": saldo
            })
            new_id = res_insert.scalar_one()

    uid_str = str(new_id)
    return {"uid": uid_str, "token": make_token(uid_str)}, 201



@app.post("/user/login")
async def login():
    try:
        data = await request.get_json()
    except Exception:
        return {"error": "JSON mal formado"}, 400

    name = data.get("name")
    password = data.get("password")

    if not name or not password:
        return {"error": "Faltan name o password"}, 400

    query = text("SELECT id_usuario, contrasena_hash FROM usuarios WHERE nombre = :nombre")

    async with async_session() as session:
        res = await session.execute(query, {"nombre": name})
        user = res.fetchone()

        if user is None or user.contrasena_hash != hash_password(password):
            return {"error": "Credenciales incorrectas"}, 401

        uid_str = str(user.id_usuario)
        return {"uid": uid_str, "token": make_token(uid_str)}, 200


@app.post("/user/logout")
async def logout():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return {"error": "Falta el token de autorización"}, 401

    # Al no guardar estado en servidor (stateless), la respuesta confirma la invalidez lógica del cliente[cite: 6]
    return {"mensaje": "Sesión cerrada con éxito"}, 200


@app.patch("/user/saldo")
async def recargar_saldo():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return {"error": "Falta el token de autorización"}, 401

    try:
        data = await request.get_json()
    except Exception:
        return {"error": "JSON mal formado"}, 400

    monto = data.get("monto")
    id_usuario = data.get("id_usuario")

    if not id_usuario or monto is None or monto <= 0:
        return {"error": "Monto o id_usuario inválidos"}, 400

    query = text("""
        UPDATE usuarios 
        SET saldo = saldo + :monto 
        WHERE id_usuario = :id_usuario 
        RETURNING id_usuario, nombre, saldo;
    """)

    async with async_session() as session:
        async with session.begin():
            res = await session.execute(query, {"monto": monto, "id_usuario": id_usuario})
            user_updated = res.fetchone()

            if not user_updated:
                return {"error": "Usuario no encontrado"}, 404

            return {
                "mensaje": "Saldo actualizado correctamente",
                "id_usuario": user_updated.id_usuario,
                "nuevo_saldo": float(user_updated.saldo)
            }, 200


@app.delete("/user")
async def delete_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return {"error": "Falta el token de autorización"}, 401

    token_recibido = auth[len("Bearer "):]

    try:
        data = await request.get_json()
    except Exception:
        return {"error": "JSON mal formado"}, 400

    id_usuario = data.get("id_usuario")
    if not id_usuario:
        return {"error": "Falta id_usuario"}, 400

    # Verificar que el token pertenece a ese ID
    if make_token(str(id_usuario)) != token_recibido:
        return {"error": "Token no valido o no autorizado"}, 403

    query = text("DELETE FROM usuarios WHERE id_usuario = :id_usuario RETURNING id_usuario;")

    async with async_session() as session:
        async with session.begin():
            res = await session.execute(query, {"id_usuario": id_usuario})
            deleted = res.fetchone()

            if not deleted:
                return {"error": "Usuario no encontrado"}, 404

            return {"mensaje": f"Usuario {id_usuario} eliminado correctamente"}, 200
        

'''
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
'''

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)