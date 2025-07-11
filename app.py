from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import mysql.connector
import os
import hashlib
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import jwt
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Flask App Initialization ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your_super_secret_key_here')
CORS(app, resources={r"/*": {"origins": "*"}})

# --- SocketIO Initialization ---
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Database Configuration ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'student_wellbeing'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"ERROR: Failed to connect to MySQL database: {err}")
        return None

# --- Signup Route ---
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'student')  # Default to student if not provided
    if not email or not password:
        return jsonify(success=False, message="Email and password are required."), 400
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed."), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify(success=False, message="User already exists."), 409
        hashed_password = generate_password_hash(password)
        cursor.execute("INSERT INTO users (email, password, role) VALUES (%s, %s, %s)", (email, hashed_password, role))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify(success=True, message="Signup successful!"), 201
    except Exception as e:
        print("Error during signup:", e)
        return jsonify(success=False, message="Server error during signup."), 500

# --- Login Route ---
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'student')  # Default to student if not provided
    if not email or not password or not role:
        return jsonify(success=False, message="Email, password, and role are required."), 400
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed."), 500
        cursor = conn.cursor(dictionary=True)
        if role == 'student':
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            dashboard_url = 'dashboard.html'
        elif role == 'mentor':
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            dashboard_url = 'mentor_dashboard.html'
        elif role == 'therapist':
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            dashboard_url = 'therapist_dashboard.html'
        else:
            cursor.close()
            conn.close()
            return jsonify(success=False, message="Invalid role."), 400
        cursor.close()
        conn.close()
        if user and check_password_hash(user['password'], password):
            return jsonify(success=True, message="Login successful.", dashboard_url=dashboard_url, role=role), 200
        else:
            return jsonify(success=False, message="Invalid credentials."), 401
    except Exception as e:
        print("Error during login:", e)
        return jsonify(success=False, message="Server error during login."), 500

# --- Therapists Route ---
@app.route('/therapists', methods=['GET'])
def get_therapists():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed."), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name, specialty, bio, email, phone, profile_picture_url FROM therapists ORDER BY name ASC")
        therapists = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(success=True, therapists=therapists), 200
    except Exception as e:
        print("Error fetching therapists:", e)
        return jsonify(success=False, message="Database error fetching therapists."), 500

# --- Mentors Listing Route ---
@app.route('/mentors', methods=['GET'])
def get_mentors():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed.", mentors=[]), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT mentor_id, name, email, expertise, bio, is_verified, created_at FROM mentors ORDER BY name ASC")
        mentors = cursor.fetchall()
        # Add availability field for frontend compatibility
        for mentor in mentors:
            mentor['availability'] = 'Available' if mentor.get('is_verified') else 'Unavailable'
        cursor.close()
        conn.close()
        return jsonify(success=True, mentors=mentors), 200
    except Exception as e:
        print("Error fetching mentors:", e)
        return jsonify(success=False, message="Database error fetching mentors.", mentors=[]), 500

# --- Health Check Endpoint ---
@app.route('/health', methods=['GET'])
def health_check():
    try:
        conn = get_db_connection()
        if conn:
            conn.ping(reconnect=True)
            conn.close()
            return jsonify(status="healthy", database="connected", timestamp=datetime.datetime.now().isoformat()), 200
        return jsonify(status="unhealthy", database="disconnected"), 500
    except Exception as e:
        return jsonify(status="unhealthy", error=str(e)), 500

