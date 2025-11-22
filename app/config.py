class Config:
    SECRET_KEY = 'your_secret_key_here'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres.username:3L5R4kOlMePehZtt@localhost:port/dbname'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ➜ voeg deze toe
    UPLOAD_FOLDER = "app/static/profile_pics"
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
