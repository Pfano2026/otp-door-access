# OTP-Based Door Access (ESP32 + Servo)

Flow: **request** (website/app) -> **wait** (user types OTP on keypad) -> **verify** (ESP32 calls server) -> **action** (servo opens door).

## Files
- `schema.sql`  - database tables (users, devices, otps, access_logs)
- `app.py`      - Flask website + API (OTP expires in 60 s, 3 attempts, one-time use)
- `render.yaml` - Render deployment config
- `firmware/otp_door/otp_door.ino` - ESP32 code

## Wiring
Servo signal -> GPIO18 (power from 5V, common GND) | Buzzer -> GPIO19
OLED SDA -> 21, SCL -> 22 | Keypad rows 13,12,14,27 / cols 26,25,33,32

## Run locally
    pip install -r requirements.txt
    python app.py

## GitHub
    git init
    git add .
    git commit -m "OTP door access"
    git branch -M main
    git remote add origin https://github.com/YOUR_USER/otp-door-access.git
    git push -u origin main

## Render
1. render.com -> New -> Web Service -> connect the GitHub repo
2. Build: `pip install -r requirements.txt`  Start: `gunicorn app:app`
3. Environment: `SECRET_KEY` (random), `DEVICE_KEY` (same as API_KEY in the ESP32)
4. Put your `https://xxx.onrender.com` URL in the firmware's VERIFY_URL

Note: Render's free tier wipes the SQLite file on redeploy/restart. For a persistent database
use a Render Postgres instance or a persistent disk.
