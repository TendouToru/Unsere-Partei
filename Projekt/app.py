from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import os
from werkzeug.utils import secure_filename
import secrets
from flask_socketio import SocketIO, emit
from datetime import datetime
import pytz

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key:
    app.secret_key = secrets.token_hex(32)
socketio = SocketIO(app, cors_allowed_origins="*")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")

app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
active_users = set()


# Datenbank Modell für Nutzer
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vorname = db.Column(db.String(80), nullable=False)
    nachname = db.Column(db.String(80), nullable=False)
    geburt = db.Column(db.String(80), nullable=False)
    adresse = db.Column(db.String(80), nullable=False)
    postort = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())


class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())


def log_action(action):
    log = LogEntry(action=action)
    db.session.add(log)
    db.session.commit()


def is_safe_path(basedir, path, follow_symlinks=True):
    # Absoluter Pfad vom Ziel
    if follow_symlinks:
        return os.path.realpath(path).startswith(os.path.realpath(basedir) + os.sep)
    else:
        return os.path.abspath(path).startswith(os.path.abspath(basedir) + os.sep)


def count_files_recursive(path):
    total = 0
    for root, dirs, files in os.walk(path):
        total += len(files)
    return total


# HOMEPAGE
@app.route("/")
def home():
    return render_template("index.html")


# NUTZER-HINZUFÜGEN
@app.route("/add_user", methods=["GET", "POST"])
def add_user():
    if request.method == "POST":
        vorname = request.form["vorname"]
        nachname = request.form["nachname"]
        geburt = request.form["geburt"]
        adresse = request.form["adresse"]
        postort = request.form["postort"]
        email = request.form["email"]
        new_user = User(vorname=vorname, nachname=nachname, geburt=geburt, adresse=adresse, postort=postort, email=email)
        db.session.add(new_user)
        db.session.commit()
        log_action(f"Mitglied hinzugefügt: {vorname} {nachname}")
        return redirect(url_for("list_users"))
    return render_template("add_user.html")


# MITGLIEDSLISTE
@app.route("/users")
def list_users():
    query = request.args.get('q', '').lower()
    users = User.query.all()

    if query:
        users = [u for u in users if
                 query in u.vorname.lower() or
                 query in u.nachname.lower() or
                 query in u.email.lower()]

    return render_template("users.html", users=users)


