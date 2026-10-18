import asyncio
import httpx

# URLs de los dos microservicios
USER_API_URL = "http://localhost:5050"
MAIN_API_URL = "http://localhost:5000"

async def probar_apis():
    async with httpx.AsyncClient(timeout=10.0) as client:
        print("==================================================")
        print("1. PRUEBAS DE LA API DE USUARIOS (user.py)")
        print("==================================================")

        # 1.1 Crear Usuario (Éxito)
        user_payload = {
            "name": "usuario_test",
            "password": "Password123",
            "pais": "Francia",
            "saldo": 50.00
        }
        res = await client.put(f"{USER_API_URL}/user", json=user_payload)
        print(f"[PUT /user] Crear usuario -> Status: {res.status_code}")
        print("  Respuesta:", res.json())
        assert res.status_code == 201
        
        data_user = res.json()
        user_id = int(data_user["uid"])
        token = data_user["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1.2 Crear Usuario Duplicado (Control de Errores - 409)
        res = await client.put(f"{USER_API_URL}/user", json=user_payload)
        print(f"[PUT /user] Crear duplicado -> Status: {res.status_code} (Esperado 409)")

        # 1.3 Login (Éxito)
        login_payload = {"name": "usuario_test", "password": "Password123"}
        res = await client.post(f"{USER_API_URL}/user/login", json=login_payload)
        print(f"[POST /user/login] Login exitoso -> Status: {res.status_code}")

        # 1.4 Login Erróneo (Control de Errores - 401)
        res = await client.post(f"{USER_API_URL}/user/login", json={"name": "usuario_test", "password": "mal"})
        print(f"[POST /user/login] Credenciales erróneas -> Status: {res.status_code} (Esperado 401)")

        # 1.5 Recargar Saldo
        saldo_payload = {"id_usuario": user_id, "monto": 25.50}
        res = await client.patch(f"{USER_API_URL}/user/saldo", json=saldo_payload, headers=headers)
        print(f"[PATCH /user/saldo] Recargar saldo -> Status: {res.status_code}")
        print("  Respuesta:", res.json())

        # 1.6 Logout
        res = await client.post(f"{USER_API_URL}/user/logout", headers=headers)
        print(f"[POST /user/logout] Logout -> Status: {res.status_code}")


        print("\n==================================================")
        print("2. PRUEBAS DE LA API PRINCIPAL (api.py)")
        print("==================================================")

        # 2.1 Crear Película
        peli_payload = {
            "titulo": "Película Pruebas",
            "anio": 2026,
            "precio": 12.00,
            "stock": 10,
            "id_director": None
        }
        res = await client.post(f"{MAIN_API_URL}/peliculas", json=peli_payload)
        print(f"[POST /peliculas] Crear película -> Status: {res.status_code}")
        print("  Respuesta:", res.json())
        peli_id = res.json()["id_pelicula"]

        # 2.2 Listar Películas con Filtro
        res = await client.get(f"{MAIN_API_URL}/peliculas?anio=2026")
        print(f"[GET /peliculas] Listar por año -> Status: {res.status_code}")
        print("  Películas encontradas:", len(res.json()))

        # 2.3 Añadir al Carrito (Actualiza stock por Trigger)
        carrito_payload = {"id_usuario": user_id, "id_pelicula": peli_id, "cantidad": 2}
        res = await client.post(f"{MAIN_API_URL}/carrito/add", json=carrito_payload)
        print(f"[POST /carrito/add] Añadir al carrito -> Status: {res.status_code}")

        # 2.4 Pagar Carrito (Verifica saldo y actualiza mediante Trigger)
        res = await client.post(f"{MAIN_API_URL}/carrito/pagar", json={"id_usuario": user_id})
        print(f"[POST /carrito/pagar] Pagar carrito -> Status: {res.status_code}")
        print("  Respuesta:", res.json())

        # 2.5 Intentar Pagar sin Saldo Suficiente (Control de Errores - Excepción Trigger)
        # Añadimos un producto que supere el saldo actual
        await client.post(f"{MAIN_API_URL}/carrito/add", json={"id_usuario": user_id, "id_pelicula": peli_id, "cantidad": 50})
        res = await client.post(f"{MAIN_API_URL}/carrito/pagar", json={"id_usuario": user_id})
        print(f"[POST /carrito/pagar] Saldo insuficiente -> Status: {res.status_code} (Esperado 400)")

        # 2.6 Votar Película (Entre 0 y 10)
        voto_payload = {"id_usuario": user_id, "puntuacion": 9.5}
        res = await client.post(f"{MAIN_API_URL}/peliculas/{peli_id}/votar", json=voto_payload)
        print(f"[POST /peliculas/{peli_id}/votar] Valorar -> Status: {res.status_code}")

        # 2.7 Consultar Puntuación Media (Vía Stored Procedure)
        res = await client.get(f"{MAIN_API_URL}/peliculas/{peli_id}/puntuacion")
        print(f"[GET /peliculas/{peli_id}/puntuacion] Media de nota -> Status: {res.status_code}")
        print("  Respuesta:", res.json())

        # 2.8 Consultar Ventas por Año y País (/ventas/<año>/<país>)
        res = await client.get(f"{MAIN_API_URL}/ventas/2026/Francia")
        print(f"[GET /ventas/2026/Francia] Historial de ventas -> Status: {res.status_code}")
        print("  Ventas encontradas:", len(res.json()))

        # 2.9 Borrar Película Creada
        res = await client.delete(f"{MAIN_API_URL}/peliculas/{peli_id}")
        print(f"[DELETE /peliculas/{peli_id}] Borrar película -> Status: {res.status_code}")


        print("\n==================================================")
        print("3. LIMPIEZA DE USUARIOS DE PRUEBA")
        print("==================================================")

        # 3.1 Borrar Usuario
        res = await client.request("DELETE", f"{USER_API_URL}/user", json={"id_usuario": user_id}, headers=headers)
        print(f"[DELETE /user] Borrar usuario -> Status: {res.status_code}")
        
        print("\n¡TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE!")

if __name__ == "__main__":
    asyncio.run(probar_apis())