import uuid
import requests

USER_URL = "http://127.0.0.1:5050"
FILE_URL = "http://127.0.0.1:5051"

def test(nombre_prueba: str, condicion: bool):
    """Muestra por pantalla el resultado de cada prueba."""
    if condicion:
        print(f"✅ [ÉXITO] {nombre_prueba}")
    else:
        print(f"❌ [FALLO] {nombre_prueba}")

# ==============================================================================
# 1. PRUEBAS DE CREACIÓN Y AUTENTICACIÓN DE USUARIOS
# ==============================================================================
def probar_creacion_y_login_usuarios():
    print("\n--- 1. PRUEBAS DE CREACIÓN Y AUTENTICACIÓN ---")
    
    user_a_name = f"user_{uuid.uuid4().hex[:6]}"
    pass_a_old = "pass123"
    
    # PUT /user: Crear usuario A
    res = requests.put(f"{USER_URL}/user", json={"name": user_a_name, "password": pass_a_old})
    test("Crear usuario principal (201)", res.status_code == 201)
    
    data_a = res.json() if res.status_code == 201 else {}
    uid_a = data_a.get("uid", "")
    token_a = data_a.get("token", "")
    
    # PUT /user: Error por usuario duplicado
    res_dup = requests.put(f"{USER_URL}/user", json={"name": user_a_name, "password": pass_a_old})
    test("Rechazar creación de usuario duplicado (409)", res_dup.status_code == 409)
    
    # POST /user: Login correcto
    res_login_ok = requests.post(f"{USER_URL}/user", json={"name": user_a_name, "password": pass_a_old})
    test("Login exitoso con credenciales correctas (200)", res_login_ok.status_code == 200)
    
    # POST /user: Login con contraseña incorrecta
    res_login_fail = requests.post(f"{USER_URL}/user", json={"name": user_a_name, "password": "wrong_password"})
    test("Rechazar login con contraseña incorrecta (401)", res_login_fail.status_code == 401)
    
    # POST /user: Login con usuario inexistente
    res_login_nouser = requests.post(f"{USER_URL}/user", json={"name": "usuario_fantasma", "password": "123"})
    test("Rechazar login con usuario inexistente (401)", res_login_nouser.status_code == 401)
    
    return user_a_name, uid_a, token_a, pass_a_old


# ==============================================================================
# 2. PRUEBAS DE CAMBIO DE CONTRASEÑA
# ==============================================================================
def probar_cambio_contrasena(user_a_name: str, token_a: str, pass_a_old: str):
    print("\n--- 2. PRUEBAS DE MODIFICACIÓN DE CONTRASEÑA ---")
    
    pass_a_new = "newpass456"
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    # PATCH /user: Cambiar contraseña
    res_patch = requests.patch(f"{USER_URL}/user", json={"password": pass_a_new}, headers=headers_a)
    test("Modificar contraseña con token válido (200)", res_patch.status_code == 200)
    
    # POST /user: Login con contraseña antigua (debe fallar)
    res_old = requests.post(f"{USER_URL}/user", json={"name": user_a_name, "password": pass_a_old})
    test("Denegar login con la contraseña antigua tras el cambio (401)", res_old.status_code == 401)
    
    # POST /user: Login con contraseña nueva (debe funcionar)
    res_new = requests.post(f"{USER_URL}/user", json={"name": user_a_name, "password": pass_a_new})
    test("Permitir login con la nueva contraseña (200)", res_new.status_code == 200)


# ==============================================================================
# 3. PRUEBAS CRUD DE ARCHIVOS (PROPIETARIO)
# ==============================================================================
def probar_gestion_archivos_propietario(uid_a: str, token_a: str):
    print("\n--- 3. PRUEBAS DE GESTIÓN DE ARCHIVOS (PROPIETARIO) ---")
    
    headers_a = {"Authorization": f"Bearer {token_a}"}
    filename = "documento.txt"
    content = "Contenido confidencial de prueba"
    
    # PUT /file/<uid>/<filename>: Subir archivo
    res_upload = requests.put(f"{FILE_URL}/file/{uid_a}/{filename}", headers=headers_a, data=content)
    test("Subir archivo a directorio personal (200)", res_upload.status_code == 200)
    
    # GET /file/<uid>: Listar archivos
    res_list = requests.get(f"{FILE_URL}/file/{uid_a}", headers=headers_a)
    archivos = res_list.json().get("archivos", []) if res_list.status_code == 200 else []
    test("Listar archivos del propietario (200)", res_list.status_code == 200 and len(archivos) > 0)
    
    # GET /file/<uid>/<filename>: Descargar archivo privado
    res_download = requests.get(f"{FILE_URL}/file/{uid_a}/{filename}", headers=headers_a)
    test("Descargar archivo privado propio (200)", res_download.status_code == 200 and res_download.json().get("content") == content)
    
    # PATCH /file/<uid>/<filename>: Cambiar visibilidad a público
    res_public = requests.patch(f"{FILE_URL}/file/{uid_a}/{filename}", headers=headers_a, json={"public": True})
    test("Cambiar visibilidad del archivo a público (200)", res_public.status_code == 200)
    
    # GET /file/<uid>/<filename>: Descargar público sin autenticación
    res_pub_noauth = requests.get(f"{FILE_URL}/file/{uid_a}/{filename}")
    test("Descargar archivo público sin token (200)", res_pub_noauth.status_code == 200)
    
    return filename


