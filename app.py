from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from supabase_config import supabase
import secrets
import os
from datetime import datetime, timedelta, timezone
from functools import wraps

app = Flask(__name__)
# Generate a new secret key on each restart to invalidate old sessions
app.secret_key = secrets.token_hex(32)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin786")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_logged_in" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def generate_key(prefix="PRO"):
    random_part = secrets.token_hex(8).upper()
    return f"{prefix}-{random_part}"


# ===== AUTHENTICATION ROUTES =====

@app.route("/")
def root():
    """Redirect to login if not authenticated, otherwise to dashboard"""
    if "admin_logged_in" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("generate"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)
            return redirect(url_for("generate"))
        else:
            return render_template("login.html", error="Invalid Password")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("login"))


# ===== KEY MANAGEMENT ROUTES =====

@app.route("/generate", methods=["GET", "POST"])
@login_required
def generate():
    """Key generation page"""
    message = None
    new_entry = None

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

        try:
            response = supabase.table("keys").insert(data).execute()
            if response.data:
                message = "✅ Key Generated Successfully!"
                new_entry = {
                    "key": new_key,
                    "duration": duration_days,
                }
            else:
                message = "⚠️ Could not save to database."
        except Exception as e:
            message = f"❌ Error: {str(e)}"

    return render_template("generate.html", message=message, last_key=new_entry)


@app.route("/keys")
@login_required
def keys():
    """View all keys with used/unused status"""
    try:
        result = supabase.table("keys").select("*").order("created_at", desc=True).execute()
        keys_data = result.data or []
        
        # Add status for each key
        for key in keys_data:
            key['status'] = 'Used' if key.get('is_used') or key.get('used_by') else 'Unused'
        
        return render_template("keys.html", generated_keys=keys_data)
    except Exception as e:
        return f"Error fetching keys: {str(e)}", 500