# --- Dashboard Data Route ---
@app.route('/dashboard_data', methods=['GET'])
def dashboard_data():
    user_email = request.args.get('user_email')
    if not user_email:
        return jsonify(success=False, message="User email is required.", data={}), 400
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed.", data={}), 500
        cursor = conn.cursor(dictionary=True)

        # Get latest mood (assuming a 'mood_logs' table with 'user_email', 'mood_score', 'timestamp')
        cursor.execute("""
            SELECT mood_score, timestamp FROM mood_logs
            WHERE user_email = %s
            ORDER BY timestamp DESC LIMIT 1
        """, (user_email,))
        mood_row = cursor.fetchone()
        current_mood = mood_row['mood_score'] if mood_row else None

        # Get mood streak (consecutive days with mood logs)
        cursor.execute("""
            SELECT DATE(timestamp) as day FROM mood_logs
            WHERE user_email = %s
            GROUP BY day
            ORDER BY day DESC
        """, (user_email,))
        days = [row['day'] for row in cursor.fetchall()]
        streak = 1
        if days:
            from datetime import timedelta, date
            today = days[0]
            for i in range(1, len(days)):
                if (today - days[i]).days == i:
                    streak += 1
                else:
                    break

        # Get points earned (example: count of mood logs * 10)
        cursor.execute("SELECT COUNT(*) as count FROM mood_logs WHERE user_email = %s", (user_email,))
        points_earned = cursor.fetchone()['count'] * 10

        # Get mood trend (last 7 days)
        cursor.execute("""
            SELECT DATE(timestamp) as day, AVG(mood_score) as avg_mood
            FROM mood_logs
            WHERE user_email = %s
            GROUP BY day
            ORDER BY day DESC LIMIT 7
        """, (user_email,))
        trend_rows = cursor.fetchall()[::-1]  # reverse for chronological order
        mood_trend_labels = [str(row['day']) for row in trend_rows]
        mood_trend_data = [round(row['avg_mood']) if row['avg_mood'] is not None else None for row in trend_rows]

        # Get recent activities (last 5 mood logs, include notes)
        cursor.execute("""
            SELECT 'Mood Check-in' as type, CONCAT('Mood: ', mood_score) as detail, notes, timestamp as time
            FROM mood_logs WHERE user_email = %s
            ORDER BY timestamp DESC LIMIT 5
        """, (user_email,))
        recent_activities = [
            {
                'type': row['type'],
                'detail': row['detail'],
                'notes': row['notes'],
                'time': row['time'].strftime('%Y-%m-%d %H:%M') if row['time'] else ''
            }
            for row in cursor.fetchall()
        ]

        cursor.close()
        conn.close()

        return jsonify(success=True, data={
            'current_mood': current_mood,
            'streak': streak,
            'points_earned': points_earned,
            'mood_trend_labels': mood_trend_labels,
            'mood_trend_data': mood_trend_data,
            'recent_activities': recent_activities
        }), 200
    except Exception as e:
        print("Error fetching dashboard data:", e)
        return jsonify(success=False, message="Server error fetching dashboard data.", data={}), 500

# --- Add/Update Mood Log Route to support notes ---
@app.route('/mood_log', methods=['POST'])
def mood_log():
    data = request.get_json()
    user_email = data.get('user_email')
    mood_score = data.get('mood_score')
    # Accept both 'mood_notes' and 'notes' for compatibility
    notes = data.get('mood_notes', data.get('notes', None))
    # Accept both 'mood_date' and 'date' for compatibility
    date_str = data.get('mood_date', data.get('date', None))  # Optional date in YYYY-MM-DD
    if not user_email or not mood_score:
        return jsonify(success=False, message="User email and mood score are required."), 400
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed."), 500
        cursor = conn.cursor()
        if date_str:
            # Use provided date at midnight
            try:
                dt = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                cursor.execute(
                    "INSERT INTO mood_logs (user_email, mood_score, notes, timestamp) VALUES (%s, %s, %s, %s)",
                    (user_email, mood_score, notes, dt)
                )
            except Exception as e:
                cursor.close()
                conn.close()
                return jsonify(success=False, message="Invalid date format. Use YYYY-MM-DD."), 400
        else:
            cursor.execute(
                "INSERT INTO mood_logs (user_email, mood_score, notes, timestamp) VALUES (%s, %s, %s, NOW())",
                (user_email, mood_score, notes)
            )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify(success=True, message="Mood logged successfully!"), 201
    except Exception as e:
        print("Error logging mood:", e)
        return jsonify(success=False, message="Server error logging mood."), 500

# --- Update Mood History Route to return notes ---
@app.route('/mood_history', methods=['GET'])
def mood_history():
    user_email = request.args.get('user_email')
    if not user_email:
        return jsonify(success=False, message="User email is required.", data=[]), 400
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed.", data=[]), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT mood_score, notes, timestamp FROM mood_logs WHERE user_email = %s ORDER BY timestamp DESC LIMIT 30",
            (user_email,)
        )
        rows = cursor.fetchall()
        data = [
            {
                'mood_score': row['mood_score'],
                'notes': row['notes'],
                'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M') if row['timestamp'] else ''
            }
            for row in rows
        ]
        cursor.close()
        conn.close()
        return jsonify(success=True, data=data), 200
    except Exception as e:
        print("Error fetching mood history:", e)
        return jsonify(success=False, message="Server error fetching mood history.", data=[]), 500

