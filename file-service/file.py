import os
import json
import uuid
from quart import Quart, request
from werkzeug.utils import secure_filename

app = Quart(__name__)

# Ruta base: file-service/data/files/
BASE_DIR = os.path.join(os.path.dirname(__file__), "data", "files")
os.makedirs(BASE_DIR, exist_ok=True)

SHARED_SECRET_STR = os.getenv("SHARED_SECRET", "12345678-1234-5678-1234-567812345678")
SHARED_SECRET = uuid.UUID(SHARED_SECRET_STR)

def verify_token(uid_str: str, token: str) -> bool:
    """Verifica si el token corresponde al UID dado[cite: 1, 4]."""
    try:
        expected_token = str(uuid.uuid5(SHARED_SECRET, uid_str))
        return token == expected_token
    except Exception:
        return False

def get_auth_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):]
    return None

def get_user_dir(uid: str) -> str:
    """Sanea el UID para prevenir Path Traversal."""
    safe_uid = secure_filename(uid)
    return os.path.join(BASE_DIR, safe_uid)

def get_metadata(user_dir: str) -> dict:
    """Usa .metadata.json para evitar colisiones con ficheros del usuario."""
    meta_path = os.path.join(user_dir, ".metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}

def save_metadata(user_dir: str, metadata: dict):
    meta_path = os.path.join(user_dir, ".metadata.json")
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)
    except OSError:
        pass

@app.get("/file/<uid>")
async def list_files(uid):
    token = get_auth_token()
    if not token:
        return {"error": "No autenticado"}, 401
    if not verify_token(uid, token):
        return {"error": "Acceso prohibido"}, 403

    user_dir = get_user_dir(uid)
    if not os.path.exists(user_dir):
        return {"archivos": []}, 200

    metadata = get_metadata(user_dir)
    archivos = []
    for f in os.listdir(user_dir):
        if f != ".metadata.json":
            archivos.append({"nombre": f, "public": metadata.get(f, {}).get("public", False)})

    return {"archivos": archivos}, 200

@app.put("/file/<uid>/<filename>")
async def upload_file(uid, filename):
    token = get_auth_token()
    if not token:
        return {"error": "No autenticado"}, 401
    if not verify_token(uid, token):
        return {"error": "Acceso prohibido"}, 403

    safe_file = secure_filename(filename)
    if not safe_file or safe_file == ".metadata.json":
        return {"error": "Nombre de archivo no válido"}, 400

    user_dir = get_user_dir(uid)
    os.makedirs(user_dir, exist_ok=True) # Se crea la carpeta data/files/<UID>

    data = await request.get_data(as_text=True)
    file_path = os.path.join(user_dir, safe_file)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(data)
    except OSError:
        return {"error": "Error al guardar el archivo en disco"}, 500

    metadata = get_metadata(user_dir)
    if safe_file not in metadata:
        metadata[safe_file] = {"public": False}
        save_metadata(user_dir, metadata)

    return {"message": f"Archivo {safe_file} guardado correctamente"}, 200

@app.get("/file/<uid>/<filename>")
async def download_file(uid, filename):
    safe_file = secure_filename(filename)
    user_dir = get_user_dir(uid)
    file_path = os.path.join(user_dir, safe_file)

    if not os.path.exists(file_path):
        return {"error": "Archivo no encontrado"}, 404

    metadata = get_metadata(user_dir)
    is_public = metadata.get(safe_file, {}).get("public", False)

    if not is_public:
        token = get_auth_token()
        if not token:
            return {"error": "No autenticado"}, 401
        if not verify_token(uid, token):
            return {"error": "Acceso prohibido"}, 403

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return {"error": "Error al leer el archivo"}, 500

    return {"content": content}, 200

@app.delete("/file/<uid>/<filename>")
async def delete_file(uid, filename):
    token = get_auth_token()
    if not token:
        return {"error": "No autenticado"}, 401
    if not verify_token(uid, token):
        return {"error": "Acceso prohibido"}, 403

    safe_file = secure_filename(filename)
    user_dir = get_user_dir(uid)
    file_path = os.path.join(user_dir, safe_file)

    if not os.path.exists(file_path):
        return {"error": "Archivo no encontrado"}, 404

    try:
        os.remove(file_path)
    except OSError:
        return {"error": "Error al eliminar el archivo"}, 500

    metadata = get_metadata(user_dir)
    if safe_file in metadata:
        del metadata[safe_file]
        save_metadata(user_dir, metadata)

    return {"message": "Archivo eliminado"}, 200

@app.patch("/file/<uid>/<filename>")
async def change_visibility(uid, filename):
    token = get_auth_token()
    if not token:
        return {"error": "No autenticado"}, 401
    if not verify_token(uid, token):
        return {"error": "Acceso prohibido"}, 403

    try:
        data = await request.get_json()
    except Exception:
        return {"error": "JSON mal formado"}, 400

    if data is None or "public" not in data:
        return {"error": "Debe especificar el campo 'public' como booleano"}, 400

    safe_file = secure_filename(filename)
    user_dir = get_user_dir(uid)
    file_path = os.path.join(user_dir, safe_file)

    if not os.path.exists(file_path):
        return {"error": "Archivo no encontrado"}, 404

    metadata = get_metadata(user_dir)
    metadata[safe_file] = {"public": bool(data["public"])}
    save_metadata(user_dir, metadata)

    return {"message": f"Visibilidad de {safe_file} actualizada"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5051)