@app.route("/delete_key/<uuid:key_id>", methods=["DELETE", "POST"])
@login_required
def delete_key(key_id):
    """Delete a key only if it's unused"""
    try:
        # First check if key is used
        key_response = supabase.table("keys").select("*").eq("id", str(key_id)).execute()
        
        if not key_response.data:
            return jsonify({"status": "error", "message": "Key not found"}), 404
        
        key = key_response.data[0]
        
        # Check if key is used
        if key.get("is_used") or key.get("used_by"):
            return jsonify({"status": "error", "message": "Cannot delete used keys"}), 400
        
        # Delete the key
        response = supabase.table("keys").delete().eq("id", str(key_id)).execute()
        
        if response.data:
            return jsonify({"status": "success", "message": "Key deleted successfully"}), 200
        else:
            return jsonify({"status": "error", "message": "Failed to delete key"}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ===== DASHBOARD ROUTE =====

@app.route("/dashboard")
@login_required
def dashboard():
    """Simplified dashboard showing key stats and user table"""
    try:
        # Fetch keys
        keys_response = supabase.table("keys").select("*").execute()
        keys = keys_response.data or []
        
        # Calculate key stats
        total_keys = len(keys)
        used_keys = sum(1 for k in keys if k.get("is_used") or k.get("used_by"))
        unused_keys = total_keys - used_keys
        
        # Fetch users
        users_response = supabase.table("users").select("*").execute()
        users = users_response.data or []
        
        # Fetch usage data
        usage_free_response = supabase.table("usage_free").select("*").execute()
        usage_free = usage_free_response.data or []
        
        usage_pro_response = supabase.table("usage_pro").select("*").execute()
        usage_pro = usage_pro_response.data or []
        
        # Build user map
        user_map = {}
        
        for user in users:
            uid = user.get("id")
            user_map[uid] = {
                "id": uid,
                "email": user.get("email", "Unknown"),
                "full_name": user.get("full_name", ""),
                "created_at": user.get("created_at"),
                "role": "Free",
                "key": None,
                "key_id": None,
                "pro_start": None,
                "pro_end": None,
                "usage_input": 0,
                "usage_output": 0,
                "ocr_count": 0,
            }
        
        # Map keys to users
        for k in keys:
            user_id = k.get("used_by")
            if user_id and user_id in user_map:
                user_map[user_id]["role"] = "Pro"
                user_map[user_id]["key"] = k.get("key")
                user_map[user_id]["key_id"] = k.get("id")
                user_map[user_id]["pro_start"] = k.get("created_at")
                user_map[user_id]["pro_end"] = k.get("expiry_date")
        
        # Map usage
        for u in usage_free + usage_pro:
            user_id = u.get("user_id")
            if user_id in user_map:
                user_map[user_id]["usage_input"] += u.get("tokens_input_used", 0)
                user_map[user_id]["usage_output"] += u.get("tokens_output_used", 0)
                user_map[user_id]["ocr_count"] += u.get("ocr_count", 0)
        
        processed_users = list(user_map.values())
        processed_users.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        
        # Calculate user stats
        all_time_users = len(users)
        pro_users_count = sum(1 for u in processed_users if u["role"] == "Pro")
        
        # Calculate this month users
        now = datetime.now(timezone.utc)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month_users = 0
        for u in users:
            created_at_str = u.get("created_at")
            if created_at_str:
                try:
                    created_at_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    if created_at_dt >= start_of_month:
                        this_month_users += 1
                except:
                    pass
        
        return render_template(
            "dashboard.html",
            users=processed_users,
            stats={
                "total_keys": total_keys,
                "used_keys": used_keys,
                "unused_keys": unused_keys,
                "all_time_users": all_time_users,
                "pro_users": pro_users_count,
                "this_month_users": this_month_users,
            }
        )
    except Exception as e:
        return f"Error loading dashboard: {str(e)}", 500


# ===== USER MANAGEMENT ROUTES =====

@app.route("/remove_pro/<user_id>", methods=["POST"])
@login_required
def remove_pro(user_id):
    """Remove Pro status from a user, delete their key, and move them to Free tier"""
    try:
        # Find and delete the user's key
        keys_response = supabase.table("keys").select("*").eq("used_by", user_id).execute()
        
        if keys_response.data:
            for key in keys_response.data:
                # Delete the key
                supabase.table("keys").delete().eq("id", key["id"]).execute()
        
        # Delete from usage_pro table
        supabase.table("usage_pro").delete().eq("user_id", user_id).execute()
        
        # Add to usage_free table with 0 usage
        free_data = {
            "user_id": user_id,
            "tokens_input_used": 0,
            "tokens_output_used": 0
        }
        supabase.table("usage_free").insert(free_data).execute()
        
        return jsonify({
            "status": "success",
            "message": "Pro status removed successfully. User moved to Free tier and key deleted."
        }), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ===== STATS PAGE ROUTE =====

@app.route("/stats")
@login_required
def stats():
    """Comprehensive statistics page with charts and trends"""
    try:
        # Fetch all data
        keys_response = supabase.table("keys").select("*").execute()
        keys = keys_response.data or []
        
        users_response = supabase.table("users").select("*").execute()
        users = users_response.data or []
        
        usage_free_response = supabase.table("usage_free").select("*").execute()
        usage_free = usage_free_response.data or []
        
        usage_pro_response = supabase.table("usage_pro").select("*").execute()
        usage_pro = usage_pro_response.data or []
        
        # Calculate key stats
        total_keys = len(keys)
        used_keys = sum(1 for k in keys if k.get("is_used") or k.get("used_by"))
        unused_keys = total_keys - used_keys
        
        # Calculate user stats
        all_time_users = len(users)
        pro_users_count = sum(1 for k in keys if k.get("used_by"))
        
        # Calculate this month users
        now = datetime.now(timezone.utc)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month_users = 0
        for u in users:
            created_at_str = u.get("created_at")
            if created_at_str:
                try:
                    created_at_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    if created_at_dt >= start_of_month:
                        this_month_users += 1
                except:
                    pass
        
        # Calculate monthly user growth (last 6 months)
        monthly_data = {}
        for i in range(6):
            month_date = now - timedelta(days=30 * i)
            month_key = month_date.strftime("%b %Y")
            monthly_data[month_key] = 0
        
        for u in users:
            created_at_str = u.get("created_at")
            if created_at_str:
                try:
                    created_at_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    month_key = created_at_dt.strftime("%b %Y")
                    if month_key in monthly_data:
                        monthly_data[month_key] += 1
                except:
                    pass
        
        # Calculate total token usage
        total_input_tokens = sum(u.get("tokens_input_used", 0) for u in usage_free + usage_pro)
        total_output_tokens = sum(u.get("tokens_output_used", 0) for u in usage_free + usage_pro)
        
        # Calculate total OCR count
        total_ocr_count = sum(u.get("ocr_count", 0) for u in usage_free + usage_pro)
        
        # Calculate this month OCR count
        this_month_ocr_count = 0
        for u in usage_free + usage_pro:
            created_at_str = u.get("created_at")
            if created_at_str:
                try:
                    created_at_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    if created_at_dt >= start_of_month:
                        this_month_ocr_count += u.get("ocr_count", 0)
                except:
                    pass
        
        stats_data = {
            "total_keys": total_keys,
            "used_keys": used_keys,
            "unused_keys": unused_keys,
            "all_time_users": all_time_users,
            "pro_users": pro_users_count,
            "this_month_users": this_month_users,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_ocr_count": total_ocr_count,
            "this_month_ocr_count": this_month_ocr_count,
            "monthly_growth": list(reversed(list(monthly_data.items()))),
        }
        
        return render_template("stats.html", stats=stats_data)
    except Exception as e:
        return f"Error loading stats: {str(e)}", 500


# ===== AUTO EXPIRY CHECKER =====

def check_expired_pro_users():
    """Check for expired Pro users and automatically downgrade them"""
    try:
        now = datetime.now(timezone.utc)
        
        # Fetch all keys
        keys_response = supabase.table("keys").select("*").execute()
        keys = keys_response.data or []
        
        for key in keys:
            if key.get("used_by") and key.get("expiry_date"):
                try:
                    expiry_date = datetime.fromisoformat(key["expiry_date"].replace('Z', '+00:00'))
                    
                    # Check if key has expired
                    if expiry_date <= now:
                        user_id = key['used_by']
                        # Delete the expired key
                        supabase.table("keys").delete().eq("id", key["id"]).execute()
                        # Delete from usage_pro
                        supabase.table("usage_pro").delete().eq("user_id", user_id).execute()
                        # Add to usage_free with 0 usage
                        free_data = {
                            "user_id": user_id,
                            "tokens_input_used": 0,
                            "tokens_output_used": 0
                        }
                        supabase.table("usage_free").insert(free_data).execute()
                        print(f"Removed expired Pro key for user: {user_id}")
                except Exception as e:
                    print(f"Error processing key {key.get('id')}: {str(e)}")
                    
    except Exception as e:
        print(f"Error checking expired Pro users: {str(e)}")


if __name__ == "__main__":
    # Run expiry check before starting the app
    check_expired_pro_users()
    app.run(debug=True)
