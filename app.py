from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import pymysql
from flask_bcrypt import Bcrypt
from db import get_db_connection
from config import Config
import os
import hashlib
import shutil
import mimetypes
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid
import tkinter as tk
from tkinterdnd2 import DND_FILES, TkinterDnD
from tkinter import filedialog, messagebox
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, DirCreatedEvent, FileCreatedEvent
import time
import threading
from file_selector import select_files_with_tkinter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from email_util import send_email

app = Flask(__name__)
app.config.from_object(Config)
bcrypt = Bcrypt(app)

UPLOAD_FOLDER = 'uploads'
BACKUP_FOLDER = 'backups'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)

ignored_paths = set()
observer_running = 0
user_email = None

def get_agent_info():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT name, status FROM agent LIMIT 1")
        agent = cursor.fetchone()
    connection.close()
    return agent

def get_email():
    global user_email
    return user_email


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and bcrypt.check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['profile'] = {
                'email': user['email'],
                'profile_pic': user['profile_pic']
            }
            global user_email
            user_email = user['email']
            print(user_email)
            return '', 200  # Success
        return "Invalid credentials", 401

    return render_template('login.html')



@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        profile_pic = request.files.get('profile_pic')

        if not email or not password or not profile_pic:
            return "Missing required fields", 400

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        pic_path = os.path.join("static/profile_pics", profile_pic.filename)
        profile_pic.save(pic_path)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (email, password_hash, profile_pic) VALUES (%s, %s, %s)",
                (email, hashed_password, pic_path)
            )
            conn.commit()
        except pymysql.err.IntegrityError:
            return "Email already exists", 400
        finally:
            conn.close()

        return '', 200  # Success

    return render_template("signup.html")



@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    agent = get_agent_info()
    profile = session.get('profile', {'email': 'Unknown', 'profile_pic': 'https://via.placeholder.com/70'})
    return render_template('upload.html', agent=agent, profile=profile)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.route('/agent', methods=['GET'])
def get_agent():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get agent info
    cursor.execute("SELECT * FROM agent LIMIT 1")
    agent = cursor.fetchone()

    # Get event priorities
    cursor.execute("SELECT * FROM events")
    events = cursor.fetchall()

    # Get priority actions
    cursor.execute("SELECT * FROM priorities")
    priorities = cursor.fetchall()

    conn.close()
    profile = session.get('profile', {'email': 'Unknown', 'profile_pic': 'https://via.placeholder.com/70'})
    return render_template("agent.html", agent=agent, events=events, priorities=priorities, profile=profile)


@app.route('/agent/save', methods=['POST'])
def save_agent_settings():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    # Update agent name and status
    cursor.execute("UPDATE agent SET name = %s, status = %s WHERE id = 1", (data['name'], data['status']))

    # Update event priorities
    for event, priority in data['events'].items():
        cursor.execute("UPDATE events SET priority = %s WHERE event_name = %s", (priority, event))

    # Update priority actions
    for priority, action in data['priorities'].items():
        cursor.execute("UPDATE priorities SET action = %s WHERE priority_level = %s", (action, priority))

    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Settings saved successfully!"})

@app.route("/monitor")
def monitor_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    agent = get_agent_info()
    profile = session.get('profile', {'email': 'Unknown', 'profile_pic': 'https://via.placeholder.com/70'})
    return render_template("monitor.html", agent=agent, profile=profile)

