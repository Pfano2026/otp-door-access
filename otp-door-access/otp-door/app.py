import os, sqlite3, secrets, hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, session, g, render_template_string, redirect
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-me")
DB_PATH = os.environ.get("DB_PATH", "door.db")
OTP_TTL_SECONDS = 60
MAX_ATTEMPTS = 3


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.executescript(open("schema.sql").read())
        key = os.environ.get("DEVICE_KEY")
        if key:
            c.execute("UPDATE devices SET api_key=? WHERE device_id='door-1'", (key,))


def h(otp):  # hash OTP with server secret
    return hashlib.sha256((app.secret_key + otp).encode()).hexdigest()


def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ---------- Website (mobile-friendly) ----------
PAGE = """
<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>Door OTP</title>
<style>body{font-family:sans-serif;max-width:420px;margin:40px auto;padding:0 16px}
input,button{width:100%;padding:12px;margin:6px 0;font-size:16px}
.otp{font-size:42px;letter-spacing:8px;text-align:center;margin:20px 0}</style>
<h2>Door Access</h2>
{% if not user %}
<form method=post action=/login>
 <input name=username placeholder=Username required>
 <input name=password type=password placeholder=Password required>
 <button>Login</button>
 <button formaction=/register>Register</button>
</form>
{% else %}
<p>Hi {{user}} | <a href=/logout>Logout</a></p>
<button onclick="req()">Request OTP</button>
<div class=otp id=otp>------</div><p id=t></p>
<h4>Recent access</h4><ul>{% for l in logs %}<li>{{l.created_at}} - {{l.result}}</li>{% endfor %}</ul>
<script>
async function req(){
 const r=await fetch('/api/otp/request',{method:'POST'}); const d=await r.json();
 document.getElementById('otp').textContent=d.otp||'error';
 let s=d.expires_in||0; clearInterval(window.i);
 window.i=setInterval(()=>{document.getElementById('t').textContent=s>0?('Expires in '+s+'s'):'Expired'; if(s--<=0)clearInterval(window.i)},1000);
}
</script>
{% endif %}
"""


@app.route("/")
def index():
    logs = []
    if "uid" in session:
        logs = db().execute(
            "SELECT * FROM access_logs WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (session["uid"],)).fetchall()
    return render_template_string(PAGE, user=session.get("name"), logs=logs)


@app.post("/register")
def register():
    u, p = request.form["username"].strip(), request.form["password"]
    try:
        db().execute("INSERT INTO users(username,password_hash) VALUES(?,?)",
                     (u, generate_password_hash(p)))
        db().commit()
    except sqlite3.IntegrityError:
        return "Username taken", 400
    return redirect("/")


@app.post("/login")
def login():
    r = db().execute("SELECT * FROM users WHERE username=?",
                     (request.form["username"].strip(),)).fetchone()
    if r and check_password_hash(r["password_hash"], request.form["password"]):
        session["uid"], session["name"] = r["id"], r["username"]
        return redirect("/")
    return "Invalid login", 401


@app.get("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------- API: mobile app requests an OTP ----------
@app.post("/api/otp/request")
def otp_request():
    if "uid" not in session:
        return jsonify(error="login required"), 401
    device_id = (request.get_json(silent=True) or {}).get("device_id", "door-1")
    otp = f"{secrets.randbelow(10**6):06d}"
    exp = (datetime.utcnow() + timedelta(seconds=OTP_TTL_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
    d = db()
    d.execute("UPDATE otps SET used=1 WHERE user_id=? AND device_id=? AND used=0",
              (session["uid"], device_id))  # invalidate older OTPs
    d.execute("INSERT INTO otps(user_id,device_id,otp_hash,expires_at) VALUES(?,?,?,?)",
              (session["uid"], device_id, h(otp), exp))
    d.commit()
    return jsonify(otp=otp, expires_in=OTP_TTL_SECONDS)


# ---------- API: ESP32 verifies the keypad entry ----------
@app.post("/api/otp/verify")
def otp_verify():
    j = request.get_json(silent=True) or {}
    device_id, otp = j.get("device_id", ""), str(j.get("otp", ""))
    d = db()
    dev = d.execute("SELECT * FROM devices WHERE device_id=?", (device_id,)).fetchone()
    if not dev or not secrets.compare_digest(dev["api_key"], request.headers.get("X-API-Key", "")):
        return jsonify(error="unauthorized"), 401

    row = d.execute("SELECT * FROM otps WHERE device_id=? AND used=0 ORDER BY id DESC LIMIT 1",
                    (device_id,)).fetchone()

    def log(result, uid=None):
        d.execute("INSERT INTO access_logs(device_id,user_id,result) VALUES(?,?,?)",
                  (device_id, uid, result))
        d.commit()

    if not row:
        log("DENIED"); return jsonify(access=False, reason="no_active_otp")
    if row["expires_at"] < now():
        d.execute("UPDATE otps SET used=1 WHERE id=?", (row["id"],)); log("EXPIRED", row["user_id"])
        return jsonify(access=False, reason="expired")
    if row["attempts"] >= MAX_ATTEMPTS:
        d.execute("UPDATE otps SET used=1 WHERE id=?", (row["id"],)); log("LOCKED", row["user_id"])
        return jsonify(access=False, reason="too_many_attempts")
    if h(otp) != row["otp_hash"]:
        d.execute("UPDATE otps SET attempts=attempts+1 WHERE id=?", (row["id"],)); log("DENIED", row["user_id"])
        return jsonify(access=False, reason="wrong_otp")

    d.execute("UPDATE otps SET used=1 WHERE id=?", (row["id"],)); log("GRANTED", row["user_id"])
    return jsonify(access=True)


init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
