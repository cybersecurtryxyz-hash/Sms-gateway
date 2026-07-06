import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    """
    Central configuration. Everything sensitive is read from the environment
    so no secrets ever live in source control. Sensible dev fallbacks are
    provided but a real deployment should always set these explicitly.
    """

    # --- Database ---------------------------------------------------
    DATABASE_PATH = os.environ.get("DATABASE_PATH")  # explicit override wins

    # --- Secrets ------------------------------------------------------
    # Falls back to a dev-only value with a loud warning at boot time
    ADMIN_PASSWORD_DEFAULT = os.environ.get("ADMIN_PASSWORD", "admin123")
    DEVICE_TOKEN = os.environ.get("DEVICE_TOKEN", "smsgateway_secret_token_123")
    MY_NUMBER = os.environ.get("MY_NUMBER", "+91-98765-43210")
    SECRET_KEY = os.environ.get("SECRET_KEY", "sms_gateway_fallback_secret_key_123456789")

    # --- Misc -----------------------------------------------------
    ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = ENV == "development"

    @staticmethod
    def resolve_db_path():
        """
        Pick a writable location for the SQLite file depending on the
        platform we're running on (Fly/Railway volume, Vercel /tmp, or
        local dev), unless DATABASE_PATH was explicitly set.
        """
        if Config.DATABASE_PATH:
            return Config.DATABASE_PATH

        default_path = os.path.join(BASE_DIR, "sms_gateway.db")

        if os.path.exists("/data") and os.access("/data", os.W_OK):
            return "/data/sms_gateway.db"

        if os.environ.get("VERCEL") or not os.access(
            os.path.dirname(default_path) or ".", os.W_OK
        ):
            return "/tmp/sms_gateway.db"

        return default_path
