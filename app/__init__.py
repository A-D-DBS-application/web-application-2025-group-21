from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os
from flask_babel import Babel
from flask import session
from datetime import datetime # NIEUW: Nodig voor now() in templates


db = SQLAlchemy()
babel = Babel()

def create_app():
    app = Flask(__name__)

    load_dotenv()

    app.config["SECRET_KEY"] = "wachtwoord"
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    #BABEL CONFIG (meertaligheid)
    app.config["BABEL_DEFAULT_LOCALE"] = "en"
    app.config["BABEL_SUPPORTED_LOCALES"] = ["en", "nl", "fr"]
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = "translations"

    babel.init_app(app, locale_selector=get_locale)


    db.init_app(app)

    # NIEUWE SECTIE: CONTEXT PROCESSOR
    # Registreert de 'now' functie voor gebruik in alle Jinja2 templates.
    @app.context_processor
    def inject_now():
        """Maakt de datetime.now functie beschikbaar in Jinja templates."""
        return {'now': datetime.now}
    # EINDE NIEUWE SECTIE


    from .routes import main
    app.register_blueprint(main)

    return app

def get_locale():
    lang = session.get("language")
    if lang in ["en", "nl", "fr"]:
        return lang
    return "en"