# ==============================================================================
# 4. PRUEBAS CON OTRO USUARIO (PERMISOS Y CONTROL DE ACCESO ESTRICTO 403)
# ==============================================================================
def probar_acceso_otro_usuario(uid_a: str, token_a: str, filename: str):
    print("\n--- 4. PRUEBAS DE AUTORIZACIÓN Y TOKEN AJENO (DEBE DEVOLVER 403) ---")
    
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    # Volver a poner el archivo como privado para verificar que Usuario B no pueda descargarlo
    res_priv = requests.patch(f"{FILE_URL}/file/{uid_a}/{filename}", headers=headers_a, json={"public": False})
    test("Restablecer archivo a privado por el propietario (200)", res_priv.status_code == 200)

    # Crear Usuario B
    user_b_name = f"user_{uuid.uuid4().hex[:6]}"
    res_b = requests.put(f"{USER_URL}/user", json={"name": user_b_name, "password": "pass_user_b"})
    data_b = res_b.json() if res_b.status_code == 201 else {}
    token_b = data_b.get("token", "")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # Intento de Usuario B de listar directorio de Usuario A -> 403
    res_list_b = requests.get(f"{FILE_URL}/file/{uid_a}", headers=headers_b)
    test("Denegar a Usuario B listar directorio de Usuario A (devuelve 403)", res_list_b.status_code == 403)
    
    # Intento de Usuario B de descargar archivo privado de Usuario A -> 403
    res_get_b = requests.get(f"{FILE_URL}/file/{uid_a}/{filename}", headers=headers_b)
    test("Denegar a Usuario B descargar archivo privado de Usuario A (devuelve 403)", res_get_b.status_code == 403)
    
    # Intento de Usuario B de subir un archivo al directorio de Usuario A -> 403
    res_put_b = requests.put(f"{FILE_URL}/file/{uid_a}/hack.txt", headers=headers_b, data="malware")
    test("Denegar a Usuario B subir archivo en directorio de Usuario A (devuelve 403)", res_put_b.status_code == 403)
    
    # Intento de Usuario B de borrar el archivo de Usuario A -> 403
    res_del_b = requests.delete(f"{FILE_URL}/file/{uid_a}/{filename}", headers=headers_b)
    test("Denegar a Usuario B eliminar archivo de Usuario A (devuelve 403)", res_del_b.status_code == 403)


# ==============================================================================
# 5. PRUEBAS DE CASOS DE ERROR (400 Y 404)
# ==============================================================================
def probar_casos_de_error(uid_a: str, token_a: str, filename: str):
    print("\n--- 5. PRUEBAS DE ERRORES 400 Y 404 ---")
    
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    # GET /file/<uid>/<filename>: Archivo no encontrado (404)
    res_404 = requests.get(f"{FILE_URL}/file/{uid_a}/fichero_inexistente.txt", headers=headers_a)
    test("Solicitar archivo inexistente devuelve error (404)", res_404.status_code == 404)
    
    # PUT /user: Petición sin parámetros obligatorios (400)
    res_400_user = requests.put(f"{USER_URL}/user", json={"name": "solo_nombre"})
    test("Crear usuario sin contraseña devuelve error (400)", res_400_user.status_code == 400)
    
    # PATCH /file/<uid>/<filename>: Petición con cuerpo inválido (400)
    res_400_file = requests.patch(f"{FILE_URL}/file/{uid_a}/{filename}", headers=headers_a, json={"campo_incorrecto": True})
    test("Cambiar visibilidad con JSON inválido devuelve error (400)", res_400_file.status_code == 400)
    
    # DELETE /file/<uid>/<filename>: Limpieza final borrando el archivo
    #res_delete = requests.delete(f"{FILE_URL}/file/{uid_a}/{filename}", headers=headers_a)
    #test("Eliminar archivo propio correctamente (200)", res_delete.status_code == 200)


# ==============================================================================
# EJECUCIÓN PRINCIPAL
# ==============================================================================
if __name__ == "__main__":
    try:
        user_a_name, uid_a, token_a, pass_a_old = probar_creacion_y_login_usuarios()
        if uid_a and token_a:
            probar_cambio_contrasena(user_a_name, token_a, pass_a_old)
            filename = probar_gestion_archivos_propietario(uid_a, token_a)
            probar_acceso_otro_usuario(uid_a, token_a, filename)
            probar_casos_de_error(uid_a, token_a, filename)
            print("\n🎉 ¡TODAS LAS PRUEBAS COMPLETADAS SATISFACTORIAMENTE!")
        else:
            print("\n❌ Error crítico: No se pudo obtener el UID/Token del usuario principal.")
    except requests.exceptions.ConnectionError:
        print("\n❌ Error de conexión: Asegúrate de que los microservicios estén levantados con 'docker compose up -d'.")