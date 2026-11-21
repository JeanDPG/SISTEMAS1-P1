from quart import Quart, jsonify
from app.routes import auth_bp
from app.redis_client import close_redis

# Compatibilidad con Flask 3.1+ en Quart
Quart.default_config = {**Quart.default_config, "PROVIDE_AUTOMATIC_OPTIONS": True}

app = Quart(__name__)
app.register_blueprint(auth_bp, url_prefix="/auth")

@app.errorhandler(400)
async def bad_request(e):
    return jsonify({"error": "Solicitud incorrecta"}), 400

@app.errorhandler(404)
async def not_found(e):
    return jsonify({"error": "Recurso no encontrado"}), 404

@app.errorhandler(405)
async def method_not_allowed(e):
    return jsonify({"error": "Método HTTP no permitido"}), 405

@app.errorhandler(500)
async def internal_error(e):
    return jsonify({"error": "Error interno del servidor"}), 500

@app.after_serving
async def shutdown():
    await close_redis()