# --- Log Academic Stress Route ---
@app.route('/log_academic_stress', methods=['POST'])
def log_academic_stress():
    data = request.get_json()
    user_email = data.get('user_email')
    stress_level = data.get('stress_level')
    stress_date = data.get('stress_date')
    if not user_email or not stress_level or not stress_date:
        return jsonify(success=False, message="All fields are required."), 400
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed."), 500
        cursor = conn.cursor()
        try:
            dt = datetime.datetime.strptime(stress_date, '%Y-%m-%d')
        except Exception:
            cursor.close()
            conn.close()
            return jsonify(success=False, message="Invalid date format. Use YYYY-MM-DD."), 400
        cursor.execute(
            "INSERT INTO academic_stress_logs (user_email, stress_level, stress_date) VALUES (%s, %s, %s)",
            (user_email, stress_level, dt)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify(success=True, message="Academic stress logged successfully!"), 201
    except Exception as e:
        print("Error logging academic stress:", e)
        return jsonify(success=False, message="Server error logging academic stress."), 500

# --- Log GPA Route ---
@app.route('/log_gpa', methods=['POST'])
def log_gpa():
    data = request.get_json()
    user_email = data.get('user_email')
    gpa = data.get('gpa')
    academic_period = data.get('academic_period')
    gpa_date = data.get('gpa_date')
    if not user_email or gpa is None or not gpa_date:
        return jsonify(success=False, message="User email, GPA, and date are required."), 400
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed."), 500
        cursor = conn.cursor()
        try:
            dt = datetime.datetime.strptime(gpa_date, '%Y-%m-%d')
        except Exception:
            cursor.close()
            conn.close()
            return jsonify(success=False, message="Invalid date format. Use YYYY-MM-DD."), 400
        cursor.execute(
            "INSERT INTO gpa_logs (user_email, gpa, academic_period, gpa_date) VALUES (%s, %s, %s, %s)",
            (user_email, gpa, academic_period, dt)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify(success=True, message="GPA logged successfully!"), 201
    except Exception as e:
        print("Error logging GPA:", e)
        return jsonify(success=False, message="Server error logging GPA."), 500

# --- Insights and Notifications Route ---
@app.route('/insights_notifications', methods=['GET'])
def insights_notifications():
    print('HIT /insights_notifications', flush=True)  # Debug: log every request
    user_email = request.args.get('user_email')
    if not user_email:
        return jsonify(success=False, message="User email is required.", data={}), 400
    try:
        conn = get_db_connection()
        if not conn:
            print('DB connection failed in /insights_notifications', flush=True)
            return jsonify(success=False, message="Database connection failed.", data={}), 500
        cursor = conn.cursor(dictionary=True)
        # Latest mood
        cursor.execute("SELECT mood_score, notes, timestamp FROM mood_logs WHERE user_email = %s ORDER BY timestamp DESC LIMIT 1", (user_email,))
        latest_mood = cursor.fetchone()
        # Latest academic stress
        cursor.execute("SELECT stress_level, stress_date FROM academic_stress_logs WHERE user_email = %s ORDER BY stress_date DESC LIMIT 1", (user_email,))
        latest_stress = cursor.fetchone()
        # Latest GPA
        cursor.execute("SELECT gpa, academic_period, gpa_date FROM gpa_logs WHERE user_email = %s ORDER BY gpa_date DESC LIMIT 1", (user_email,))
        latest_gpa = cursor.fetchone()
        # Recent mood logs (return last 30 for graph)
        cursor.execute("SELECT mood_score, notes, timestamp FROM mood_logs WHERE user_email = %s ORDER BY timestamp DESC LIMIT 30", (user_email,))
        mood_history = cursor.fetchall()
        # Recent academic stress logs (last 30)
        cursor.execute("SELECT stress_level, stress_date FROM academic_stress_logs WHERE user_email = %s ORDER BY stress_date DESC LIMIT 30", (user_email,))
        stress_history = cursor.fetchall()
        # Recent GPA logs (last 30)
        cursor.execute("SELECT gpa, academic_period, gpa_date FROM gpa_logs WHERE user_email = %s ORDER BY gpa_date DESC LIMIT 30", (user_email,))
        gpa_history = cursor.fetchall()
        cursor.close()
        conn.close()
        print('Returning insights_notifications data', flush=True)
        return jsonify(success=True, data={
            'latest_mood': latest_mood,
            'latest_stress': latest_stress,
            'latest_gpa': latest_gpa,
            'mood_history': mood_history,
            'stress_history': stress_history,
            'gpa_history': gpa_history
        }), 200
    except Exception as e:
        print("Error fetching insights/notifications:", e, flush=True)
        return jsonify(success=False, message="Server error fetching insights/notifications.", data={}), 500

# --- Peer Support Groups Route ---
@app.route('/peer_groups', methods=['GET'])
def get_peer_groups():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT group_id, group_name, description FROM peer_groups")
    groups = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(success=True, groups=groups), 200

# --- Mentor Request Route ---
@app.route('/mentor_request', methods=['POST'])
def mentor_request():
    import traceback
    data = request.get_json()
    print('Received mentor request data:', data, flush=True)  # Debug print
    user_email = data.get('user_email')
    mentor_id = data.get('mentor_id')
    request_message = data.get('request_message', '')
    # Accept mentor_id as optional/null, ensure int or None
    if not user_email:
        print('Missing user_email', flush=True)
        return jsonify(success=False, message="User email is required."), 400
    # If mentor_id is not a valid int, set to None
    try:
        mentor_id = int(mentor_id) if mentor_id is not None and str(mentor_id).strip() != '' else None
    except Exception:
        mentor_id = None
    print(f'Inserting mentor request: user_email={user_email}, mentor_id={mentor_id}, request_message={request_message}', flush=True)
    try:
        conn = get_db_connection()
        if not conn:
            print('Database connection failed', flush=True)
            return jsonify(success=False, message="Database connection failed."), 500
        cursor = conn.cursor()
        try:
            print('About to execute INSERT for mentor_requests:', flush=True)
            print('user_email:', user_email, '| mentor_id:', mentor_id, '| request_message:', request_message, flush=True)
            cursor.execute(
                """
                INSERT INTO mentor_requests (user_email, mentor_id, request_message, status, requested_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_email, mentor_id, request_message, 'pending', datetime.datetime.now())
            )
            conn.commit()
        except Exception as sql_e:
            print('SQL error in mentor_request:', sql_e, flush=True)
            cursor.close()
            conn.close()
            return jsonify(success=False, message="SQL error submitting mentor request.", error=str(sql_e)), 500
        cursor.close()
        conn.close()
        print('Mentor request submitted successfully!', flush=True)
        return jsonify(success=True, message="Mentor request submitted successfully!"), 201
    except Exception as e:
        print("Error submitting mentor request:", e, flush=True)
        traceback.print_exc()
        return jsonify(success=False, message="Server error submitting mentor request.", error=str(e)), 500

# --- Approve Mentor Request and Create Match Route ---
@app.route('/approve_mentor_request', methods=['POST'])
def approve_mentor_request():
    data = request.get_json()
    request_id = data.get('request_id')
    if not request_id:
        return jsonify(success=False, message="Request ID is required."), 400
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Approve the request
        cursor.execute("UPDATE mentor_requests SET status = 'approved' WHERE request_id = %s", (request_id,))
        # Get mentor_id and user_email
        cursor.execute("SELECT mentor_id, user_email FROM mentor_requests WHERE request_id = %s", (request_id,))
        row = cursor.fetchone()
        if not row or not row['mentor_id']:
            cursor.close()
            conn.close()
            return jsonify(success=False, message="Mentor ID not found for this request."), 400
        # Create the match
        cursor.execute(
            "INSERT INTO mentor_matches (request_id, mentor_id, user_email) VALUES (%s, %s, %s)",
            (request_id, row['mentor_id'], row['user_email'])
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify(success=True, message="Mentor request approved and match created."), 200
    except Exception as e:
        print("Error approving mentor request:", e)
        return jsonify(success=False, message="Server error approving mentor request."), 500

# --- List Pending Mentor Requests Route ---
@app.route('/mentor_requests_pending', methods=['GET'])
def mentor_requests_pending():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed.", requests=[]), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT request_id, user_email, mentor_id, request_message, status, requested_at
            FROM mentor_requests
            WHERE status = 'pending'
            ORDER BY requested_at ASC
        """)
        requests = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(success=True, requests=requests), 200
    except Exception as e:
        print("Error fetching pending mentor requests:", e)
        return jsonify(success=False, message="Server error fetching pending mentor requests.", requests=[]), 500

# --- List Mentor Matches for User (for notification polling) ---
@app.route('/mentor_matches', methods=['GET'])
def mentor_matches():
    user_email = request.args.get('user_email')
    if not user_email:
        return jsonify(success=False, message="User email is required.", matches=[]), 400
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed.", matches=[]), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT match_id, request_id, mentor_id, user_email
            FROM mentor_matches
            WHERE user_email = %s
        """, (user_email,))
        matches = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(success=True, matches=matches), 200
    except Exception as e:
        print("Error fetching mentor matches:", e)
        return jsonify(success=False, message="Server error fetching mentor matches.", matches=[]), 500

# --- Serve approve_requests.html ---
@app.route('/approve_requests')
def serve_approve_requests():
    return send_from_directory('.', 'approve_requests.html')

# --- List Mentor Requests for a User (for status section) ---
@app.route('/mentor_requests_user', methods=['GET'])
def mentor_requests_user():
    user_email = request.args.get('user_email')
    if not user_email:
        return jsonify(success=False, message="User email is required.", requests=[]), 400
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed.", requests=[]), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT request_id, mentor_id, request_message, status, requested_at
            FROM mentor_requests
            WHERE user_email = %s
            ORDER BY requested_at DESC
        """, (user_email,))
        requests = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(success=True, requests=requests), 200
    except Exception as e:
        print("Error fetching user mentor requests:", e)
        return jsonify(success=False, message="Server error fetching user mentor requests.", requests=[]), 500

# --- Forum Categories Endpoint ---
@app.route('/forum_categories', methods=['GET'])
def forum_categories():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed.", categories=[]), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name, description FROM forum_categories ORDER BY name ASC")
        categories = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(success=True, categories=categories), 200
    except Exception as e:
        print("Error fetching forum categories:", e)
        return jsonify(success=False, message="Server error fetching forum categories.", categories=[]), 500

