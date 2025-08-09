import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
import os
from flask import Flask, render_template, request, jsonify,session,redirect
from collections import deque
from datetime import datetime, timedelta
from twilio.rest import Client
import logging
import threading
import json
import time
import qrcode
import base64
import io
from io import BytesIO
from pyzbar.pyzbar import decode
from PIL import Image
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback_secret_key')
CORS(app)

@app.route('/staff')
def staff():
    return render_template('staff.html')
import sqlite3

DB_PATH = "waitlist.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS waitlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            party_size INTEGER,
            join_time TEXT,
            wait_time REAL,
            position INTEGER,
            notified INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Waiting'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))


waitlist = deque()

available_tables = [1, 2, 3, 4, 5, 6] 
assigned_tables = {} 

def calculate_wait_time(position):
    average_time_per_table = 1 # minutes per table
    return position * average_time_per_table

import sqlite3

def check_waitlist():
    while True:
        try:
            conn = sqlite3.connect("waitlist.db")
            cursor = conn.cursor()

            # ✅ Select only the required 8 columns
            cursor.execute("""
                SELECT id, name, email, party_size, join_time, wait_time, position, notified 
                FROM waitlist WHERE notified = 0
            """)
            rows = cursor.fetchall()

            for row in rows:
                id, name, email, party_size, join_time_str, wait_time, position, notified = row
                join_time = datetime.strptime(join_time_str, '%Y-%m-%d %H:%M:%S')
                if datetime.now() >= join_time + timedelta(minutes=wait_time):
                    customer = {
                        'name': name,
                        'email': email,
                        'party_size': party_size,
                        'join_time': join_time_str,
                        'wait_time': wait_time,
                        'position': position
                    }

                    

                    # ✅ Mark as notified (moved here so it's only done after notification)
                    cursor.execute("UPDATE waitlist SET notified = 1 WHERE id = ?", (id,))
                    conn.commit()

                    notify_customer(customer)

            conn.close()

        except Exception as e:
            logging.error(f"[❌ check_waitlist error]: {e}")

        time.sleep(5)
@app.route('/staff/info')
def staff_info():
    return jsonify({"message": "Info page"})
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/menu')
def menu():
    return render_template('menu.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/waitlist', methods=['POST'])
