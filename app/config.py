import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_INSECURE_ADMIN_PASSWORD_DEFAULT = "admin123"
_INSECURE_DEVICE_TOKEN_DEFAULT = "smsgateway_secret_token_123"
_INSECURE_SECRET_KEY_DEFAULT = "sms_gateway_fallback_secret_key_123456789"


class Config:
    """
    Central configuration. Everything sensitive is read from the environment
    so no secrets ever live in source control. Dev-only fallbacks exist below
    for local `python run.py` convenience, but create_app() refuses to boot
    with them when it detects it's running on a hosted platform (Railway,
    Fly, Vercel, Heroku) - see insecure_defaults_in_use() / __init__.py.
    """

    # --- Database ---------------------------------------------------
    DATABASE_PATH = os.environ.get("DATABASE_PATH")  # explicit override wins

    # --- Secrets ------------------------------------------------------
    # Falls back to a dev-only value with a loud warning at boot time
    ADMIN_PASSWORD_DEFAULT = os.environ.get("ADMIN_PASSWORD", _INSECURE_ADMIN_PASSWORD_DEFAULT)
    DEVICE_TOKEN = os.environ.get("DEVICE_TOKEN", _INSECURE_DEVICE_TOKEN_DEFAULT)
    MY_NUMBER = os.environ.get("MY_NUMBER", "+91-98765-43210")
    SECRET_KEY = os.environ.get("SECRET_KEY", _INSECURE_SECRET_KEY_DEFAULT)

    # Explicit escape hatch for people who really do want to run with the
    # dev defaults on a hosted platform (e.g. a throwaway demo). Off by default.
    ALLOW_INSECURE_DEFAULTS = os.environ.get("ALLOW_INSECURE_DEFAULTS", "false").lower() == "true"

    # --- Misc -----------------------------------------------------
    ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = ENV == "development"

    @staticmethod
    def insecure_defaults_in_use():
        """Names of secrets that are still sitting on their insecure dev default."""
        problems = []
        if Config.ADMIN_PASSWORD_DEFAULT == _INSECURE_ADMIN_PASSWORD_DEFAULT:
            problems.append("ADMIN_PASSWORD")
        if Config.DEVICE_TOKEN == _INSECURE_DEVICE_TOKEN_DEFAULT:
            problems.append("DEVICE_TOKEN")
        if Config.SECRET_KEY == _INSECURE_SECRET_KEY_DEFAULT:
            problems.append("SECRET_KEY")
        return problems

    @staticmethod
    def running_on_hosted_platform():
        """Best-effort detection of Railway/Fly/Vercel/Heroku so we only hard
        -block boot on a real deployment, not a local `python run.py`."""
        return any(
            os.environ.get(v)
            for v in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "FLY_APP_NAME", "VERCEL", "DYNO")
        )

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
