import sqlite3
import logging

from werkzeug.security import generate_password_hash

from .config import Config

logger = logging.getLogger(__name__)

_db_path = None  # resolved lazily, cached after first successful connection


def _try_connect(path):
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    # Write test to make sure the location is actually usable
    conn.execute("CREATE TABLE IF NOT EXISTS _write_test (id INTEGER)")
    conn.execute("DROP TABLE _write_test")
    conn.commit()
    return conn


def get_db():
    """
    Return a SQLite connection, falling back gracefully:
    resolved path -> /tmp -> in-memory, logging each fallback.
    """
    global _db_path
    target_path = _db_path or Config.resolve_db_path()

    # Try original target path
    try:
        conn = _try_connect(target_path)
        _db_path = target_path  # Cache successful connection path
        return conn
    except Exception as e:
        logger.warning("Database at %s is not writable: %s", target_path, e)

    # Try /tmp fallback
    if target_path != "/tmp/sms_gateway.db":
        try:
            conn = _try_connect("/tmp/sms_gateway.db")
            _db_path = "/tmp/sms_gateway.db"  # Cache successful fallback path
            return conn
        except Exception as e:
            logger.warning("Fallback to /tmp failed: %s", e)

    logger.warning("Falling back to transient in-memory SQLite database for this connection")
    conn = sqlite3.connect(":memory:", timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables and seed default data if the DB is empty."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'coworker',
                allowed_numbers TEXT DEFAULT '*'
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                direction TEXT NOT NULL,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                text TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT NOT NULL,
                owner TEXT,
                sim_operator TEXT
            )
            """
        )
        # Safe migration for DBs created before the `owner` column existed
        try:
            cursor.execute("ALTER TABLE messages ADD COLUMN owner TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

        # Safe migration for DBs created before the `sim_operator` column existed
        try:
            cursor.execute("ALTER TABLE messages ADD COLUMN sim_operator TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

        # Safe migration for allowed_numbers column
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN allowed_numbers TEXT DEFAULT '*'")
        except sqlite3.OperationalError:
            pass  # column already exists

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS device_status (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                battery TEXT NOT NULL,
                version TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                secret_token TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gateway_numbers (
                phone_number TEXT PRIMARY KEY,
                operator_name TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute("SELECT COUNT(*) FROM gateway_numbers")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO gateway_numbers (phone_number, operator_name) VALUES (?, ?)",
                ("8800112112", "Airtel")
            )
            cursor.execute(
                "INSERT INTO gateway_numbers (phone_number, operator_name) VALUES (?, ?)",
                ("7021265165", "Jio")
            )
            cursor.execute(
                "INSERT INTO gateway_numbers (phone_number, operator_name) VALUES (?, ?)",
                ("7824834221", "Vodafone idea")
            )

        # Delete default coworkers if they exist from previous template runs to ensure clean state
        cursor.execute("DELETE FROM users WHERE username IN ('priya', 'rahul')")

        cursor.execute("SELECT COUNT(*) FROM settings WHERE key = 'admin_password'")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO settings (key, value) VALUES ('admin_password', ?)",
                (generate_password_hash(Config.ADMIN_PASSWORD_DEFAULT),),
            )

        cursor.execute("SELECT COUNT(*) FROM device_status")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                """
                INSERT INTO device_status
                    (id, name, battery, version, last_seen, secret_token, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "node1",
                    "Realme 9 Integrator Node",
                    "85%",
                    "1.1",
                    "Never",
                    Config.DEVICE_TOKEN,
                    "offline",
                ),
            )

        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Error during init_db: %s", e)
