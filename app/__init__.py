from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from flask_babel import Babel
from datetime import datetime
import os

db = SQLAlchemy()
babel = Babel()

def get_locale():
    # Belangrijk: Babel 4 krijgt de taal via locale_selector (hier)
    lang = session.get("language")
    if lang in ["en", "nl", "fr"]:
        return lang
    return "en"


def create_app():
    app = Flask(__name__)

    load_dotenv()

    app.config["SECRET_KEY"] = "wachtwoord"
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Babel configuratie
    app.config["BABEL_DEFAULT_LOCALE"] = "en"
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = "translations"

    # CRUCIAAL → locale_selector MOET in init_app voor Babel 4
    babel.init_app(app, locale_selector=get_locale)

    db.init_app(app)

    # now() in templates
    @app.context_processor
    def inject_now():
        return {'now': datetime.now}

    from .routes import main
    app.register_blueprint(main)

    return app
