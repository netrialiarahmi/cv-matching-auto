from dotenv import load_dotenv
import os, json, base64

load_dotenv('.env')

kaid = os.getenv("KAID", "").strip().strip('"')
kb = os.getenv("KB", "").strip().strip('"')

print(f"KAID: {kaid[:15]}..." if kaid else "KAID: MISSING")
print(f"KB: {kb[:30]}..." if kb else "KB: MISSING")

if kb:
    try:
        payload = kb.split('.')[1]
        payload += '=' * (4 - len(payload) % 4)
        decoded = json.loads(base64.b64decode(payload))
        expiry = decoded.get("expiry_date", "unknown")
        print(f"KB expiry: {expiry}")
        from datetime import datetime
        exp_dt = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        if exp_dt > now:
            print(f"Status: VALID ({(exp_dt - now).days} days remaining)")
        else:
            print("Status: EXPIRED")
    except Exception as e:
        print(f"Could not decode JWT: {e}")