# --- Create New Forum Topic Endpoint ---
@app.route('/create_topic', methods=['POST'])
def create_topic():
    data = request.get_json()
    category_id = data.get('category_id')
    title = data.get('title')
    description = data.get('description')  # short description
    content = data.get('content')  # full content
    created_by = data.get('created_by')
    if not category_id or not title or not description or not content or not created_by:
        print('Missing required field(s):', data)
        return jsonify(success=False, message="Category, title, description, content, and created_by are required."), 400
    try:
        conn = get_db_connection()
        if not conn:
            print('Database connection failed in /create_topic')
            return jsonify(success=False, message="Database connection failed."), 500
        cursor = conn.cursor()
        print('Inserting topic:', category_id, title, description, content, created_by)
        cursor.execute(
            "INSERT INTO forum_topics (category_id, title, description, content, created_by) VALUES (%s, %s, %s, %s, %s)",
            (category_id, title, description, content, created_by)
        )
        topic_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        print('Topic created successfully! New topic_id:', topic_id)
        return jsonify(success=True, message="Topic created successfully!", topic_id=topic_id), 201
    except Exception as e:
        import traceback
        print("Error creating topic:", e)
        traceback.print_exc()
        return jsonify(success=False, message="Server error creating topic.", error=str(e)), 500

