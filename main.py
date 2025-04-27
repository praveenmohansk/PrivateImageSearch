from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import cv2
import numpy as np
import pickle
import sqlite3
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'secret123'

# ================================
# Setup database path and connect
# ================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'users.db')

try:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT, password TEXT)''')
    conn.commit()
except Exception as e:
    print("❌ Database Error:", e)

# ================================
# Create folders if they don't exist
# ================================
os.makedirs('static/uploads', exist_ok=True)
os.makedirs('user_indexes', exist_ok=True)

# ================================
# Feature extractor using OpenCV
# ================================
def extract_feature(image_path):
    image = cv2.imread(image_path)
    image = cv2.resize(image, (128, 128))
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None,
                        [8, 8, 8], [0, 180, 0, 256, 0, 256])
    cv2.normalize(hist, hist)
    return hist.flatten().astype(np.int32)

# ================================
# Encryption (simple obfuscation)
# ================================
SECRET_KEY = 42

def encrypt_feature(feature):
    return ((feature + SECRET_KEY) % 256).astype(np.uint8)

def decrypt_feature(encrypted):
    return ((encrypted.astype(np.int32) - SECRET_KEY + 256) % 256).astype(np.uint8)

# ================================
# Load & Save Encrypted Index
# ================================
def load_index(username):
    file_path = f'user_indexes/{username}_index.pkl'
    if os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            return pickle.load(f)
    return {}

def save_index(index, username):
    with open(f'user_indexes/{username}_index.pkl', 'wb') as f:
        pickle.dump(index, f)

def find_closest_match(query_feature, encrypted_index):
    best_match = None
    min_distance = float('inf')
    for name, encrypted in encrypted_index.items():
        decrypted = decrypt_feature(encrypted)
        distance = np.linalg.norm(query_feature - decrypted)
        if distance < min_distance:
            min_distance = distance
            best_match = name
    return best_match

# ================================
# Routes
# ================================
@app.route('/')
def home():

    if 'username' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    if user:
        session['username'] = username
        return redirect(url_for('index'))
    flash("Invalid username or password")
    return redirect(url_for('home'))
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        # You can add email or reset logic here
        flash("🔐 Password reset link sent to your email (demo).")
        return redirect(url_for('home'))
    return render_template('forgot_password.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        c.execute("INSERT INTO users VALUES (?, ?)", (username, password))
        conn.commit()
        flash("Registration successful. Please login.")
        return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

@app.route('/index', methods=['GET', 'POST'])
def index():
    if 'username' not in session:
        return redirect(url_for('home'))
    username = session['username']
    if request.method == 'POST':
        file = request.files['image']
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join('static/uploads', filename)
            file.save(filepath)

            feature = extract_feature(filepath)
            encrypted_index = load_index(username)
            result = find_closest_match(feature, encrypted_index)

            return render_template('result.html', uploaded_img=filename, result_img=result)
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'username' not in session:
        return redirect(url_for('home'))
    username = session['username']
    file = request.files['image']
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join('static/uploads', filename)
        file.save(filepath)

        feature = extract_feature(filepath)
        encrypted = encrypt_feature(feature)

        index = load_index(username)
        index[filename] = encrypted
        save_index(index, username)

        flash("✅ Image encrypted and saved successfully.")
    return redirect(url_for('index'))

@app.route('/reset')
def reset():
    if 'username' not in session:
        return redirect(url_for('home'))
    username = session['username']
    file_path = f'user_indexes/{username}_index.pkl'
    if os.path.exists(file_path):
        os.remove(file_path)
    flash("🔁 Your encrypted image index has been reset.")
    return redirect(url_for('index'))

# ================================
# Run the Flask App
# ================================
if __name__ == '__main__':
    app.run(debug=True)
