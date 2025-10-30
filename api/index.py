from flask import Flask, render_template, request, session, jsonify
from supabase_config import supabase
import secrets
from datetime import datetime, timedelta, timezone
import os
from flask_cors import CORS

# Set the template and static folders relative to the api directory
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY', 'a-very-secure-random-secret-key')

def generate_key(prefix="PRO"):
    random_part = secrets.token_hex(8).upper()
    return f"{prefix}-{random_part}"

@app.route("/", methods=["GET", "POST"])
def index():
    try:
        if request.method == "POST":
            duration_days = int(request.form.get("duration", 30))
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

        return render_template("index.html")
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/keys")
def keys():
    try:
        result = supabase.table("keys").select("*").order("created_at", desc=True).execute()
        generated_keys = result.data or []
        return render_template("keys.html", generated_keys=generated_keys)
    except Exception as e:
        return f"Error fetching keys: {str(e)}", 500

@app.route("/delete_key/<uuid:key_id>", methods=["DELETE", "POST"])
def delete_key(key_id):
    try:
        response = supabase.table("keys").delete().eq("id", str(key_id)).execute()
        if response.data:
            return jsonify({"status": "success", "message": "Key deleted successfully"}), 200
        else:
            return jsonify({"status": "error", "message": "Key not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500