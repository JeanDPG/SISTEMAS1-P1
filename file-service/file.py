import os
import json
import uuid
from quart import Quart, request

app = Quart(__name__)

env_secret = os.getenv("SHARED_SECRET")
SHARED_SECRET = uuid.UUID(env_secret) if env_secret else uuid.UUID("12345678-1234-5678-1234-567812345678")
BASE_DIR = "storage"

os.makedirs(BASE_DIR, exist_ok=True)

def verify_token(uid_str: str, token: str) -> bool:
    """Verifica si el token corresponde al UID derivándolo con el secreto compartido[cite: 4]."""
    try:
        expected_token = str(uuid.uuid5(SHARED_SECRET, uid_str))
        return token == expected_token
    except Exception:
        return False

def get_auth_token():
    """Extrae el token de la cabecera indicando que es de tipo Bearer[cite: 1]."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):]
    return None

def get_metadata(uid: str) -> dict:
    """Lee el fichero metadata.json del directorio del usuario para saber si un archivo es público o privado."""
    meta_path = os.path.join(BASE_DIR, uid, "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            return json.load(f)
    return {}

def save_metadata(uid: str, metadata: dict):
    """Guarda la visibilidad de los archivos."""
    meta_path = os.path.join(BASE_DIR, uid, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f)


@app.get("/file/<uid>")
async def list_files(uid):
    # El propietario siempre podrá listar sus documentos, otros usuarios no pueden[cite: 1].
    token = get_auth_token()
    if not token or not verify_token(uid, token):
        return {"error": "No autorizado"}, 401
    
    user_dir = os.path.join(BASE_DIR, uid)
    if not os.path.exists(user_dir):
        return {"archivos": []}, 200
        
    metadata = get_metadata(uid)
    archivos = []
    for f in os.listdir(user_dir):
        if f != "metadata.json":
            archivos.append({"nombre": f, "public": metadata.get(f, {}).get("public", False)})
            
    return {"archivos": archivos}, 200


@app.put("/file/<uid>/<filename>")
async def upload_file(uid, filename):
    # El propietario siempre podrá crear o actualizar sus documentos[cite: 1].
    token = get_auth_token()
    if not token or not verify_token(uid, token):
        return {"error": "No autorizado"}, 401
        
    user_dir = os.path.join(BASE_DIR, uid)
    os.makedirs(user_dir, exist_ok=True)
    
    data = await request.get_data(as_text=True)
    file_path = os.path.join(user_dir, filename)
    
    with open(file_path, "w") as f:
        f.write(data)
        
    metadata = get_metadata(uid)
    # Si no existía, lo registramos por defecto como privado (public: False)
    if filename not in metadata:
        metadata[filename] = {"public": False}
        save_metadata(uid, metadata)
        
    return {"message": f"Archivo {filename} guardado correctamente"}, 200


@app.get("/file/<uid>/<filename>")
async def download_file(uid, filename):
    user_dir = os.path.join(BASE_DIR, uid)
    file_path = os.path.join(user_dir, filename)
    
    if not os.path.exists(file_path):
        return {"error": "Archivo no encontrado"}, 404
        
    metadata = get_metadata(uid)
    is_public = metadata.get(filename, {}).get("public", False)
    
    # Los documentos públicos podrán recuperarse sin autenticación[cite: 1].
    if not is_public:
        # Los documentos privados no podrán ser descargados por terceros, requiere validar token del propietario[cite: 1].
        token = get_auth_token()
        if not token or not verify_token(uid, token):
            return {"error": "No autorizado para ver este archivo privado"}, 401
            
    with open(file_path, "r") as f:
        content = f.read()
        
    return {"content": content}, 200


@app.delete("/file/<uid>/<filename>")
async def delete_file(uid, filename):
    # Solo el propietario puede borrar[cite: 1].
    token = get_auth_token()
    if not token or not verify_token(uid, token):
        return {"error": "No autorizado"}, 401
        
    user_dir = os.path.join(BASE_DIR, uid)
    file_path = os.path.join(user_dir, filename)
    
    if not os.path.exists(file_path):
        return {"error": "Archivo no encontrado"}, 404
        
    os.remove(file_path)
    
    # Actualizar metadata
    metadata = get_metadata(uid)
    if filename in metadata:
        del metadata[filename]
        save_metadata(uid, metadata)
        
    return {"message": "Archivo eliminado"}, 200


@app.patch("/file/<uid>/<filename>")
async def change_visibility(uid, filename):
    # Solo el propietario puede cambiar la visibilidad[cite: 1].
    token = get_auth_token()
    if not token or not verify_token(uid, token):
        return {"error": "No autorizado"}, 401
        
    data = await request.get_json()
    if data is None or "public" not in data:
        return {"error": "Debe especificar el campo 'public' como booleano"}, 400
        
    user_dir = os.path.join(BASE_DIR, uid)
    file_path = os.path.join(user_dir, filename)
    
    if not os.path.exists(file_path):
        return {"error": "Archivo no encontrado"}, 404
        
    metadata = get_metadata(uid)
    metadata[filename] = {"public": bool(data["public"])}
    save_metadata(uid, metadata)
    
    return {"message": f"Visibilidad de {filename} actualizada"}, 200


if __name__ == "__main__":
    # Arrancamos en un puerto diferente al de users (por ejemplo, el 5051)
    app.run(host="0.0.0.0", port=5051)