import os
import uuid
import hashlib
from quart import Quart, request
from sqlalchemy import text
from database import async_session
from sqlalchemy.exc import IntegrityError

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
    """Obtiene catálogo de películas filtrado por título o año."""
    titulo = request.args.get("titulo")
    anio_raw = request.args.get("anio")

    sql_base = """
        SELECT p.id_pelicula, p.titulo, p.anio, p.precio, p.stock, d.nombre AS director
        FROM peliculas p
        LEFT JOIN directores d ON p.id_director = d.id_director
    """
    
    condiciones = []
    params = {}

    if titulo and titulo.strip():
        condiciones.append("p.titulo ILIKE '%' || :titulo || '%'")
        params["titulo"] = titulo.strip()

    if anio_raw and anio_raw.isdigit():
        condiciones.append("p.anio = :anio")
        params["anio"] = int(anio_raw)

    if condiciones:
        sql_base += " WHERE " + " AND ".join(condiciones)

    query = text(sql_base)

    async with async_session() as session:
        res = await session.execute(query, params)
        peliculas = [dict(row._mapping) for row in res.fetchall()]
        
        for p in peliculas:
            if "precio" in p and p["precio"] is not None:
                p["precio"] = float(p["precio"])

        return peliculas, 200


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


from sqlalchemy.exc import DBAPIError, IntegrityError

@app.post("/carrito/pagar")
async def pagar_carrito():
    data = await request.get_json() or {}
    id_usuario = data.get("id_usuario") 

    async with async_session() as session:
        # 1. Obtener carrito activo
        res_carrito = await session.execute(
            text("SELECT id_carrito FROM carritos WHERE id_usuario = :uid AND estado = 'activo'"),
            {"uid": id_usuario}
        )
        carrito = res_carrito.fetchone()

        if not carrito:
            return {"error": "No hay un carrito activo para este usuario"}, 400

        id_carrito = carrito.id_carrito

        # 2. Calcular total a pagar
        res_total = await session.execute(
            text("""
                SELECT COALESCE(SUM(cp.cantidad * p.precio), 0.00) AS total
                FROM carrito_pelicula cp
                JOIN peliculas p ON cp.id_pelicula = p.id_pelicula
                WHERE cp.id_carrito = :cid
            """),
            {"cid": id_carrito}
        )
        total_carrito = res_total.scalar()

        if total_carrito <= 0:
            return {"error": "El carrito está vacío"}, 400

        try:
            # 3. Intentar insertar el pedido (se dispara el TRIGGER tf_procesar_pago_pedido)
            query_pedido = text("""
                INSERT INTO pedidos (id_usuario, total_pagado) 
                VALUES (:uid, :total) 
                RETURNING id_pedido, fecha_pago
            """)
            res_pedido = await session.execute(query_pedido, {"uid": id_usuario, "total": total_carrito})
            nuevo_pedido = res_pedido.fetchone()

            # 4. Actualizar estado del carrito
            await session.execute(
                text("UPDATE carritos SET estado = 'completado' WHERE id_carrito = :cid"),
                {"cid": id_carrito}
            )

            await session.commit()

            return {
                "mensaje": "Pago completado correctamente",
                "pedido": {
                    "id_pedido": nuevo_pedido.id_pedido,
                    "fecha_pago": str(nuevo_pedido.fecha_pago),
                    "total_pagado": str(total_carrito)
                }
            }, 200

        except (IntegrityError, DBAPIError) as e:
            # Revertir los cambios en la transacción
            await session.rollback()
            
            # Comprobar si el fallo proviene del TRIGGER de saldo insuficiente
            mensaje_error = str(e)
            if "Saldo insuficiente" in mensaje_error:
                return {"error": "Saldo insuficiente para realizar la compra"}, 400
            
            return {"error": "Error de integridad en la base de datos", "detalle": mensaje_error}, 400

        except Exception as e:
            await session.rollback()
            return {"error": f"Error inesperado: {str(e)}"}, 500

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