@app.route("/monitor/data")
def monitor_data():
    connection = get_db_connection()

    # Get current time in Sri Lanka timezone
    now = datetime.now(ZoneInfo("Asia/Kolkata")).replace(second=0, microsecond=0)

    # Generate last 20 minutes
    times = [(now - timedelta(minutes=i)) for i in reversed(range(20))]
    result = {t.strftime("%H:%M"): 0 for t in times}

    # Generate time bounds (start, end) for each minute
    time_bounds = [(t.strftime("%Y-%m-%d %H:%M:00"), (t + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:00")) for t in
                   times]

    with connection.cursor() as cursor:
        for (start, end), t in zip(time_bounds, result):
            cursor.execute("""
                    SELECT COUNT(*) AS count FROM logs
                    WHERE timestamp >= %s AND timestamp < %s
                """, (start, end))
            result[t] = cursor.fetchone()['count']

    connection.close()
    return jsonify(result)

@app.route("/monitor/logs")
def monitor_logs():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT event_type, file_path, file_hash, file_size, file_type, 
                   file_category, priority_level, timestamp 
            FROM logs 
            ORDER BY timestamp DESC 
            LIMIT 50
        """)
        logs = cursor.fetchall()
    connection.close()

    for row in logs:
        if row['file_size'] is not None:
            row['file_size'] = round(row['file_size'], 2)

    return jsonify(logs)

@app.route("/monitor/toggle", methods=["POST"])
def toggle_agent_status():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT status FROM agent LIMIT 1")
        current_status = cursor.fetchone()['status']
        new_status = 0 if current_status else 1
        cursor.execute("UPDATE agent SET status = %s", (new_status,))
        connection.commit()
    connection.close()
    return jsonify({"status": new_status})


def generate_hash(file_path):
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

@app.route("/versioning")
def backups_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    profile = session.get('profile', {'email': 'Unknown', 'profile_pic': 'https://via.placeholder.com/70'})
    return render_template("versioning.html", profile=profile)

@app.route("/backups/data")
def backups_data():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, path, hash, time, file_type, size
            FROM uploads
            WHERE backup_id IS NOT NULL
        """)
        rows = cursor.fetchall()
    connection.close()

    # Round size to 2 decimal places
    for row in rows:
        if row['size'] is not None:
            row['size'] = round(row['size'], 2)

    return jsonify(rows)

@app.route("/uploaded_items", methods=["GET"])
def get_uploaded_items():
    """Fetches all uploaded files and folders and returns them in the same format as /upload."""
    db = get_db_connection()
    cursor = db.cursor()

    uploaded_data = []

    # Fetch uploaded files
    cursor.execute("SELECT * FROM uploads")
    files = cursor.fetchall()

    for file in files:
        uploaded_data.append({
            "filename": os.path.basename(file['path']),
            "path": file['path'],
            "hash": file['hash'],
            "size": round(file['size'], 2),
            "type": file['type'],
            "file_type": file['file_type'],
            "backup": "Yes" if file['backup_id'] else "No"
        })

    # Fetch uploaded folders
    cursor.execute("SELECT * FROM folders")
    folders = cursor.fetchall()

    for folder in folders:
        uploaded_data.append({
            "filename": os.path.basename(folder['path']),
            "path": folder['path'],
            "type": "folder",
            "file_type": "folder"
        })

    db.close()

    if not uploaded_data:
        return jsonify({
            "message": "No uploaded files or folders found.",
            "data": None
        }), 200

    return jsonify({
        "message": "Upload history fetched successfully.",
        "data": uploaded_data
    }), 200


@app.route("/upload", methods=["POST"])
def upload_file():
    """Handles file selection, checks for duplicates, skips duplicates, and uploads unique files/folders."""
    backup_enabled = request.json.get("backup", False)

    selected_files, selected_folders = select_files_with_tkinter()
    if not selected_files and not selected_folders:
        return jsonify({"message": "No files or folders selected"}), 400

    db = get_db_connection()
    cursor = db.cursor()

    skipped_items = []
    filtered_files = []
    filtered_folders = []

    # Normalize and filter files
    for original_path in selected_files:
        normalized_path = normalize_path(original_path)
        file_hash = generate_hash(original_path)

        cursor.execute("SELECT id FROM uploads WHERE path = %s AND hash = %s", (normalized_path, file_hash))
        if cursor.fetchone():
            skipped_items.append({"type": "file", "path": normalized_path})
        else:
            filtered_files.append((original_path, normalized_path, file_hash))

    # Normalize and filter folders
    for folder_path in selected_folders:
        normalized_path = normalize_path(folder_path)

        cursor.execute("SELECT id FROM folders WHERE path = %s", (normalized_path,))
        if cursor.fetchone():
            skipped_items.append({"type": "folder", "path": normalized_path})
        else:
            filtered_folders.append(normalized_path)

    uploaded_data = []

    # Process filtered files
    for original_path, normalized_path, file_hash in filtered_files:
        filename = os.path.basename(original_path)
        unique_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_filename = f"{timestamp}_{unique_id}_{filename}"
        upload_path = os.path.join(UPLOAD_FOLDER, unique_filename)

        shutil.copy2(original_path, upload_path)
        file_size = os.path.getsize(upload_path) / (1024 * 1024)
        file_type = filename.split(".")[-1] if "." in filename else "unknown"

        backup_id = None
        if backup_enabled:
            backup_path = os.path.join(BACKUP_FOLDER, unique_filename)
            shutil.copy2(upload_path, backup_path)
            cursor.execute("INSERT INTO backups (filename, path) VALUES (%s, %s)", (filename, backup_path))
            db.commit()
            backup_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO uploads (path, hash, type, size, file_type, backup_id) VALUES (%s, %s, %s, %s, %s, %s)",
            (normalized_path, file_hash, 'file', file_size, file_type, backup_id)
        )
        db.commit()

        uploaded_data.append({
            "filename": filename,
            "path": normalized_path,
            "hash": file_hash,
            "size": round(file_size, 2),
            "type": "file",
            "file_type": file_type,
            "backup": "Yes" if backup_enabled else "No"
        })

    # Clear uploads folder
    for f in os.listdir(UPLOAD_FOLDER):
        os.remove(os.path.join(UPLOAD_FOLDER, f))

    # Process filtered folders
    for normalized_path in filtered_folders:
        cursor.execute("INSERT INTO folders (path) VALUES (%s)", (normalized_path,))
        db.commit()

        uploaded_data.append({
            "path": normalized_path,
            "type": "folder",
            "file_type": "folder"
        })

    db.close()

    # Prepare final response
    if not uploaded_data and skipped_items:
        return jsonify({
            "message": "All selected files and folders already exist.",
            "data": None
        }), 200

    if uploaded_data and skipped_items:
        return jsonify({
            "message": "Some files or folders already existed and were skipped.",
            "data": uploaded_data
        }), 200

    return jsonify({
        "message": "Upload successful.",
        "data": uploaded_data
    }), 200



