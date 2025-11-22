from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)

    load_dotenv()

    # laad configuratie uit Config class
    from .config import Config
    app.config.from_object(Config)

    # database
    db.init_app(app)

    # blueprint
    from .routes import main
    app.register_blueprint(main)

    return app
