from supabase_config import supabase
import json

def inspect_db():
    print("--- Keys Table ---")
    try:
        response = supabase.table("keys").select("*").limit(1).execute()
        if response.data:
            print(json.dumps(response.data[0], indent=2))
        else:
            print("No data in keys table.")
    except Exception as e:
        print(f"Error fetching keys: {e}")

    print("\n--- Users Table (Guessing) ---")
    try:
        response = supabase.table("users").select("*").limit(1).execute()
        if response.data:
            print(json.dumps(response.data[0], indent=2))
        else:
            print("No data in users table or table does not exist.")
    except Exception as e:
        print(f"Error fetching users: {e}")

    print("\n--- User Usage / Stats (Guessing) ---")
    try:
        response = supabase.table("user_usage").select("*").limit(1).execute()
        if response.data:
            print(json.dumps(response.data[0], indent=2))
        else:
             print("No data in user_usage table or table does not exist.")
    except Exception as e:
        print(f"Error fetching user_usage: {e}")

if __name__ == "__main__":
    inspect_db()
