import requests

USER_URL = "http://127.0.0.1:5050"
FILE_URL = "http://127.0.0.1:5051"

def test(nombre_prueba: str, condicion: bool):
    """Muestra por pantalla el nombre de la prueba y si el resultado es el esperado[cite: 1]."""
    if condicion:
        print(f"✅ [ÉXITO] {nombre_prueba}")
    else:
        print(f"❌ [FALLO] {nombre_prueba}")

def run_tests():
    print("--- PRUEBAS DEL MICROSERVICIO DE USUARIOS ---")
    
    # PUT /user: Crear usuario[cite: 1]
    res_crear = requests.put(f"{USER_URL}/user", json={"name": "estudiante", "password": "123"})
    test("Crear usuario nuevo (código 201)", res_crear.status_code == 201)
    
    # Extraer tokens para las siguientes pruebas
    datos_usuario = res_crear.json() if res_crear.status_code == 201 else {}
    uid = datos_usuario.get("uid", "")
    token = datos_usuario.get("token", "")
    headers = {"Authorization": f"Bearer {token}"}

    # PUT /user: Error al crear duplicado
    res_duplicado = requests.put(f"{USER_URL}/user", json={"name": "estudiante", "password": "123"})
    test("Error al crear usuario ya existente (código 409)", res_duplicado.status_code == 409)

    # POST /user: Iniciar sesión[cite: 1]
    res_login = requests.post(f"{USER_URL}/user", json={"name": "estudiante", "password": "123"})
    test("Iniciar sesión correctamente (código 200)", res_login.status_code == 200)

    # PATCH /user: Modificar contraseña[cite: 1]
    res_patch_user = requests.patch(f"{USER_URL}/user", json={"password": "456"}, headers=headers)
    test("Modificar contraseña con token válido (código 200)", res_patch_user.status_code == 200)

    print("\n--- PRUEBAS DEL MICROSERVICIO DE ARCHIVOS ---")

    # PUT /file/<uid>/<filename>: Crear documento[cite: 1]
    res_crear_file = requests.put(f"{FILE_URL}/file/{uid}/apuntes.txt", headers=headers, data="Contenido de prueba")
    test("Crear documento en el directorio (código 200)", res_crear_file.status_code == 200)
    if res_crear_file.status_code != 200:
        print(f"DEBUG ERROR SERVIDOR ARCHIVOS: {res_crear_file.status_code} - {res_crear_file.text}")

    # GET /file/<uid>: Listar documentos[cite: 1]
    res_listar = requests.get(f"{FILE_URL}/file/{uid}", headers=headers)
    archivos = res_listar.json().get("archivos", [])
    test("Listar documentos del propietario (código 200)", res_listar.status_code == 200 and len(archivos) > 0)

    # GET /file/<uid>/<filename>: Recuperar documento privado sin autorización (debe fallar)[cite: 1]
    res_get_privado_fail = requests.get(f"{FILE_URL}/file/{uid}/apuntes.txt")
    test("Denegar acceso a documento privado sin token (código 401)", res_get_privado_fail.status_code == 401)

    # GET /file/<uid>/<filename>: Recuperar documento privado con autorización[cite: 1]
    res_get_privado_ok = requests.get(f"{FILE_URL}/file/{uid}/apuntes.txt", headers=headers)
    test("Recuperar documento privado propio (código 200)", res_get_privado_ok.status_code == 200)

    # PATCH /file/<uid>/<filename>: Modificar visibilidad a público[cite: 1]
    res_visibilidad = requests.patch(f"{FILE_URL}/file/{uid}/apuntes.txt", headers=headers, json={"public": True})
    test("Modificar visibilidad del documento a público (código 200)", res_visibilidad.status_code == 200)

    # GET /file/<uid>/<filename>: Recuperar documento público sin autorización[cite: 1]
    res_get_publico = requests.get(f"{FILE_URL}/file/{uid}/apuntes.txt")
    test("Recuperar documento público sin token (código 200)", res_get_publico.status_code == 200 and res_get_publico.json().get("content") == "Contenido de prueba")

    # DELETE /file/<uid>/<filename>: Eliminar documento[cite: 1]
    res_borrar = requests.delete(f"{FILE_URL}/file/{uid}/apuntes.txt", headers=headers)
    test("Eliminar documento propio (código 200)", res_borrar.status_code == 200)

if __name__ == "__main__":
    try:
        run_tests()
    except requests.exceptions.ConnectionError:
        print("❌ Error de conexión: Asegúrate de que los contenedores Docker están levantados con 'docker compose up -d'.")