"""
diagnose.py — run this on your PC BEFORE starting Flask.

    python diagnose.py

It checks every layer:
  1. Required Python packages installed
  2. MySQL server is reachable
  3. Login credentials are correct
  4. The quizdatabase database exists
  5. All required tables exist
  6. Your PC's local IP (to paste into api_service.dart)
"""

import sys
import socket

REQUIRED = ["flask", "flask_sqlalchemy", "flask_jwt_extended",
            "flask_cors", "pymysql", "bcrypt", "dotenv"]

# ── 1. Packages ───────────────────────────────────────────────────────────────
print("\n─────────────────────────────────────────")
print("  Cerebro Metron — Connection Diagnostics")
print("─────────────────────────────────────────\n")

print("[1] Checking Python packages...")
missing = []
for pkg in REQUIRED:
    try:
        __import__(pkg)
        print(f"    ✓  {pkg}")
    except ImportError:
        print(f"    ✗  {pkg}  ← MISSING")
        missing.append(pkg)

if missing:
    print(f"\n  Install missing packages:")
    print(f"  pip install {' '.join(missing)}\n")
    sys.exit(1)

# ── 2. Load config ────────────────────────────────────────────────────────────
print("\n[2] Loading config...")
try:
    from dotenv import load_dotenv
    load_dotenv()
    import os

    DB_USER = os.getenv("DB_USER", "root")
    DB_PASS = os.getenv("DB_PASS", "12345")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "quizdatabase")

    # Also read full URL if set
    full_url = os.getenv("DATABASE_URL", "")
    if full_url:
        print(f"    DATABASE_URL env var found: {full_url[:40]}...")
    else:
        print(f"    Using defaults → {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
        print(f"    Password: {'*' * len(DB_PASS)}")
except Exception as e:
    print(f"    ✗  Config error: {e}")
    sys.exit(1)

# ── 3. TCP connection to MySQL port ───────────────────────────────────────────
print(f"\n[3] Checking TCP connection to {DB_HOST}:{DB_PORT}...")
try:
    sock = socket.create_connection((DB_HOST, DB_PORT), timeout=5)
    sock.close()
    print(f"    ✓  Port {DB_PORT} is open on {DB_HOST}")
except (socket.timeout, ConnectionRefusedError, OSError) as e:
    print(f"    ✗  Cannot reach MySQL at {DB_HOST}:{DB_PORT}")
    print(f"       Error: {e}")
    print(f"\n  FIX: Make sure MySQL is running.")
    print(f"    Windows: open Services → find 'MySQL80' or 'MySQL' → Start")
    print(f"    Or run:  net start mysql\n")
    sys.exit(1)

# ── 4. Login credentials ──────────────────────────────────────────────────────
print(f"\n[4] Testing credentials for user '{DB_USER}'...")
try:
    import pymysql
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT,
                           user=DB_USER, password=DB_PASS,
                           connect_timeout=5)
    conn.close()
    print(f"    ✓  Login successful")
except pymysql.err.OperationalError as e:
    code, msg = e.args
    print(f"    ✗  Login failed: {msg}")
    if code == 1045:
        print(f"\n  FIX: Wrong username or password.")
        print(f"  Open config.py and change the DATABASE_URL to match your MySQL credentials.")
        print(f"  Example: mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/quizdatabase\n")
    sys.exit(1)

# ── 5. Database exists ────────────────────────────────────────────────────────
print(f"\n[5] Checking database '{DB_NAME}' exists...")
try:
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT,
                           user=DB_USER, password=DB_PASS,
                           database=DB_NAME, connect_timeout=5)
    print(f"    ✓  Database '{DB_NAME}' exists")
except pymysql.err.OperationalError as e:
    code, msg = e.args
    print(f"    ✗  {msg}")
    if code == 1049:
        print(f"\n  FIX: Run the schema SQL script to create the database.")
        print(f"  Open MySQL Workbench or run:")
        print(f"    mysql -u {DB_USER} -p < schema.sql\n")
    sys.exit(1)

# ── 6. Tables exist ───────────────────────────────────────────────────────────
print(f"\n[6] Checking required tables...")
REQUIRED_TABLES = ["users", "classroom", "classroom_students",
                   "quiz", "question", "choice", "attempt", "answer"]
cursor = conn.cursor()
cursor.execute("SHOW TABLES")
existing = {row[0] for row in cursor.fetchall()}

all_ok = True
for table in REQUIRED_TABLES:
    if table in existing:
        print(f"    ✓  {table}")
    else:
        print(f"    ✗  {table}  ← MISSING")
        all_ok = False

conn.close()

if not all_ok:
    print(f"\n  FIX: Some tables are missing. Re-run the schema SQL script.")
    print(f"    mysql -u {DB_USER} -p < schema.sql\n")
    sys.exit(1)

# ── 7. Local IP ───────────────────────────────────────────────────────────────
print(f"\n[7] Your PC's local IP addresses (for api_service.dart):")
try:
    hostname = socket.gethostname()
    ips = socket.getaddrinfo(hostname, None)
    seen = set()
    for ip in ips:
        addr = ip[4][0]
        if addr.startswith("192.168.") or addr.startswith("10.") or addr.startswith("172."):
            if addr not in seen:
                seen.add(addr)
                print(f"    →  {addr}  ← use this in api_service.dart")
    if not seen:
        # fallback
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        print(f"    →  {s.getsockname()[0]}  ← use this in api_service.dart")
        s.close()
except Exception:
    print("    Could not determine local IP automatically.")
    print("    Run: ipconfig (Windows) or ifconfig (Mac/Linux)")

# ── Done ──────────────────────────────────────────────────────────────────────
print(f"""
─────────────────────────────────────────
  ✓  All checks passed!
─────────────────────────────────────────

  Next steps:
  1. Copy the IP above into api_service.dart:
         static const String _pcIp = 'YOUR_IP_HERE';

  2. Start Flask:
         python app.py

  3. Make sure your phone is on the same Wi-Fi network.

  Windows Firewall — allow port 5000 (run as Administrator):
    netsh advfirewall firewall add rule name="Flask5000" ^
      dir=in action=allow protocol=TCP localport=5000
""")