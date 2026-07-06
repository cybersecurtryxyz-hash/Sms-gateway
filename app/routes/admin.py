import sqlite3
from datetime import datetime

from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash

from ..db import get_db
from ..security import check_admin_auth, verify_admin_password, set_admin_password, generate_admin_token
from ..config import Config

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _require_admin():
    """Returns an error response tuple if unauthorized, else None."""
    if not check_admin_auth(request):
        return jsonify({"error": "Unauthorized"}), 401
    return None


@admin_bp.route("/login", methods=["POST"])
def admin_login():
    data = request.json or {}
    if verify_admin_password(data.get("password")):
        # Issue a short-lived signed session token instead of asking the
        # client to remember/replay the raw password on every request.
        token = generate_admin_token()
        return jsonify({"success": True, "token": token}), 200
    return jsonify({"error": "Invalid admin password"}), 401


@admin_bp.route("/change-password", methods=["POST"])
def admin_change_password():
    if (err := _require_admin()) is not None:
        return err

    data = request.json or {}
    new_password = data.get("new_password", "").strip()
    if not new_password:
        return jsonify({"error": "New password cannot be empty"}), 400

    set_admin_password(new_password)
    return jsonify({"success": True}), 200


@admin_bp.route("/status", methods=["GET"])
def admin_status():
    if (err := _require_admin()) is not None:
        return err

    conn = get_db()
    row = conn.execute("SELECT * FROM device_status LIMIT 1").fetchone()
    conn.close()

    if not row:
        return jsonify(
            {
                "status": "offline",
                "name": "No registered node",
                "battery": "0%",
                "version": "1.0",
                "last_seen": "Never",
                "secret_token": Config.DEVICE_TOKEN,
            }
        )

    status = row["status"]
    if row["last_seen"] != "Never":
        try:
            last_dt = datetime.strptime(row["last_seen"], "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - last_dt).total_seconds() > 45:
                status = "offline"
        except Exception:
            pass

    return jsonify(
        {
            "status": status,
            "name": row["name"],
            "battery": row["battery"],
            "version": row["version"],
            "last_seen": row["last_seen"],
            # Always the live DEVICE_TOKEN env var - this is what the server
            # actually checks, so the dashboard can never show a stale value.
            "secret_token": Config.DEVICE_TOKEN,
        }
    )


@admin_bp.route("/users", methods=["GET", "POST"])
def admin_users():
    if (err := _require_admin()) is not None:
        return err

    conn = get_db()
    if request.method == "GET":
        rows = conn.execute("SELECT username, name, role FROM users").fetchall()
        conn.close()
        return jsonify({"users": [dict(r) for r in rows]})

    data = request.json or {}
    username = data.get("username", "").strip()
    name = data.get("name", "").strip()
    password = data.get("password", "").strip()

    if not username or not name or not password:
        conn.close()
        return jsonify({"error": "All fields are required"}), 400

    try:
        conn.execute(
            "INSERT INTO users (username, name, password_hash) VALUES (?, ?, ?)",
            (username, name, generate_password_hash(password)),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already exists"}), 400
    finally:
        conn.close()

    return jsonify({"success": True}), 200


@admin_bp.route("/users/<username>", methods=["DELETE"])
def admin_delete_user(username):
    if (err := _require_admin()) is not None:
        return err

    conn = get_db()
    conn.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return jsonify({"success": True}), 200


@admin_bp.route("/messages", methods=["GET"])
def admin_messages():
    if (err := _require_admin()) is not None:
        return err

    conn = get_db()
    rows = conn.execute("SELECT * FROM messages ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify({"messages": [dict(r) for r in rows]})
