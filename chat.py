from flask import Flask, render_template, redirect, url_for, request, g, flash, jsonify, session
from flask_socketio import SocketIO, emit
from cryptography.fernet import Fernet
import sqlite3

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'NANTERRE_TFN0104!'
app.config['SESSION_USE_COOKIES'] = True
app.secret_key = 'Utilisateur_enligne4!'
socketio = SocketIO(app)

# Générez une clé de chiffrement
key = Fernet.generate_key()
cipher_suite = Fernet(key)

# Fonction pour établir une connexion à la base de données
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect('chat_app.db')
        # Activer les clés étrangères pour les contraintes de référence
        db.execute("PRAGMA foreign_keys = 1")
    return db

# Fonction pour créer la table des utilisateurs et des messages dans la base de données
def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

# Fonction pour fermer la connexion à la base de données à la fin de la requête
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Page d'accueil
@app.route('/')
def home():
    return render_template('index.html')

# Page de création de compte
@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']

        # Ajout de l'utilisateur à la base de données
        with get_db() as db:
            cursor = db.cursor()
            cursor.execute("INSERT INTO users (username, password, first_name, last_name, email) VALUES (?, ?, ?, ?, ?)",
                           (username, password, first_name, last_name, email))
            db.commit()

        return redirect('/chat_home/' + username)


    return render_template('create_account.html')

# Page de connexion
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Vérification de l'utilisateur dans la base de données
        with get_db() as db:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password))
            user = cursor.fetchone()

        if user:
            username = user[1]

            # Mettez à jour le statut de l'utilisateur à "1" (en ligne)
            with get_db() as db:
                cursor = db.cursor()
                cursor.execute("UPDATE users SET status = 1 WHERE username = ?", (username,))
                db.commit()

            # Récupérez la liste des utilisateurs en ligne
            cursor.execute("SELECT username FROM users WHERE status = 1")
            online_users = cursor.fetchall()

            # Utilisez flask.session pour stocker la liste des utilisateurs en ligne
            session['online_users'] = online_users

            # Effectuez la redirection vers la page chat_home avec le nom d'utilisateur
            return redirect(url_for('chat_home', username=username))
        else:
            flash("Veuillez créer un compte avant de vous connecter.", 'error')

    return render_template('login.html')

# Page de discussion
@app.route('/chat_home/<username>')
def chat_home(username):
    # Récupérez l'historique de chat de l'utilisateur depuis la base de données
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("""
            SELECT sender, recipient, content, timestamp
            FROM messages
            WHERE (sender = ? AND recipient = ?) OR (sender = ? AND recipient = ?)
            ORDER BY timestamp ASC
        """, (username, "TO_EVERYONE", "TO_EVERYONE", username))
        chat_history = cursor.fetchall()

        # Récupérez les utilisateurs en ligne depuis la base de données
        cursor.execute("SELECT username FROM users WHERE status = 1 AND username != ?", (username,))
        online_users = cursor.fetchall()

    return render_template('chat_home.html', username=username, chat_history=chat_history, online_users=online_users)


# Page de déconnexion
@app.route('/logout/<username>')
def logout(username):
    # Mettez à jour le statut de l'utilisateur à "0" (hors ligne)
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("UPDATE users SET status = 0 WHERE username = ?", (username,))
        db.commit()

    # Déconnectez l'utilisateur de la session
    session.pop('online_users', None)
    session.pop('sid', None)

    flash('Vous avez été déconnecté avec succès.', 'success')
    return redirect(url_for('home'))


# Nouvelle route pour l'envoi de messages chiffrés dans la discussion individuelle
@app.route('/send_message/<sender>/<recipient>', methods=['POST'])
def send_message(sender, recipient):
    if request.method == 'POST':
        message = request.form['message']

        # Récupérer la clé de session depuis la session Flask
        session_key = session.get('session_key', None)
        
        if session_key:
            # Utiliser la clé de session pour chiffrer le message
            cipher_suite = Fernet(session_key)
            encrypted_message = cipher_suite.encrypt(message.encode())

            # Enregistrez le message chiffré dans la base de données avec le timestamp actuel
            with get_db() as db:
                cursor = db.cursor()
                cursor.execute("INSERT INTO messages (sender, recipient, content, timestamp) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                               (sender, recipient, encrypted_message))
                db.commit()


            # Émettez le message à l'utilisateur destinataire via SocketIO
            socketio.emit('message', {'sender': sender, 'message': encrypted_message.decode()}, room=recipient)

            # Retournez une réponse JSON indiquant que le message a été envoyé avec succès
            return jsonify({'status': 'success', 'message': 'Message envoyé avec succès'})
        else:
            # Retourner une réponse JSON indiquant une erreur si la clé de session est absente
            return jsonify({'status': 'error', 'message': 'Clé de session manquante'})


# Page pour écrire un nouveau message
@app.route('/new_message')
def new_message():
    # Logique pour afficher la page pour écrire un nouveau message
    return render_template('new_message.html')

# Page pour consulter l'historique de chat
@app.route('/chat_history/<username>')
def chat_history(username):
    # Récupérez l'historique de chat de l'utilisateur depuis la base de données
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("SELECT sender, recipient, content FROM messages WHERE sender = ? OR recipient = ?",
                       (username, username))
        chat_history = cursor.fetchall()

    return render_template('chat_history.html', username=username, chat_history=chat_history)

# Page pour supprimer l'historique de chat
@app.route('/delete_chat_history/<username>', methods=['POST'])
def delete_chat_history(username):
    # Supprimez l'historique de chat de l'utilisateur de la base de données
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("DELETE FROM messages WHERE sender = ? OR recipient = ?", (username, username))
        db.commit()

    flash('Historique de chat supprimé avec succès.', 'success')
    return redirect(url_for('chat_home', username=username))

@app.route('/delete_message/<message_id>', methods=['POST'])
def delete_message(message_id):
    # Supprimez le message de la base de données
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        db.commit()

    flash('Message supprimé avec succès.', 'success')
    return redirect(url_for('chat_home', username=username))



# Route Flask où vous pouvez obtenir le sid
@app.route('/get_sid')
def get_sid():
    sid = request.sid
    # Transmettez le sid au gestionnaire d'événements Socket.IO
    socketio.emit('get_sid_response', {'sid': sid})
    return "Sid envoyé au gestionnaire d'événements Socket.IO"
# Gestionnaire d'événements Socket.IO pour la connexion initiale du client
@socketio.on('connect')
def handle_connect():
    sid = request.sid
    session['sid'] = sid
    # Générer une clé de session pour cet utilisateur
    session_key = Fernet.generate_key()
    
    # Stocker la clé de session dans la session Flask
    session['session_key'] = session_key
    
    # Envoyer la clé de session au client via SocketIO
    socketio.emit('session_key', {'sid': sid, 'session_key': session_key})

# Gestionnaire d'événements Socket.IO
@socketio.on('message')
def handle_message(data):
    recipient = data['recipient']
    message = data['message']
    
    # Accédez au SID stocké dans la session Flask
    sid = session.get('sid', None)
    
    # Émettez le message au destinataire en utilisant le sid correct
    socketio.emit('message', {'sender': sid, 'message': message}, room=recipient)


if __name__ == '__main__':
    init_db()
    app.run(debug=True) 