# MITGLIED LÖSCHEN
@app.route("/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    log_action(f"Mitglied gelöscht: {user.vorname} {user.nachname}")
    return redirect(url_for("list_users"))


# DOKUMENTE - Dateien und Ordner verwalten
@app.route('/dokumente', defaults={'subpath': ''}, methods=['GET', 'POST'])
@app.route('/dokumente/<path:subpath>', methods=['GET', 'POST'])
def dokumente(subpath):
    try:
        # Basisverzeichnis sicher normalisieren
        base_dir = os.path.abspath(os.path.normpath(app.config['UPLOAD_FOLDER']))
        
        # Subpath sicher verarbeiten
        safe_subpath = subpath.strip('/')
        if safe_subpath:
            # Jeden Pfadteil einzeln secure_filename anwenden
            path_parts = [secure_filename(part) for part in safe_subpath.split('/') if part]
            safe_subpath = '/'.join(path_parts)
        
        # Vollständigen Pfad konstruieren
        current_path = os.path.join(base_dir, safe_subpath) if safe_subpath else base_dir
        current_path = os.path.abspath(os.path.normpath(current_path))
        
        # Sicherheitsprüfung - ist der Pfad innerhalb des erlaubten Bereichs?
        if not current_path.startswith(base_dir):
            flash("Zugriff außerhalb des erlaubten Bereichs verweigert.", 'error')
            return redirect(url_for('dokumente', subpath=''))
            
        # Verzeichnis erstellen falls nicht vorhanden
        if not os.path.exists(current_path):
            os.makedirs(current_path, exist_ok=True)
            
        # POST-Verarbeitung (Datei-Upload oder Ordner-Erstellung)
        if request.method == 'POST':
            if 'new_folder' in request.form:
                folder_name = secure_filename(request.form['new_folder'])
                if folder_name:
                    new_folder_path = os.path.join(current_path, folder_name)
                    if is_safe_path(base_dir, new_folder_path):
                        os.makedirs(new_folder_path, exist_ok=True)
                        flash(f"Ordner '{folder_name}' wurde erstellt.", 'success')
                        log_action(f"Ordner erstellt: {os.path.join(safe_subpath, folder_name)}")
                    else:
                        flash("Ungültiger Ordnerpfad.", 'error')
                else:
                    flash("Ordnername darf nicht leer sein.", 'error')
                    
            elif 'file' in request.files:
                file = request.files['file']
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    save_path = os.path.join(current_path, filename)
                    if is_safe_path(base_dir, save_path):
                        file.save(save_path)
                        flash("Datei erfolgreich hochgeladen.", 'success')
                        log_action(f"Datei hochgeladen: {os.path.join(safe_subpath, filename)}")
                    else:
                        flash("Ungültiger Dateipfad.", 'error')
                else:
                    flash("Keine Datei ausgewählt.", 'error')
                    
            return redirect(url_for('dokumente', subpath=safe_subpath))
        
        # Verzeichnisinhalt lesen
        try:
            entries = os.listdir(current_path)
            directories = []
            files = []
            
            for entry in entries:
                full_path = os.path.join(current_path, entry)
                if os.path.isdir(full_path):
                    directories.append(entry)
                elif os.path.isfile(full_path):
                    files.append(entry)
                    
        except Exception as e:
            flash(f"Fehler beim Lesen des Verzeichnisses: {str(e)}", 'error')
            return redirect(url_for('dokumente', subpath=''))
        
        # Template rendern
        return render_template('dokumente.html',
                            files=files,
                            directories=directories,
                            current_path=safe_subpath)
                            
    except Exception as e:
        flash(f"Schwerwiegender Fehler: {str(e)}", 'error')
        return redirect(url_for('dokumente', subpath=''))


# DATEI LÖSCHEN
@app.route('/delete_file/<path:filename>', methods=['POST'])
def delete_file(filename):
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not is_safe_path(app.config['UPLOAD_FOLDER'], full_path):
        flash("Ungültiger Pfad.", 'error')
        return redirect(url_for('dokumente', subpath=''))

    if os.path.exists(full_path):
        try:
            os.remove(full_path)
            flash(f'Datei "{os.path.basename(filename)}" wurde erfolgreich gelöscht.', 'success')
            log_action(f'Datei gelöscht: {filename}')
        except Exception as e:
            flash(f'Fehler beim Löschen: {e}', 'error')
    else:
        flash('Datei nicht gefunden.', 'error')

    parent_path = os.path.dirname(filename)
    return redirect(url_for('dokumente', subpath=parent_path))

@app.route('/download/<path:filename>')
def download_file(filename):
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not is_safe_path(app.config['UPLOAD_FOLDER'], full_path):
        flash("Ungültiger Pfad.", 'error')
        return redirect(url_for('dokumente', subpath=''))
    
    if os.path.exists(full_path):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    else:
        flash('Datei nicht gefunden.', 'error')
        return redirect(url_for('dokumente', subpath=os.path.dirname(filename)))

# STATISTIKEN
@app.route('/stats')
def stats():
    num_users = User.query.count()
    num_files = count_files_recursive(app.config['UPLOAD_FOLDER'])
    return render_template('stats.html', num_users=num_users, num_files=num_files)


# CHAT-FORUM
@app.route('/chat')
def chat():
    messages = ChatMessage.query.order_by(ChatMessage.timestamp.asc()).all()

    berlin = pytz.timezone("Europe/Berlin")
    messages_with_local_time = []
    for msg in messages:
        utc_time = msg.timestamp.replace(tzinfo=pytz.utc)
        local_time = utc_time.astimezone(berlin)
        messages_with_local_time.append({
            'username': msg.username,
            'message': msg.message,
            'date': local_time.strftime("%d.%m.%Y"),
            'time': local_time.strftime("%H:%M")
        })

    return render_template('chat.html', messages=messages_with_local_time)


# SocketIO-Event für neue Nachrichten
@socketio.on('message')
def handle_message(data):
    msg = ChatMessage(username=data['username'], message=data['message'])
    db.session.add(msg)
    db.session.commit()

    # Zeitzone umwandeln: von UTC zu Europe/Berlin
    utc_time = msg.timestamp.replace(tzinfo=pytz.utc)
    local_time = utc_time.astimezone(pytz.timezone("Europe/Berlin"))

    emit('message', {
        'username': data['username'],
        'message': data['message'],
        'date': local_time.strftime("%d.%m.%Y"),
        'time': local_time.strftime("%H:%M")
    }, broadcast=True)


@socketio.on('connect')
def handle_connect():
    active_users.add(request.sid)
    emit('update_active_users', {'count': len(active_users)}, broadcast=True)


@socketio.on('disconnect')
def handle_disconnect():
    active_users.discard(request.sid)
    emit('update_active_users', {'count': len(active_users)}, broadcast=True)


@app.route('/api/stats')
def get_stats():
    today = datetime.today().date()
    messages_today = ChatMessage.query.filter(ChatMessage.timestamp >= today).count()
    return {
        'messages_today': messages_today,
        'next_event': "14.06.2025 - Gründungsmeeting"  # Eventabgriff
    }

# Protokoll
@app.route("/log")
def show_log():
    entries = LogEntry.query.order_by(LogEntry.timestamp.desc()).limit(100).all()
    return render_template("log.html", entries=entries)
    
# Löschen Protokoll
@app.route('/log/delete/<int:entry_id>', methods=['POST'])
def delete_log_entry(entry_id):
    entry = LogEntry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    flash('Eintrag gelöscht.', 'success')
    return redirect(url_for('show_log')) 

# Fehlerhandler für Upload-Limit überschritten
@app.errorhandler(413)
def request_entity_too_large(error):
    flash("Datei ist zu groß (max. 16 MB).")
    return redirect(request.referrer or url_for('dokumente', subpath='')), 413


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
