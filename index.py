from flask import Flask, jsonify, request
from supabase import create_client
import secrets
from datetime import datetime, timedelta, timezone
import os

app = Flask(__name__)

# Initialize Supabase directly
supabase = create_client(
    supabase_url=os.environ.get('SUPABASE_URL'),
    supabase_key=os.environ.get('SUPABASE_KEY')
)

@app.route("/api/test")
def test():
    return jsonify({"status": "ok"})

@app.route("/api/generate", methods=['POST'])
def generate():
    try:
        duration_days = int(request.json.get('duration', 30))
        key = f"PRO-{secrets.token_hex(8).upper()}"
        expiry_date = datetime.now(timezone.utc) + timedelta(days=duration_days)
        
        data = {
            "key": key,
            "is_used": False,
            "duration_days": duration_days,
            "expiry_date": expiry_date.isoformat()
        }
        
        result = supabase.table("keys").insert(data).execute()
        return jsonify({
            "success": True,
            "key": key,
            "expiry_date": expiry_date.isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/keys")
def list_keys():
    try:
        result = supabase.table("keys").select("*").execute()
        return jsonify({"keys": result.data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500