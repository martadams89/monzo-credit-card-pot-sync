import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Signs session cookies. When unset, a random key is generated on first start
    # and kept in the database (see app.security.persistent_secret_key).
    SECRET_KEY = os.environ.get("SECRET_KEY") or None
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URI"
    ) or "sqlite:///" + os.path.join(basedir, "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LOCAL_URL = os.environ.get("POT_SYNC_LOCAL_URL") or "http://localhost:1337"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = LOCAL_URL.startswith("https://")
    PERMANENT_SESSION_LIFETIME = 30 * 24 * 3600