# --- List Topics for a Category Endpoint ---
@app.route('/forum_topics/<int:category_id>', methods=['GET'])
def forum_topics(category_id):
    try:
        print(f"Fetching topics for category_id: {category_id}", flush=True)
        conn = get_db_connection()
        if not conn:
            print('Database connection failed in /forum_topics', flush=True)
            return jsonify(success=False, message="Database connection failed.", topics=[]), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, title, description, created_by, created_at
            FROM forum_topics
            WHERE category_id = %s
            ORDER BY created_at DESC
        """, (category_id,))
        topics_raw = cursor.fetchall()
        print(f"Found {len(topics_raw)} topics for category_id {category_id}", flush=True)
        # Map fields for frontend compatibility, handle NULLs
        topics = []
        for row in topics_raw:
            topics.append({
                'id': row['id'],
                'title': row['title'] or 'Untitled',
                'user_name': row['created_by'] or 'Unknown',
                'created_at': row['created_at'].strftime('%Y-%m-%d %H:%M') if row['created_at'] else '',
                'last_updated': row['created_at'].strftime('%Y-%m-%d %H:%M') if row['created_at'] else '',
                'content': row['description'] or ''
            })
        cursor.close()
        conn.close()
        return jsonify(success=True, topics=topics), 200
    except Exception as e:
        import traceback
        print(f"Error fetching forum topics for category_id {category_id}: {e}", flush=True)
        traceback.print_exc()
        return jsonify(success=False, message="Server error fetching forum topics.", topics=[]), 500

# --- Forum Posts with Nested Replies Endpoint ---
@app.route('/forum_posts/<int:topic_id>', methods=['GET'])
def forum_posts(topic_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Fetch all posts for the topic
        cursor.execute("SELECT id, topic_id, user_email, content, created_at, parent_id FROM forum_posts WHERE topic_id = %s ORDER BY created_at ASC", (topic_id,))
        posts = cursor.fetchall()
        cursor.close()
        conn.close()
        # Build a dict of posts by id
        post_dict = {post['id']: {**post, 'replies': []} for post in posts}
        root_posts = []
        for post in posts:
            if post['parent_id']:
                parent = post_dict.get(post['parent_id'])
                if parent:
                    parent['replies'].append(post_dict[post['id']])
            else:
                root_posts.append(post_dict[post['id']])
        return jsonify(success=True, posts=root_posts), 200
    except Exception as e:
        print("Error fetching forum posts:", e)
        import traceback; traceback.print_exc()
        return jsonify(success=False, message="Server error fetching posts.", posts=[]), 500

# --- GAD-7 Assessment Submission Route ---
@app.route('/submit_gad7', methods=['POST'])
def submit_gad7():
    data = request.get_json()
    user_email = data.get('user_email')
    answers = data.get('answers')  # Should be a list of 7 integers
    if not user_email or not answers or len(answers) != 7:
        return jsonify(success=False, message="User email and 7 answers are required."), 400
    try:
        total_score = sum(int(x) for x in answers)
        # Severity and advice mapping
        if total_score <= 4:
            severity, color, advice = 'Minimal', 'green', 'No action needed. Monitor as needed.'
        elif total_score <= 9:
            severity, color, advice = 'Mild', 'yellow', 'Consider self-help and monitor symptoms.'
        elif total_score <= 14:
            severity, color, advice = 'Moderate', 'orange', 'Consider talking to a professional.'
        else:
            severity, color, advice = 'Severe', 'red', 'Seek professional help soon.'
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed."), 500
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO gad7_assessments (user_email, q1, q2, q3, q4, q5, q6, q7, total_score, severity, advice)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_email, *answers, total_score, severity, advice)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify(success=True, total_score=total_score, severity=severity, color=color, advice=advice), 201
    except Exception as e:
        print("Error submitting GAD-7:", e)
        return jsonify(success=False, message="Server error submitting GAD-7."), 500

# --- PHQ-9 Assessment Submission Route ---
@app.route('/submit_phq9', methods=['POST'])
def submit_phq9():
    data = request.get_json()
    user_email = data.get('user_email')
    answers = data.get('answers')  # Should be a list of 9 integers
    if not user_email or not answers or len(answers) != 9:
        return jsonify(success=False, message="User email and 9 answers are required."), 400
    try:
        total_score = sum(int(x) for x in answers)
        # Severity and advice mapping
        if total_score <= 4:
            severity, color, advice = 'Minimal', 'green', 'No action needed. Monitor as needed.'
        elif total_score <= 9:
            severity, color, advice = 'Mild', 'yellow', 'Consider self-help and monitor symptoms.'
        elif total_score <= 14:
            severity, color, advice = 'Moderate', 'orange', 'Consider talking to a professional.'
        elif total_score <= 19:
            severity, color, advice = 'Moderately Severe', 'red', 'Seek professional help soon.'
        else:
            severity, color, advice = 'Severe', 'darkred', 'Seek immediate professional help.'
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed."), 500
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO phq9_assessments (user_email, q1, q2, q3, q4, q5, q6, q7, q8, q9, total_score, severity, advice)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_email, *answers, total_score, severity, advice)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify(success=True, total_score=total_score, severity=severity, color=color, advice=advice), 201
    except Exception as e:
        print("Error submitting PHQ-9:", e)
        return jsonify(success=False, message="Server error submitting PHQ-9."), 500

# --- Zoom Integration ---
ZOOM_CLIENT_ID = os.getenv('ZOOM_CLIENT_ID')
ZOOM_CLIENT_SECRET = os.getenv('ZOOM_CLIENT_SECRET')
ZOOM_ACCOUNT_ID = os.getenv('ZOOM_ACCOUNT_ID')
ZOOM_OAUTH_TOKEN_URL = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ZOOM_ACCOUNT_ID}"
ZOOM_CREATE_MEETING_URL = "https://api.zoom.us/v2/users/me/meetings"

_zoom_token_cache = {'access_token': None, 'expires_at': 0}

def get_zoom_access_token():
    global _zoom_token_cache
    now = int(time.time())
    if _zoom_token_cache['access_token'] and now < _zoom_token_cache['expires_at']:
        return _zoom_token_cache['access_token']
    auth = (ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET)
    resp = requests.post(ZOOM_OAUTH_TOKEN_URL, auth=auth)
    if resp.status_code == 200:
        data = resp.json()
        _zoom_token_cache['access_token'] = data['access_token']
        _zoom_token_cache['expires_at'] = now + data['expires_in'] - 60  # buffer
        return data['access_token']
    else:
        print('Failed to get Zoom access token:', resp.text)
        return None

def create_zoom_meeting(topic, start_time):
    token = get_zoom_access_token()
    if not token:
        return None
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        "topic": topic,
        "type": 2,  # Scheduled meeting
        "start_time": start_time,
        "duration": 60,
        "timezone": "UTC",
        "settings": {
            "join_before_host": True,
            "waiting_room": False
        }
    }
    resp = requests.post(ZOOM_CREATE_MEETING_URL, headers=headers, json=payload)
    if resp.status_code == 201:
        return resp.json().get('join_url')
    else:
        print('Failed to create Zoom meeting:', resp.text)
        return None

# --- Book Appointment Route (Zoom optional) ---
@app.route('/book_appointment', methods=['POST'])
def book_appointment():
    data = request.get_json()
    user_email = data.get('user_email')
    therapist_id = data.get('therapist_id')
    appointment_time = data.get('appointment_time')  # Expecting ISO format string
    reason = data.get('reason', None)
    if not user_email or not therapist_id or not appointment_time:
        return jsonify(success=False, message="user_email, therapist_id, and appointment_time are required."), 400
    try:
        # Parse appointment_time to datetime
        try:
            appt_dt = datetime.datetime.fromisoformat(appointment_time)
        except Exception:
            return jsonify(success=False, message="Invalid appointment_time format. Use ISO 8601."), 400
        # Try to create Zoom meeting, but do not fail if it doesn't work
        zoom_url = None
        try:
            zoom_url = create_zoom_meeting(
                topic=f"Therapy Session with {user_email}",
                start_time=appt_dt.isoformat()
            )
        except Exception as e:
            print("Zoom meeting creation failed, proceeding without meeting_url.", e)
            zoom_url = None
        # Add meeting_url column if missing
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed."), 500
        cursor = conn.cursor()
        try:
            cursor.execute("SHOW COLUMNS FROM appointments LIKE 'meeting_url'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE appointments ADD COLUMN meeting_url VARCHAR(512)")
                conn.commit()
        except Exception as e:
            print('Error checking/adding meeting_url column:', e)
        cursor.execute(
            """
            INSERT INTO appointments (user_email, therapist_id, appointment_time, reason, meeting_url)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_email, therapist_id, appt_dt, reason, zoom_url)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify(success=True, message="Appointment booked successfully!", meeting_url=zoom_url), 201
    except Exception as e:
        print("Error booking appointment:", e)
        return jsonify(success=False, message="Server error booking appointment."), 500

