-- Base de datos: si1
-- Usuario: alumnodb

-- Limpieza previa de tablas y funciones
DROP TABLE IF EXISTS valoraciones CASCADE;
DROP TABLE IF EXISTS lineas_pedido CASCADE;
DROP TABLE IF EXISTS pedidos CASCADE;
DROP TABLE IF EXISTS carrito_pelicula CASCADE;
DROP TABLE IF EXISTS carritos CASCADE;
DROP TABLE IF EXISTS pelicula_actor CASCADE;
DROP TABLE IF EXISTS peliculas CASCADE;
DROP TABLE IF EXISTS actores CASCADE;
DROP TABLE IF EXISTS directores CASCADE;
DROP TABLE IF EXISTS usuarios CASCADE;

DROP FUNCTION IF EXISTS sp_calcular_puntuacion_media(INT);
DROP FUNCTION IF EXISTS tf_actualizar_stock_carrito();
DROP FUNCTION IF EXISTS tf_procesar_pago_pedido();

-- =========================================================
-- 1. TABLAS PRINCIPALES
-- =========================================================

CREATE TABLE usuarios (
    id_usuario SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    contrasena_hash VARCHAR(255) NOT NULL,
    pais VARCHAR(50) NOT NULL,
    saldo DECIMAL(10, 2) NOT NULL DEFAULT 0.00 CHECK (saldo >= 0)
);

CREATE TABLE directores (
    id_director SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL
);

CREATE TABLE actores (
    id_actor SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL
);

CREATE TABLE peliculas (
    id_pelicula SERIAL PRIMARY KEY,
    titulo VARCHAR(150) NOT NULL,
    anio INT CHECK (anio > 1800),
    precio DECIMAL(8, 2) NOT NULL CHECK (precio >= 0),
    stock INT NOT NULL DEFAULT 0 CHECK (stock >= 0),
    id_director INT REFERENCES directores(id_director) ON DELETE SET NULL
);

CREATE TABLE pelicula_actor (
    id_pelicula INT REFERENCES peliculas(id_pelicula) ON DELETE CASCADE,
    id_actor INT REFERENCES actores(id_actor) ON DELETE CASCADE,
    PRIMARY KEY (id_pelicula, id_actor)
);

CREATE TABLE carritos (
    id_carrito SERIAL PRIMARY KEY,
    id_usuario INT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    estado VARCHAR(20) NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'completado', 'cancelado'))
);

CREATE TABLE carrito_pelicula (
    id_carrito INT REFERENCES carritos(id_carrito) ON DELETE CASCADE,
    id_pelicula INT REFERENCES peliculas(id_pelicula) ON DELETE CASCADE,
    cantidad INT NOT NULL DEFAULT 1 CHECK (cantidad > 0),
    PRIMARY KEY (id_carrito, id_pelicula)
);

CREATE TABLE pedidos (
    id_pedido SERIAL PRIMARY KEY,
    id_usuario INT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    fecha_pago TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    total_pagado DECIMAL(10, 2) NOT NULL DEFAULT 0.00 CHECK (total_pagado >= 0)
);

CREATE TABLE lineas_pedido (
    id_pedido INT REFERENCES pedidos(id_pedido) ON DELETE CASCADE,
    id_pelicula INT REFERENCES peliculas(id_pelicula) ON DELETE CASCADE,
    cantidad INT NOT NULL CHECK (cantidad > 0),
    precio_unitario DECIMAL(8, 2) NOT NULL CHECK (precio_unitario >= 0),
    PRIMARY KEY (id_pedido, id_pelicula)
);

CREATE TABLE valoraciones (
    id_usuario INT REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    id_pelicula INT REFERENCES peliculas(id_pelicula) ON DELETE CASCADE,
    puntuacion NUMERIC(3, 1) NOT NULL CHECK (puntuacion >= 0 AND puntuacion <= 10),
    PRIMARY KEY (id_usuario, id_pelicula)
);

-- =========================================================
-- 2. PROCEDIMIENTOS ALMACENADOS (Stored Procedures / Functions)
-- =========================================================

-- SP para calcular el promedio de valoraciones de una película (0 a 10)
CREATE OR REPLACE FUNCTION sp_calcular_puntuacion_media(p_id_pelicula INT)
RETURNS NUMERIC(3, 1) AS $$
DECLARE
    v_media NUMERIC(3, 1);
BEGIN
    SELECT COALESCE(AVG(puntuacion), 0.0)
    INTO v_media
    FROM valoraciones
    WHERE id_pelicula = p_id_pelicula;
    
    RETURN v_media;
END;
$$ LANGUAGE plpgsql;

-- =========================================================
-- 3. TRIGGERS Y FUNCIONES ASOCIADAS
-- =========================================================

-- Trigger 1: Gestión de stock al modificar productos en el carrito
CREATE OR REPLACE FUNCTION tf_actualizar_stock_carrito()
RETURNS TRIGGER AS $$
DECLARE
    v_diferencia INT;
BEGIN
    IF (TG_OP = 'INSERT') THEN
        UPDATE peliculas 
        SET stock = stock - NEW.cantidad 
        WHERE id_pelicula = NEW.id_pelicula;
    ELSIF (TG_OP = 'UPDATE') THEN
        v_diferencia := NEW.cantidad - OLD.cantidad;
        UPDATE peliculas 
        SET stock = stock - v_diferencia 
        WHERE id_pelicula = NEW.id_pelicula;
    ELSIF (TG_OP = 'DELETE') THEN
        UPDATE peliculas 
        SET stock = stock + OLD.cantidad 
        WHERE id_pelicula = OLD.id_pelicula;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_actualizar_stock_carrito
AFTER INSERT OR UPDATE OR DELETE ON carrito_pelicula
FOR EACH ROW EXECUTE FUNCTION tf_actualizar_stock_carrito();

-- Trigger 2: Descontar saldo del cliente al registrar un nuevo pago de pedido
CREATE OR REPLACE FUNCTION tf_procesar_pago_pedido()
RETURNS TRIGGER AS $$
DECLARE
    v_saldo_actual DECIMAL(10, 2);
BEGIN
    SELECT saldo INTO v_saldo_actual 
    FROM usuarios 
    WHERE id_usuario = NEW.id_usuario;

    IF v_saldo_actual < NEW.total_pagado THEN
        RAISE EXCEPTION 'Saldo insuficiente para completar el pedido. Saldo actual: %, Necesario: %', v_saldo_actual, NEW.total_pagado;
    END IF;

    UPDATE usuarios 
    SET saldo = saldo - NEW.total_pagado 
    WHERE id_usuario = NEW.id_usuario;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_procesar_pago_pedido
BEFORE INSERT ON pedidos
FOR EACH ROW EXECUTE FUNCTION tf_procesar_pago_pedido();