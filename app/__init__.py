from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from datetime import datetime
import os

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)

    load_dotenv()

    app.config["SECRET_KEY"] = "wachtwoord"
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # now() in templates
    @app.context_processor
    def inject_now():
        return {"now": datetime.now}

    from .routes import main
    app.register_blueprint(main)

    return app
