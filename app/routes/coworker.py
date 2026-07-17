import time
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from ..db import get_db
from ..security import verify_coworker_password, generate_token, verify_token, get_bearer_token
from ..config import Config
from ..extensions import limiter

coworker_bp = Blueprint("coworker", __name__, url_prefix="/api")


def _require_coworker():
    token = get_bearer_token(request)
    username = verify_token(token)
    if not username:
        return None, (jsonify({"error": "Unauthorized"}), 401)
    return username, None


@coworker_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute; 30 per hour")
def coworker_login():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")

    user = verify_coworker_password(username, password or "")
    if user:
        token = generate_token(username)
        return (
            jsonify(
                {
                    "token": token,
                    "username": user["username"],
                    "name": user["name"],
                    "my_number": Config.MY_NUMBER,
                }
            ),
            200,
        )
    return jsonify({"error": "Invalid user credentials"}), 401


@coworker_bp.route("/numbers", methods=["GET"])
def coworker_get_numbers():
    username, err = _require_coworker()
    if err:
        return err

    conn = get_db()
    user_row = conn.execute("SELECT allowed_numbers FROM users WHERE username = ?", (username,)).fetchone()
    if not user_row:
        conn.close()
        return jsonify({"numbers": []}), 200

    allowed = user_row["allowed_numbers"] or "*"
    
    # Fetch all gateway numbers
    rows = conn.execute("SELECT phone_number, operator_name FROM gateway_numbers ORDER BY timestamp DESC").fetchall()
    conn.close()

    numbers = []
    for r in rows:
        phone = r["phone_number"]
        operator = r["operator_name"]
        
        # Filter if allowed_numbers is not '*'
        if allowed == "*" or phone in allowed.split(","):
            numbers.append({
                "phone_number": phone,
                "operator_name": operator
            })

    return jsonify({"numbers": numbers}), 200


@coworker_bp.route("/inbox", methods=["GET"])
def coworker_inbox():
    username, err = _require_coworker()
    if err:
        return err

    conn = get_db()
    # Only this coworker's own sent messages and replies routed to them -
    # coworkers should never see each other's conversations.
    rows = conn.execute(
        "SELECT * FROM messages WHERE owner = ? ORDER BY time DESC, id DESC LIMIT 200",
        (username,),
    ).fetchall()
    conn.close()
    return jsonify({"messages": [dict(r) for r in rows]})


@coworker_bp.route("/send", methods=["POST"])
def coworker_send_sms():
    username, err = _require_coworker()
    if err:
        return err

    data = request.json or {}
    to = data.get("to")
    text = data.get("text")
    sim_operator = data.get("sim_operator", "").strip()

    if not to or not text:
        return jsonify({"error": "Receiver and message are required"}), 400

    conn = get_db()
    
    # Confirm user existence
    user_row = conn.execute("SELECT username, allowed_numbers FROM users WHERE username = ?", (username,)).fetchone()
    if not user_row:
        conn.close()
        return jsonify({"error": "User profile not found"}), 404

    allowed = user_row["allowed_numbers"] or "*"

    if sim_operator == "ALL_OPERATORS":
        # Fetch all gateway numbers
        rows = conn.execute("SELECT phone_number, operator_name FROM gateway_numbers").fetchall()
        
        # Filter matching operators
        operators_to_send = []
        for r in rows:
            phone = r["phone_number"]
            operator = r["operator_name"]
            if allowed == "*" or phone in allowed.split(","):
                operators_to_send.append(operator)
        
        if not operators_to_send:
            operators_to_send = [""]
        
        inserted_ids = []
        base_time = int(time.time() * 1000)
        time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        
        for idx, op in enumerate(operators_to_send):
            msg_id = f"MSG-{base_time}-{idx}"
            conn.execute(
                """
                INSERT INTO messages (id, direction, sender, recipient, text, time, status, owner, sim_operator)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (msg_id, "out", username, to, text, time_str, "queued", username, op),
            )
            inserted_ids.append(msg_id)
        
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message_id": inserted_ids[0]}), 200
    else:
        msg_id = f"MSG-{int(time.time() * 1000)}"
        time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            """
            INSERT INTO messages (id, direction, sender, recipient, text, time, status, owner, sim_operator)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (msg_id, "out", username, to, text, time_str, "queued", username, sim_operator),
        )
        conn.commit()
        conn.close()

        return jsonify({"success": True, "message_id": msg_id}), 200
