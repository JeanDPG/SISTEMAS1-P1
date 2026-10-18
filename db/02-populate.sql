-- =========================================================
-- SCRIPT DE CARGA DE DATOS INICIALES (populate.sql)
-- Base de Datos: si1 | Usuario: alumnodb
-- =========================================================

-- Limpieza preventiva de datos existentes
TRUNCATE TABLE valoraciones, lineas_pedido, pedidos, carrito_pelicula, carritos, 
               pelicula_actor, peliculas, actores, directores, usuarios RESTART IDENTITY CASCADE;

-- ---------------------------------------------------------
-- 1. USUARIOS
-- (Contraseñas simuladas en hash; saldo disponible suficiente)
-- ---------------------------------------------------------
INSERT INTO usuarios (nombre, contrasena_hash, pais, saldo) VALUES
('Juan Pérez',     '$2b$12$eImiTXuWVxfM37uY4JANjO...hash1', 'España',   100.00),
('Pierre Dubois', '$2b$12$eImiTXuWVxfM37uY4JANjO...hash2', 'Francia',  150.50),
('Marie Laurent', '$2b$12$eImiTXuWVxfM37uY4JANjO...hash3', 'Francia',  200.00),
('John Doe',      '$2b$12$eImiTXuWVxfM37uY4JANjO...hash4', 'EEUU',      50.00),
('Alice Smith',   '$2b$12$eImiTXuWVxfM37uY4JANjO...hash5', 'Reino Unido', 80.00);

-- ---------------------------------------------------------
-- 2. DIRECTORES
-- ---------------------------------------------------------
INSERT INTO directores (nombre) VALUES
('Christopher Nolan'),
('Denis Villeneuve'),
('Quentin Tarantino'),
('Pedro Almodóvar');

-- ---------------------------------------------------------
-- 3. ACTORES
-- ---------------------------------------------------------
INSERT INTO actores (nombre) VALUES
('Leonardo DiCaprio'),
('Cillian Murphy'),
('Timothée Chalamet'),
('Zendaya'),
('Brad Pitt'),
('Penélope Cruz');

-- ---------------------------------------------------------
-- 4. PELÍCULAS
-- (Nota: El stock bajará automáticamente si se añaden a carritos vía Trigger)
-- ---------------------------------------------------------
INSERT INTO peliculas (titulo, anio, precio, stock, id_director) VALUES
('Inception',         2010, 14.99, 50, 1),
('Oppenheimer',       2023, 19.99, 30, 1),
('Dune: Part Two',    2024, 18.50, 40, 2),
('Pulp Fiction',      1994,  9.99, 25, 3),
('Volver',            2006,  8.99, 15, 4);

-- ---------------------------------------------------------
-- 5. RELACIÓN PELÍCULA - ACTOR (N:M)
-- ---------------------------------------------------------
INSERT INTO pelicula_actor (id_pelicula, id_actor) VALUES
(1, 1), -- Inception - Leonardo DiCaprio
(2, 2), -- Oppenheimer - Cillian Murphy
(3, 3), -- Dune: Part Two - Timothée Chalamet
(3, 4), -- Dune: Part Two - Zendaya
(4, 5), -- Pulp Fiction - Brad Pitt
(5, 6); -- Volver - Penélope Cruz

-- ---------------------------------------------------------
-- 6. VALORACIONES (0 a 10)
-- ---------------------------------------------------------
INSERT INTO valoraciones (id_usuario, id_pelicula, puntuacion) VALUES
(1, 1, 9.5),
(1, 2, 8.0),
(2, 1, 10.0),
(2, 3, 9.0),
(3, 2, 8.5),
(3, 3, 9.8),
(4, 4, 7.5);

-- ---------------------------------------------------------
-- 7. CARRITOS Y SUS ARTÍCULOS
-- (Nota: Al insertar en carrito_pelicula, el Trigger actualizará el stock)
-- ---------------------------------------------------------
-- Carritos activos/pendientes
INSERT INTO carritos (id_usuario, estado) VALUES
(1, 'activo'),
(2, 'completado'),
(3, 'completado');

-- Artículos dentro de los carritos
INSERT INTO carrito_pelicula (id_carrito, id_pelicula, cantidad) VALUES
(1, 1, 1), -- Usuario 1 tiene Inception en carrito activo
(2, 3, 2), -- Usuario 2 tuvo Dune 2
(3, 2, 1); -- Usuario 3 tuvo Oppenheimer

-- ---------------------------------------------------------
-- 8. PEDIDOS Y LÍNEAS DE PEDIDO
-- (Importante: Fechas en 2026 para probar el endpoint /ventas/2026/Francia)
-- (El Trigger de pago verificará y descontará el saldo automáticamente)
-- ---------------------------------------------------------

-- Pedido 1 (Francia, 2026)
INSERT INTO pedidos (id_usuario, fecha_pago, total_pagado) VALUES
(2, '2026-03-15 10:30:00+01', 37.00);

INSERT INTO lineas_pedido (id_pedido, id_pelicula, cantidad, precio_unitario) VALUES
(1, 3, 2, 18.50); -- 2 x Dune: Part Two

-- Pedido 2 (Francia, 2026)
INSERT INTO pedidos (id_usuario, fecha_pago, total_pagado) VALUES
(3, '2026-05-20 16:45:00+01', 19.99);

INSERT INTO lineas_pedido (id_pedido, id_pelicula, cantidad, precio_unitario) VALUES
(2, 2, 1, 19.99); -- 1 x Oppenheimer

-- Pedido 3 (España, 2026 - Para contraste)
INSERT INTO pedidos (id_usuario, fecha_pago, total_pagado) VALUES
(1, '2026-01-10 12:00:00+01', 14.99);

INSERT INTO lineas_pedido (id_pedido, id_pelicula, cantidad, precio_unitario) VALUES
(3, 1, 1, 14.99); -- 1 x Inception