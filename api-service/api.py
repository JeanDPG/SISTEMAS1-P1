import os
import uuid
import hashlib
from quart import Quart, request
from sqlalchemy import text
from database import async_session

app = Quart(__name__)

# Secreto para verificar tokens
SHARED_SECRET_STR = os.getenv("SHARED_SECRET", "12345678-1234-5678-1234-567812345678")
SHARED_SECRET = uuid.UUID(SHARED_SECRET_STR)

def verify_token(token: str, uid: int) -> bool:
    """Verifica si el token pertenece al id_usuario (uid)."""
    expected_token = str(uuid.uuid5(SHARED_SECRET, str(uid)))
    return token == expected_token

def get_authenticated_user_id():
    """Extrae el token Bearer y verifica la autenticación."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return auth[len("Bearer "):]


# =========================================================
# 1. GESTIÓN DE RECURSOS PRINCIPALES (Películas)
# =========================================================

@app.post("/peliculas")
async def crear_pelicula():
    """Creación de una nueva película."""
    try:
        data = await request.get_json()
    except Exception:
        return {"error": "JSON mal formado"}, 400

    titulo = data.get("titulo")
    anio = data.get("anio")
    precio = data.get("precio")
    stock = data.get("stock", 0)
    id_director = data.get("id_director")

    if not titulo or precio is None:
        return {"error": "Título y precio son obligatorios"}, 400

    query = text("""
        INSERT INTO peliculas (titulo, anio, precio, stock, id_director)
        VALUES (:titulo, :anio, :precio, :stock, :id_director)
        RETURNING id_pelicula, titulo, anio, precio, stock;
    """)

    async with async_session() as session:
        async with session.begin():
            res = await session.execute(query, {
                "titulo": titulo, "anio": anio, "precio": precio,
                "stock": stock, "id_director": id_director
            })
            peli = res.fetchone()
            return dict(peli._mapping), 201


@app.delete("/peliculas/<int:id_pelicula>")
async def borrar_pelicula(id_pelicula):
    """Borrado de una película por ID."""
    query = text("DELETE FROM peliculas WHERE id_pelicula = :id_pelicula RETURNING id_pelicula;")
    
    async with async_session() as session:
        async with session.begin():
            res = await session.execute(query, {"id_pelicula": id_pelicula})
            deleted = res.fetchone() 
            if not deleted:
                return {"error": "Película no encontrada"}, 404
            return {"mensaje": f"Película {id_pelicula} eliminada correctamente"}, 200


# =========================================================
# 2. OBTENER LISTADO DE PELÍCULAS
# =========================================================

@app.get("/peliculas")
async def listar_peliculas():
    """Obtiene catálogo de películas filtrado por título o año (si se pasa por query params)."""
    titulo = request.args.get("titulo")
    anio_raw = request.args.get("anio")

    # Parsear año a número entero si existe
    anio = int(anio_raw) if anio_raw and anio_raw.isdigit() else None

    # Casteo explícito ::TEXT y ::INT para resolver AmbiguousParameterError en PostgreSQL
    query = text("""
        SELECT p.id_pelicula, p.titulo, p.anio, p.precio, p.stock, d.nombre AS director
        FROM peliculas p
        LEFT JOIN directores d ON p.id_director = d.id_director
        WHERE (:titulo::TEXT IS NULL OR p.titulo ILIKE '%' || :titulo::TEXT || '%')
          AND (:anio::INT IS NULL OR p.anio = :anio::INT);
    """)

    async with async_session() as session:
        res = await session.execute(query, {
            "titulo": titulo if titulo else None, 
            "anio": anio
        })
        peliculas = [dict(row._mapping) for row in res.fetchall()]
        
        # Convertir tipos Decimal a float para permitir serialización a JSON
        for p in peliculas:
            if "precio" in p and p["precio"] is not None:
                p["precio"] = float(p["precio"])

        return jsonify(peliculas), 200


# =========================================================
# 3. CONSUMO DE PELÍCULAS (Carrito y Pago)
# =========================================================

@app.post("/carrito/add")
async def anadir_al_carrito():
    """a. Añadir película al carrito (El trigger actualiza el stock automáticamente)."""
    try:
        data = await request.get_json()
    except Exception:
        return {"error": "JSON mal formado"}, 400

    id_usuario = data.get("id_usuario")
    id_pelicula = data.get("id_pelicula")
    cantidad = data.get("cantidad", 1)

    if not id_usuario or not id_pelicula:
        return {"error": "Faltan id_usuario o id_pelicula"}, 400

    # Usamos una sola consulta SQL (UPSERT) para obtener/crear carrito e insertar el elemento
    query = text("""
        WITH c AS (
            INSERT INTO carritos (id_usuario, estado)
            VALUES (:id_usuario, 'activo')
            ON CONFLICT DO NOTHING
            RETURNING id_carrito
        ),
        target_carrito AS (
            SELECT id_carrito FROM c
            UNION ALL
            SELECT id_carrito FROM carritos 
            WHERE id_usuario = :id_usuario AND estado = 'activo'
            LIMIT 1
        )
        INSERT INTO carrito_pelicula (id_carrito, id_pelicula, cantidad)
        SELECT id_carrito, :id_pelicula, :cantidad FROM target_carrito
        ON CONFLICT (id_carrito, id_pelicula) 
        DO UPDATE SET cantidad = carrito_pelicula.cantidad + EXCLUDED.cantidad
        RETURNING id_carrito, id_pelicula, cantidad;
    """)

    async with async_session() as session:
        async with session.begin():
            res = await session.execute(query, {
                "id_usuario": id_usuario,
                "id_pelicula": id_pelicula,
                "cantidad": cantidad
            })
            item = res.fetchone()
            return {"mensaje": "Película añadida al carrito", "detalle": dict(item._mapping)}, 200


@app.post("/carrito/pagar")
async def pagar_carrito():
    """
    b. Pagar el carrito de la compra.
    c. Almacenar la fecha de pago y calcular total.
    (El trigger del pedido descontará automáticamente el saldo al usuario).
    """
    try:
        data = await request.get_json()
    except Exception:
        return {"error": "JSON mal formado"}, 400

    id_usuario = data.get("id_usuario")
    if not id_usuario:
        return {"error": "Falta id_usuario"}, 400

    # Una sola consulta realiza: cálculo del total del carrito, inserción del pedido, 
    # vuelco de líneas de pedido y cierre del carrito.
    query = text("""
        WITH carrito_activo AS (
            SELECT id_carrito FROM carritos 
            WHERE id_usuario = :id_usuario AND estado = 'activo'
            LIMIT 1
        ),
        items_precio AS (
            SELECT cp.id_pelicula, cp.cantidad, p.precio, (cp.cantidad * p.precio) AS subtotal
            FROM carrito_pelicula cp
            JOIN peliculas p ON cp.id_pelicula = p.id_pelicula
            WHERE cp.id_carrito = (SELECT id_carrito FROM carrito_activo)
        ),
        nuevo_pedido AS (
            INSERT INTO pedidos (id_usuario, fecha_pago, total_pagado)
            SELECT :id_usuario, CURRENT_TIMESTAMP, COALESCE(SUM(subtotal), 0)
            FROM items_precio
            RETURNING id_pedido, fecha_pago, total_pagado
        ),
        ins_lineas AS (
            INSERT INTO lineas_pedido (id_pedido, id_pelicula, cantidad, precio_unitario)
            SELECT np.id_pedido, ip.id_pelicula, ip.cantidad, ip.precio
            FROM nuevo_pedido np CROSS JOIN items_precio ip
        ),
        cierra_carrito AS (
            UPDATE carritos SET estado = 'completado'
            WHERE id_carrito = (SELECT id_carrito FROM carrito_activo)
        )
        SELECT id_pedido, fecha_pago, total_pagado FROM nuevo_pedido;
    """)

    async with async_session() as session:
        async with session.begin():
            try:
                res = await session.execute(query, {"id_usuario": id_usuario})
                pedido = res.fetchone()
                if not pedido:
                    return {"error": "No hay un carrito activo para procesar el pago"}, 400
                return {
                    "mensaje": "Pago completado correctamente",
                    "pedido": dict(pedido._mapping)
                }, 200
            except Exception as e:
                # Captura la excepción enviada por el trigger de falta de saldo
                return {"error": str(e)}, 400


# =========================================================
# 4. CONSULTAS AVANZADAS
# =========================================================

@app.post("/peliculas/<int:id_pelicula>/votar")
async def votar_pelicula(id_pelicula):
    """a. Permitir que un usuario vote una película (de 0 a 10)."""
    try:
        data = await request.get_json()
    except Exception:
        return {"error": "JSON mal formado"}, 400

    id_usuario = data.get("id_usuario")
    puntuacion = data.get("puntuacion")

    if not id_usuario or puntuacion is None or not (0 <= float(puntuacion) <= 10):
        return {"error": "id_usuario y puntuación (entre 0 y 10) son obligatorios"}, 400

    query = text("""
        INSERT INTO valoraciones (id_usuario, id_pelicula, puntuacion)
        VALUES (:id_usuario, :id_pelicula, :puntuacion)
        ON CONFLICT (id_usuario, id_pelicula)
        DO UPDATE SET puntuacion = EXCLUDED.puntuacion
        RETURNING id_usuario, id_pelicula, puntuacion;
    """)

    async with async_session() as session:
        async with session.begin():
            res = await session.execute(query, {
                "id_usuario": id_usuario,
                "id_pelicula": id_pelicula,
                "puntuacion": puntuacion
            })
            val = res.fetchone()
            return {"mensaje": "Puntuación guardada", "valoracion": dict(val._mapping)}, 200


@app.get("/peliculas/<int:id_pelicula>/puntuacion")
async def obtener_puntuacion_media(id_pelicula):
    """b. Consultar la puntuación media ejecutando el Stored Procedure `sp_calcular_puntuacion_media`."""
    query = text("SELECT sp_calcular_puntuacion_media(:id_pelicula) AS media;")

    async with async_session() as session:
        res = await session.execute(query, {"id_pelicula": id_pelicula})
        media = res.scalar_one()
        return {"id_pelicula": id_pelicula, "puntuacion_media": float(media)}, 200


# =========================================================
# 5. ENDPOINT ESPECIAL DE VENTAS (/ventas/<año>/<país>)
# =========================================================

@app.get("/ventas/<int:anio>/<string:pais>")
async def recuperar_ventas(anio, pais):
    """
    Recupera el historial de compras para un año y país determinado.
    Ejemplo: /ventas/2026/Francia
    """
    query = text("""
        SELECT 
            p.id_pedido,
            p.fecha_pago,
            p.total_pagado,
            u.id_usuario,
            u.nombre AS usuario_nombre,
            u.pais
        FROM pedidos p
        JOIN usuarios u ON p.id_usuario = u.id_usuario
        WHERE u.pais = :pais 
          AND EXTRACT(YEAR FROM p.fecha_pago) = :anio;
    """)

    async with async_session() as session:
        res = await session.execute(query, {"anio": anio, "pais": pais})
        ventas = [dict(row._mapping) for row in res.fetchall()]
        return ventas, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)