def join_waitlist():
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        party_size = data.get('party_size')

        if not name or not email or not party_size:
            return jsonify({'message': 'Missing information'}), 400

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Check if already exists
        c.execute("SELECT * FROM waitlist WHERE name=? OR email=?", (name, email))
        if c.fetchone():
            conn.close()
            return jsonify({'message': 'Already in waitlist'}), 409

        # Calculate position and wait time
        c.execute("SELECT COUNT(*) FROM waitlist")
        position = c.fetchone()[0] + 1
        wait_time = calculate_wait_time(position)  # You already have this function

        join_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # ✅ Add estimated ready time
        estimated_ready_time = datetime.now() + timedelta(minutes=wait_time)
        estimated_ready_time_str = estimated_ready_time.strftime('%Y-%m-%d %H:%M:%S')

        # Insert into DB
        c.execute('''
            INSERT INTO waitlist (name, email, party_size, join_time, wait_time, position)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, email, party_size, join_time, wait_time, position))

        conn.commit()
        conn.close()

        # ✅ Include estimated_ready_time in the response
        return jsonify({
            'message': 'Added to waitlist',
            'position': position,
            'name': name,
            'wait_time': wait_time,
            'estimated_ready_time': estimated_ready_time_str
        })

    except Exception as e:
        logging.error(f"Error in join_waitlist: {str(e)}")
        return jsonify({'message': str(e)}), 500


@app.route('/force_notify', methods=['POST'])
def force_notify():
    data = request.json
    name = data.get('name')

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM waitlist WHERE name=? AND notified=0", (name,))
    row = c.fetchone()

    if not row:
        return jsonify({'message': 'Already notified or not found'}), 404

    id, name, email, party_size, join_time, wait_time, position, notified = row
    customer = {
        "name": name,
        "email": email,
        "party_size": party_size,
        "wait_time": wait_time,
        "position": position
    }

    # This will not run if already notified (checked above)
    notify_customer(customer)

    # Mark as notified
    c.execute("UPDATE waitlist SET notified=1 WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Notification sent'}), 200


@app.route('/cancel_waitlist', methods=['POST'])
def cancel_waitlist():
    try:
        data = request.json
        name = data['name']
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM waitlist WHERE name = ?", (name,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Waitlist cancelled'}), 200
    except Exception as e:
        logging.error(f"Error cancelling waitlist: {str(e)}")
        return jsonify({'message': 'Error cancelling waitlist'}), 500


def notify_customer(customer):
    try:
        # ✅ Check if 'email' key exists (safe guard)
        if 'email' not in customer:
            logging.error("[❌ notify_customer] Missing email in customer data")
            return

        # Generate QR code
        qr_data = json.dumps({
            "name": customer['name'],
            "email": customer['email'],
            "party_size": customer.get('party_size', 'N/A'),
            "join_time": customer.get('join_time', 'N/A'),
            "wait_time": customer['wait_time']
        })
        qr = qrcode.make(qr_data)
        resized_qr = qr.resize((150, 150))
        img_byte_arr = io.BytesIO()
        resized_qr.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        img_data = img_byte_arr.read()

        msg = EmailMessage()
        msg['Subject'] = "✅ Your Table is Ready at Kasata Restaurant!"
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = customer['email']

        # ✅ Add only HTML alternative (no plain text)
        msg.add_alternative(f"""\
        <html>
          <body>
            <p>Hello <strong>{customer['name']}</strong>,</p>
            <p>Your table is ready! Please arrive within <strong>10 minutes</strong> at <strong>Kasata Restaurant</strong>.</p>
            <p>Here is your QR Code for entry:</p>
            <img src="cid:qrcode_cid" width="150" height="150" alt="QR Code">
            <p>Thank you for waiting!</p>
            <p><em>— Kasata Restaurant Team</em></p>
          </body>
        </html>
        """, subtype='html')

        msg.get_payload()[0].add_related(img_data, 'image', 'png', cid='qrcode_cid')

        # ✅ Send the email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
            logging.info(f"✅ Email successfully sent to {customer['email']}")

    except Exception as e:
        logging.error(f"❌ Error sending email: {str(e)}")

# Flask route example
@app.route("/waitlist")
def waitlist_page():
    name = request.args.get("name")

    # fallback to localStorage-like session check if needed (advanced: skip for now)
    if not name:
        return "Missing name in query string", 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT position, join_time, wait_time FROM waitlist WHERE name=?", (name,))
    row = c.fetchone()
    conn.close()

    if not row:
        return "User not found", 404

    position, join_time_str, wait_time = row
    join_time = datetime.strptime(join_time_str, "%Y-%m-%d %H:%M:%S")
    ready_time = join_time + timedelta(minutes=wait_time)
    remaining = max(int((ready_time - datetime.now()).total_seconds()), 0)

    return render_template("waitlist.html", name=name, position=position, wait_time=remaining)


# Start background thread
background_thread = threading.Thread(target=check_waitlist)
background_thread.daemon = True
background_thread.start()

@app.route("/check_user", methods=["POST"])
def check_user():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")

    conn = sqlite3.connect("waitlist.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM waitlist WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return jsonify({"status": row[4]})  # status is in column index 4
    else:
        return jsonify({"status": "Not found"})

@app.route("/assign_table", methods=["POST"])
def assign_table():
    data = request.get_json()
    email = data.get("email")

    conn = sqlite3.connect("waitlist.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM waitlist WHERE email = ?", (email,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Email not found"}), 404

    cursor.execute("UPDATE waitlist SET status = ? WHERE email = ?", ("Assigned", email))
    conn.commit()
    conn.close()

    return jsonify({"message": "Table assigned successfully!"})

@app.route("/get_status", methods=["GET"])
def get_status():
    email = request.args.get("email")
    try:
        conn = sqlite3.connect("waitlist.db")
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM waitlist WHERE email=?", (email,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return jsonify({"status": result[0]})
        else:
            return jsonify({"status": "Not Found"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/scan_qr', methods=['POST'])
def scan_qr():
    data = request.get_json()
    name = data['name']
    email = data['email']
    party_size = data['party_size']
    join_time = data['join_time']
    wait_time = data['wait_time']

    conn = sqlite3.connect('waitlist.db')
    c = conn.cursor()

    c.execute('''SELECT status FROM waitlist WHERE name=? AND email=? AND join_time=?''',
              (name, email, join_time))
    result = c.fetchone()

    if result:
        current_status = result[0]
        if current_status != 'assigned':
            c.execute('''UPDATE waitlist SET status=? WHERE name=? AND email=? AND join_time=?''',
                      ('assigned', name, email, join_time))
            conn.commit()
        conn.close()
        return jsonify({"message": "Status updated to assigned", "status": "assigned"})
    else:
        conn.close()
        return jsonify({"message": "User not found", "status": "not_found"}), 404



@app.route('/update_status', methods=['POST'])
def update_status():
    data = request.get_json()
    print(f"[DEBUG] Received data for update_status: {data}")
    email = data.get('email')
    name = data.get('name')
    party_size = data.get('party_size')
    join_time = data.get('join_time')

    if not email:
        return jsonify({'error': 'Missing email'}), 400

    # Find or assign a table
    if available_tables:
        assigned_table = available_tables.pop(0)
        assigned_tables[email] = assigned_table
        return jsonify({
            'message': f'Table {assigned_table} assigned ',
            'assigned_table': assigned_table
        })
    else:
        return jsonify({'error': 'No tables available'}), 503


@app.route('/add_to_waitlist', methods=['POST'])
def add_to_waitlist():
    data = request.json
    email = data.get("email")

    conn = sqlite3.connect("waitlist.db")
    cursor = conn.cursor()

    # Check if already exists
    cursor.execute("SELECT * FROM waitlist WHERE email=?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"message": "Already in waitlist"}), 200

    # Insert into waitlist
    cursor.execute("""
        INSERT INTO waitlist (name, email, party_size, join_time, wait_time, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data["name"],
        data["email"],
        data["party_size"],
        data["join_time"],
        data["wait_time"],
        "Waiting"  # default status
    ))
    conn.commit()
    conn.close()

    return jsonify({"message": "Added to waitlist"}), 201
@app.route('/check_status')
def check_status():
    email = request.args.get('email')

    conn = sqlite3.connect("waitlist.db")
    c = conn.cursor()
    c.execute("SELECT status FROM waitlist WHERE email = ?", (email,))
    result = c.fetchone()
    conn.close()

    if result:
        return jsonify({"status": result[0]})
    else:
        return jsonify({"status": "Not Found"}), 404


STAFF_CREDENTIALS = {
    "staff1": "pass123",
    "staff2": "pass456"
}

@app.route('/staff-login', methods=['GET', 'POST'])
def staff_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in STAFF_CREDENTIALS and STAFF_CREDENTIALS[username] == password:
            session['staff_logged_in'] = True
            return redirect('/staff')  # Redirect to scanner page
        else:
            return "Invalid credentials"
    return render_template('stafflogin.html')

@app.route('/scanner')
def scanner():
    if not session.get('staff_logged_in'):
        return redirect('/staff-login')
    return render_template('index.html')
@app.route('/get_customer_info')
def get_customer_info():
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'Missing email'}), 400

    conn = sqlite3.connect('waitlist.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, party_size, join_time, wait_time, status FROM waitlist WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return jsonify({
            'name': row[0],
            'party_size': row[1],
            'join_time': row[2],
            'wait_time': row[3],
            'status': row[4]
        })
    else:
        return jsonify({'error': 'Customer not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)
