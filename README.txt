================================================================================
Práctica 3. Microservicios Avanzados y BBDD NoSQL
Sistemas Informáticos - Escuela Politécnica Superior (UAM)
================================================================================

1. DESPLIEGUE CON DOCKER COMPOSE
--------------------------------------------------------------------------------
Para construir y levantar todos los servicios en segundo plano:
  $ docker compose up --build -d

Para verificar que todos los contenedores están levantados y saludables:
  $ docker compose ps

Para detener y eliminar los contenedores:
  $ docker compose down

Para detener y borrar los volúmenes persistentes (limpieza total):
  $ docker compose down -v


2. SERVICIOS Y PUERTOS
--------------------------------------------------------------------------------
- API Gateway (Nginx):      Puerto 8080 (único expuesto al exterior)
- auth-service (Quart):     Puerto 5050 (red interna)
- library-service (Quart):  Puerto 5051 (red interna)
- redis (NoSQL AOF):        Puerto 6379 (red interna)
- mongodb (NoSQL):          Puerto 27017 (red interna)


3. EJECUCIÓN DE LOS TESTS (PYTEST)
--------------------------------------------------------------------------------
Se recomienda crear un entorno virtual para ejecutar la batería de pruebas:
  $ python3 -m venv .venv
  $ source .venv/bin/activate
  $ pip install -r p3_test_requirements.txt
  $ pytest p3_test.py
