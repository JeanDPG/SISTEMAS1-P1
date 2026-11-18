from quart import Quart
from app.routes import auth_bp

app = Quart(__name__)
app.register_blueprint(auth_bp, url_prefix="/auth")