def log_event(event_type, path, file_hash=None, file_size=None, file_type=None,
              file_category=None, priority_level=None):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO logs (
                    event_type, file_path, file_hash, file_size, file_type,
                    file_category, priority_level, timestamp
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            now = datetime.now()
            cursor.execute(sql, (
                event_type, path, file_hash, file_size, file_type,
                file_category, priority_level, now
            ))
            conn.commit()
            print(f"Logged event: {event_type} for {path} at {now}")
    except pymysql.Error as e:
        print(f"Error logging event: {e}")
    finally:
        if conn:
            conn.close()

@app.route("/backups/restore", methods=["POST"])
def restore_backup():
    file_id = request.form.get('id')
    connection = get_db_connection()
    with connection.cursor() as cursor:
        # Get file info
        cursor.execute("SELECT path, backup_id FROM uploads WHERE id = %s", (file_id,))
        file_row = cursor.fetchone()

        if not file_row:
            return jsonify({"message": "File not found!"}), 404

        # Get backup path
        cursor.execute("SELECT path FROM backups WHERE id = %s", (file_row['backup_id'],))
        backup_row = cursor.fetchone()

        if not backup_row:
            return jsonify({"message": "Backup not found!"}), 404

        original_path = file_row['path']
        backup_path = backup_row['path']

        try:
            # Ignore this path temporarily
            ignored_paths.add(original_path)
            shutil.copy2(backup_path, original_path)
            # You could add a small delay before removing if needed
            ignored_paths.remove(original_path)

            return jsonify({"message": "File restored successfully!"})
        except Exception as e:
            return jsonify({"message": f"Error restoring: {str(e)}"}), 500
    connection.close()

@app.route("/reset", methods=["POST"])
def reset_all_data():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("UPDATE agent SET status = %s", (0,))
        db.commit()

        # Clear all relevant tables
        cursor.execute("DELETE FROM uploads")
        cursor.execute("DELETE FROM backups")
        cursor.execute("DELETE FROM logs")
        cursor.execute("DELETE FROM folders")
        db.commit()

        # Clear the backups folder
        for filename in os.listdir(BACKUP_FOLDER):
            file_path = os.path.join(BACKUP_FOLDER, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)

        cursor.execute("UPDATE agent SET status = %s", (1,))
        db.commit()
        db.close()
        return jsonify({"message": "All data and backup files reset successfully."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def log_from_file_id(file_id, event_type, priority_level=None):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Get file info from uploads
            cursor.execute("SELECT path, hash, size, file_type, type FROM uploads WHERE id = %s", (file_id,))
            result = cursor.fetchone()

            if result:
                path = result['path']
                file_hash = result['hash']
                size = result['size']
                file_type = result['file_type']
                file_category = "file"
                print(result['size'])
                log_event(
                    event_type=event_type,
                    path=path,
                    file_hash=file_hash,
                    file_size=size,
                    file_type=file_type,
                    file_category=file_category,
                    priority_level=priority_level
                )
            else:
                print(f"No upload entry found with ID {file_id}")
    except pymysql.Error as e:
        print(f"Error retrieving file info for logging: {e}")
    finally:
        if conn:
            conn.close()


def normalize_path(path):
    """ Convert paths to a consistent format (forward slashes) """
    return os.path.normpath(path).replace("\\", "/")

def get_backup_info(file_id):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        SELECT b.path
        FROM uploads u
        LEFT JOIN backups b ON u.backup_id = b.id
        WHERE u.id = %d
    """ % file_id)
    result = cursor.fetchone()
    db.close()
    return result

def is_monitoring_enabled():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM agent WHERE id = 1")
    result = cur.fetchone()
    conn.close()
    return result and result['status'] == 1


class FileMonitorHandler(FileSystemEventHandler):
    def __init__(self, monitored_files, monitored_folders):
        self.monitored_files = monitored_files  # Dictionary: path -> id
        self.monitored_folders = monitored_folders  # Dictionary: path -> id
        self.suppress_events = set()  # Paths to suppress temporarily

    def on_created(self, event):
        path = normalize_path(event.src_path)
        folder_path = os.path.dirname(path)

        if path in ignored_paths or folder_path in ignored_paths:
            return

        if path in self.suppress_events or folder_path in self.suppress_events:
            return  # Skip event triggered by restoration

        if folder_path in self.monitored_folders:
            event_info = get_event_action("on_create")
            action = event_info['action']
            priority_level = event_info['priority_level']

            if "Email" in action:
                receiver = get_email()
                send_email(receiver, "created", path, priority_level)

            # Get file info directly
            try:
                file_hash = ""
                if os.path.isfile(path):
                    size = os.path.getsize(path) / (1024 * 1024)
                    file_type, _ = mimetypes.guess_type(path)
                    file_category = "file"
                    file_hash = generate_hash(path)
                elif os.path.isdir(path):
                    size = 0.0  # or calculate folder size if needed
                    file_type = None
                    file_category = "folder"
                else:
                    print("Unknown created type:", path)
                    return

                log_event(
                    event_type="on_create",
                    path=path,
                    file_hash=file_hash,
                    file_size=size,
                    file_type=file_type,
                    file_category=file_category,
                    priority_level=priority_level
                )

            except Exception as e:
                print(f"Error handling on_created for {path}: {e}")

        print("Created:", folder_path)

    def on_modified(self, event):
        path = normalize_path(event.src_path)
        if path in ignored_paths:
            return

        if path in self.suppress_events:
            self.suppress_events.remove(path)
            return

        print("Modified:", path)

        if os.path.isfile(path):  # Handle file modifications
            self._check_file_integrity(path)

        # elif os.path.isdir(path):  # Handle folder modifications
        #     for file_path, file_id in self.monitored_files.items():
        #         if file_path.startswith(path):  # File is inside the modified folder
        #             self._check_file_integrity(file_path)

    def on_deleted(self, event):
        path = normalize_path(event.src_path)
        print("Deleted:", path)

        if path in self.monitored_files:
            file_id = self.monitored_files[path]

            event_info = get_event_action("on_delete")
            action = event_info['action']
            priority_level = event_info['priority_level']

            log_from_file_id(file_id=file_id, event_type="on_delete", priority_level=priority_level)

            if "Backup Restore" in action:
                # Attempt restore
                print("Backup restore..")
                self._restore_file_from_backup(path, file_id)

            if "Email" in action:
                receiver = get_email()
                send_email(receiver, "deleted", path, priority_level)


    def on_moved(self, event):
        path = normalize_path(event.src_path)
        if path in ignored_paths:
            return
        old_path = normalize_path(event.src_path)
        new_path = normalize_path(event.dest_path)
        print(f"Moved: {old_path} -> {new_path}")
        if old_path in self.monitored_files:
            file_id = self.monitored_files[old_path]
            event_info = get_event_action("on_delete")
            action = event_info['action']
            priority_level = event_info['priority_level']

            log_from_file_id(file_id=file_id, event_type="on_moved", priority_level=priority_level)

    def _check_file_integrity(self, file_path):
        if not os.path.exists(file_path):  # File may have been deleted
            return

        file_id = self.monitored_files.get(file_path)
        if not file_id:
            return

        try:
            current_hash = generate_hash(file_path)
            result = get_uploaded_file_info(file_id)

            if result and 'hash' in result:
                original_hash = result['hash']
                if current_hash != original_hash:

                    event_info = get_event_action("on_modified")
                    action = event_info['action']
                    priority_level = event_info['priority_level']

                    log_from_file_id(file_id=file_id, event_type="on_modified", priority_level=priority_level)

                    if "Backup Restore" in action:
                        # Attempt restore
                        print("Backup restore..")
                        self._restore_file_from_backup(file_path, file_id)

                    if "Email" in action:
                        receiver = get_email()
                        send_email(receiver, "modified", file_path, priority_level)

                else:
                    print(f"No content change: {file_path}")

        except Exception as e:
            print(f"Error checking integrity for {file_path}: {e}")

    def _restore_file_from_backup(self, path, file_id):
        try:
            backup_info = get_backup_info(file_id)
            if backup_info['path'] is not None:
                backup_path = backup_info['path']
                self.suppress_events.add(path)
                shutil.copy2(backup_path, path)
                print(f"File restored from backup: {path}")
            else:
                print(f"No backup available to restore: {path}")
        except Exception as e:
            print(f"Failed to restore file: {e}")


def get_uploaded_file_info(file_id):

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT hash FROM uploads WHERE id = %s", (file_id,))
            row = cursor.fetchone()
            return row if row else None
    finally:
        conn.close()

def get_event_action(event_name):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT p.priority_level, p.action
                FROM events e
                JOIN priorities p ON e.priority = p.priority_level
                WHERE e.event_name = %s
            """, (event_name,))
            result = cursor.fetchone()
            if result['action']:
                return {'action': result['action'], 'priority_level': result['priority_level']}
            else:
                return None

    except Exception as e:
        print(f"Error performing action for event {event_name}: {e}")
        return None
    finally:
        conn.close()


def send_email_notification(event_name, file_path):
    print(f"Sending email for {event_name} on {file_path}]")
    # Actual email logic here


# Fetch file paths from the database
def get_files_from_db():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id, path FROM uploads")
    files = {normalize_path(row["path"]): row["id"] for row in cursor.fetchall()}
    db.close()
    return files

def get_folders_from_db():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT path FROM folders")
    folders = {normalize_path(row["path"]) for row in cursor.fetchall()}
    db.close()
    return folders



# Main function to start monitoring
def start_monitoring():
    global user_email
    file_paths = get_files_from_db()
    folder_paths = get_folders_from_db()
    event_handler = FileMonitorHandler(file_paths, folder_paths)
    observer = Observer()

    def schedule_dirs(file_dict, folder_set):
        observer.unschedule_all()
        watched_dirs = set(os.path.dirname(path) for path in file_dict)

        # Only add folder paths not already in watched_dirs
        for folder_path in folder_set:
            dir_path = normalize_path(folder_path)
            if dir_path not in watched_dirs:
                watched_dirs.add(dir_path)

        for directory in watched_dirs:
            observer.schedule(event_handler, directory, recursive=False)
        print("Currently watched directories:", watched_dirs)

    # Initial schedule
    schedule_dirs(file_paths, folder_paths)

    if is_monitoring_enabled():
        observer.start()
        global observer_running
        observer_running = 1
        print("Monitoring started...")

    try:
        while True:
            time.sleep(10)
            if observer_running:
                if is_monitoring_enabled():
                    new_files = get_files_from_db()
                    new_folders = get_folders_from_db()
                    if new_files.keys() != file_paths.keys() or new_folders != folder_paths:
                        print("New files/folders detected. Updating monitoring list...")
                        file_paths.clear()
                        file_paths.update(new_files)
                        folder_paths.clear()
                        folder_paths.update(new_folders)
                        event_handler.monitored_files = file_paths
                        event_handler.monitored_folders = folder_paths
                        schedule_dirs(file_paths, folder_paths)
                else:
                    observer.stop()
                    observer_running = 0
            elif is_monitoring_enabled():
                observer_running = 1
                file_paths = get_files_from_db()
                folder_paths = get_folders_from_db()
                event_handler = FileMonitorHandler(file_paths, folder_paths)
                observer = Observer()
                schedule_dirs(file_paths, folder_paths)
                observer.start()

    except KeyboardInterrupt:
        observer.stop()
    observer.join()



def run_flask():
    app.run(debug=True, use_reloader=False)  # Prevent reloader from interfering

if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Start monitoring in the main thread
    start_monitoring()
