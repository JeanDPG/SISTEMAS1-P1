-- Optimizacion de /ventas/<anio>/<pais> para PostgreSQL 15.
-- Ejecuta la seccion 1 antes de los indices para guardar el plan base.
-- Con pocos datos PostgreSQL puede elegir Seq Scan; es un resultado normal.

-- 1. Plan de referencia: consulta original no sargable por anio.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT p.id_pedido, p.fecha_pago, p.total_pagado,
       u.id_usuario, u.nombre AS usuario_nombre, u.pais
FROM pedidos p
JOIN usuarios u ON p.id_usuario = u.id_usuario
WHERE u.pais = 'Francia'
  AND EXTRACT(YEAR FROM p.fecha_pago) = 2026;

-- 2. Estrategia A: indice funcional para la expresion original.
CREATE INDEX IF NOT EXISTS idx_pedidos_anio_pago
    ON pedidos ((EXTRACT(YEAR FROM fecha_pago)));

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT p.id_pedido, p.fecha_pago, p.total_pagado,
       u.id_usuario, u.nombre AS usuario_nombre, u.pais
FROM pedidos p
JOIN usuarios u ON p.id_usuario = u.id_usuario
WHERE u.pais = 'Francia'
  AND EXTRACT(YEAR FROM p.fecha_pago) = 2026;

-- 3. Estrategia B: intervalo semiabierto y indices compuestos.
-- El rango incluye todas las horas del anio y permite indexar fecha_pago.
CREATE INDEX IF NOT EXISTS idx_usuarios_pais_id
    ON usuarios (pais, id_usuario);
CREATE INDEX IF NOT EXISTS idx_pedidos_fecha_usuario
    ON pedidos (fecha_pago, id_usuario);

ANALYZE usuarios;
ANALYZE pedidos;

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT p.id_pedido, p.fecha_pago, p.total_pagado,
       u.id_usuario, u.nombre AS usuario_nombre, u.pais
FROM usuarios u
JOIN pedidos p ON p.id_usuario = u.id_usuario
WHERE u.pais = 'Francia'
  AND p.fecha_pago >= make_date(2026, 1, 1)
  AND p.fecha_pago < make_date(2027, 1, 1);

-- Para la memoria, compara Execution Time, filas estimadas/reales,
-- buffers y nodos. El indice funcional esta ligado a EXTRACT; el rango
-- semiabierto es mas flexible. Mide con volumen representativo: con tablas
-- pequenas un Seq Scan puede ser mas barato que recorrer indices.
