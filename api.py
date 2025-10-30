from flask import Flask, jsonify, request
from supabase import create_client, Client
import secrets
from datetime import datetime, timedelta, timezone
import os

app = Flask(__name__)

# Initialize Supabase client
supabase: Client = create_client(
    os.environ.get('SUPABASE_URL'),
    os.environ.get('SUPABASE_KEY')
)

def generate_key(prefix="PRO"):
    random_part = secrets.token_hex(8).upper()
    return f"{prefix}-{random_part}"

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "supabase_url": os.environ.get('SUPABASE_URL', 'not_set'),
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/generate", methods=["POST"])
def generate():
    try:
        duration_days = int(request.json.get("duration", 30))
        new_key = generate_key()
        expiry_date = datetime.now(timezone.utc) + timedelta(days=duration_days)

        data = {
            "key": new_key,
            "is_used": False,
            "duration_days": duration_days,
            "expiry_date": expiry_date.isoformat(),
        }

        response = supabase.table("keys").insert(data).execute()
        if response.data:
            return jsonify({
                "status": "success",
                "message": "✅ Key Generated Successfully!",
                "key": new_key,
                "duration": duration_days,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Could not save to database"
            }), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/keys", methods=["GET"])
def list_keys():
    try:
        result = supabase.table("keys").select("*").order("created_at", desc=True).execute()
        return jsonify({"status": "success", "keys": result.data or []})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/delete_key/<uuid:key_id>", methods=["DELETE"])
def delete_key(key_id):
    try:
        response = supabase.table("keys").delete().eq("id", str(key_id)).execute()
        if response.data:
            return jsonify({"status": "success", "message": "Key deleted successfully"})
        else:
            return jsonify({"status": "error", "message": "Key not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500