# --- User Appointments Route ---
@app.route('/user_appointments', methods=['GET'])
def user_appointments():
    user_email = request.args.get('user_email')
    if not user_email:
        return jsonify(success=False, message="User email is required.", appointments=[]), 400
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed.", appointments=[]), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT a.id as appointment_id, a.therapist_id, a.appointment_time, a.status, t.name as therapist_name, t.specialty, t.email as therapist_email, t.phone as therapist_phone, t.profile_picture_url, a.meeting_url
            FROM appointments a
            JOIN therapists t ON a.therapist_id = t.id
            WHERE a.user_email = %s AND a.appointment_time >= NOW()
            ORDER BY a.appointment_time ASC
        """, (user_email,))
        appointments = [
            {
                'appointment_id': row['appointment_id'],
                'therapist_id': row['therapist_id'],
                'appointment_time': row['appointment_time'].isoformat() if row['appointment_time'] else '',
                'status': row['status'] if 'status' in row else 'Scheduled',
                'therapist_name': row['therapist_name'],
                'specialty': row['specialty'],
                'therapist_email': row['therapist_email'],
                'therapist_phone': row['therapist_phone'],
                'profile_picture_url': row['profile_picture_url'],
                'meeting_url': row.get('meeting_url', '') if 'meeting_url' in row else ''
            }
            for row in cursor.fetchall()
        ]
        cursor.close()
        conn.close()
        return jsonify(success=True, appointments=appointments), 200
    except Exception as e:
        print("Error fetching user appointments:", e)
        return jsonify(success=False, message="Server error fetching appointments.", appointments=[]), 500

# --- Cancel Appointment Route ---
@app.route('/cancel_appointment', methods=['POST'])
def cancel_appointment():
    import traceback
    data = request.get_json()
    appointment_id = data.get('appointment_id')
    user_email = data.get('user_email')
    # Validate appointment_id is an integer
    try:
        appointment_id_int = int(appointment_id)
    except (TypeError, ValueError):
        print(f"Invalid appointment_id for cancel: {appointment_id}", flush=True)
        return jsonify(success=False, message="Invalid appointment_id. Must be an integer."), 400
    if not appointment_id or not user_email:
        return jsonify(success=False, message="appointment_id and user_email are required."), 400
    try:
        conn = get_db_connection()
        if not conn:
            print('DB connection failed in /cancel_appointment', flush=True)
            return jsonify(success=False, message="Database connection failed."), 500
        cursor = conn.cursor()
        # Check if status column exists in appointments table
        try:
            cursor.execute("SHOW COLUMNS FROM appointments LIKE 'status'")
            status_col = cursor.fetchone()
            if not status_col:
                print('Adding status column to appointments table', flush=True)
                cursor.execute("ALTER TABLE appointments ADD COLUMN status VARCHAR(32) DEFAULT 'Scheduled'")
                conn.commit()
        except Exception as e:
            print("Error checking/adding status column:", e, flush=True)
            traceback.print_exc()
        # Only allow the user who booked the appointment to cancel it
        try:
            cursor.execute("""
                UPDATE appointments SET status = 'Cancelled'
                WHERE id = %s AND user_email = %s
            """, (appointment_id_int, user_email))
            conn.commit()
        except Exception as e:
            print('Error running UPDATE for cancel:', e, flush=True)
            traceback.print_exc()
            cursor.close()
            conn.close()
            return jsonify(success=False, message="SQL error cancelling appointment.", error=str(e)), 500
        cursor.close()
        conn.close()
        return jsonify(success=True, message="Appointment cancelled successfully!"), 200
    except Exception as e:
        print("Error cancelling appointment (outer):", e, flush=True)
        traceback.print_exc()
        return jsonify(success=False, message="Server error cancelling appointment.", error=str(e)), 500

# --- SocketIO Handlers ---
@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('connection_response', {'status': 'connected', 'sid': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('join_group')
def handle_join_group(data):
    group_id = data.get('group_id')
    user_email = data.get('user_email')
    join_room(group_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM group_membership WHERE group_id=%s AND user_email=%s", (group_id, user_email))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO group_membership (group_id, user_email) VALUES (%s, %s)", (group_id, user_email))
        conn.commit()
    cursor.execute("SELECT user_email as sender_email, message_text, timestamp FROM group_messages WHERE group_id=%s ORDER BY timestamp ASC LIMIT 50", (group_id,))
    messages = [
        {'sender_email': row[0], 'message_text': row[1], 'timestamp': row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else ''}
        for row in cursor.fetchall()
    ]
    cursor.close()
    conn.close()
    emit('load_messages', {'messages': messages}, room=request.sid)

@socketio.on('leave_group')
def handle_leave_group(data):
    group_id = data.get('group_id')
    user_email = data.get('user_email')
    leave_room(group_id)
    # Optionally remove from group_membership

@socketio.on('send_message')
def handle_send_message(data):
    group_id = data.get('group_id')
    user_email = data.get('user_email')
    message_text = data.get('message_text')
    timestamp = datetime.datetime.now()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO group_messages (group_id, user_email, message_text, timestamp) VALUES (%s, %s, %s, %s)", (group_id, user_email, message_text, timestamp))
    conn.commit()
    cursor.close()
    conn.close()
    emit('new_message', {
        'group_id': group_id,
        'sender_email': user_email,
        'message_text': message_text,
        'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S')
    }, room=group_id)

#Chatbot connect

@app.route('/chat', methods=['POST'])
def chatbot_response():
    data = request.get_json()
    user_message = data.get('message')

    if not user_message:
        return jsonify({'reply': 'Please enter a message.'}), 400

    try:
        # Call Gemini API
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return jsonify({'reply': 'Bot is currently unavailable. API key missing.'}), 500

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}

        payload = {
            "contents": [{"role": "user", "parts": [{"text": user_message}]}],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1000
            }
        }

        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        gemini_response = response.json()

        bot_reply = "I'm sorry, I couldn't generate a response."
        if gemini_response and gemini_response.get('candidates'):
            for candidate in gemini_response['candidates']:
                if 'content' in candidate and 'parts' in candidate['content']:
                    for part in candidate['content']['parts']:
                        if 'text' in part:
                            bot_reply = part['text']
                            break
                if bot_reply != "I'm sorry, I couldn't generate a response.":
                    break

        return jsonify({'reply': bot_reply}), 200

    except Exception as e:
        print("Chatbot Error:", e)
        return jsonify({'reply': f"Server error: {str(e)}"}), 500



# --- Create Forum Post/Reply Endpoint ---
@app.route('/create_post', methods=['POST'])
def create_post():
    import sys
    import traceback
    data = request.get_json()
    print("[DEBUG] /create_post called. Raw data:", data, file=sys.stderr)
    topic_id = data.get('topic_id')
    post_content = data.get('post_content')
    user_email = data.get('user_email')
    parent_id = data.get('parent_id')
    print(f"[DEBUG] topic_id: {topic_id}, post_content: {post_content}, user_email: {user_email}, parent_id: {parent_id}", file=sys.stderr)
    if not topic_id or not post_content or not user_email:
        print("[ERROR] Missing required fields.", file=sys.stderr)
        return jsonify(success=False, message="topic_id, post_content, and user_email are required."), 400
    try:
        conn = get_db_connection()
        if not conn:
            print("[ERROR] Database connection failed.", file=sys.stderr)
            return jsonify(success=False, message="Database connection failed."), 500
        cursor = conn.cursor()
        print(f"[DEBUG] Executing SQL: INSERT INTO forum_posts (topic_id, user_email, content, parent_id) VALUES (%s, %s, %s, %s) with params: ({topic_id}, {user_email}, {post_content}, {parent_id})", file=sys.stderr)
        cursor.execute(
            "INSERT INTO forum_posts (topic_id, user_email, content, parent_id) VALUES (%s, %s, %s, %s)",
            (topic_id, user_email, post_content, parent_id)
        )
        conn.commit()
        print("[DEBUG] Insert successful.", file=sys.stderr)
        cursor.close()
        conn.close()
        return jsonify(success=True, message="Reply posted successfully!"), 201
    except Exception as e:
        print("[ERROR] Exception in /create_post:", e, file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return jsonify(success=False, message="Server error creating post.", error=str(e)), 500

# --- Get Single Forum Topic by ID ---
@app.route('/forum_topic/<int:topic_id>', methods=['GET'])
def get_forum_topic(topic_id):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(success=False, message="Database connection failed.", topic=None), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, title, description, content, created_by, created_at FROM forum_topics WHERE id = %s", (topic_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return jsonify(success=False, message="Topic not found.", topic=None), 404
        topic = {
            'id': row['id'],
            'title': row['title'] or 'Untitled',
            'short_description': row['description'] or '',
            'user_name': row['created_by'] or 'Unknown',
            'created_at': row['created_at'].strftime('%Y-%m-%d %H:%M') if row['created_at'] else '',
            'last_updated': row['created_at'].strftime('%Y-%m-%d %H:%M') if row['created_at'] else '',
            'content': row['content'] or ''
        }
        return jsonify(success=True, topic=topic), 200
    except Exception as e:
        import traceback
        print(f"Error fetching forum topic {topic_id}: {e}")
        traceback.print_exc()
        return jsonify(success=False, message="Server error fetching topic.", topic=None), 500

# --- Main Execution ---
if __name__ == '__main__':
    print("Starting server...")
    port = int(os.environ.get('PORT', 5000))
    # Use localhost for strict matching with frontend
    socketio.run(app, host='127.0.0.1', port=port, debug=True)
