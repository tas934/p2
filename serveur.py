import socket
import select
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, g, flash, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'NANTERRE_TFN0104!'
socketio = SocketIO(app)

clients = {}
serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host, port = "127.0.0.1", 4000
serveur.bind((host, port))
serveur.listen(10)
client_connecte = True
socket_objs = {serveur}
messages = {}

print("Bienvenue dans le chat!")

@socketio.on('connect')
def handle_connect():
    # Envoyez la liste des utilisateurs connectés à tous les clients
    emit('users_list', {'users': get_connected_users()}, broadcast=True)

def broadcast(message, sender_socket):
    for client_socket in socket_objs:
        if client_socket != serveur and client_socket != sender_socket:
            try:
                client_socket.send(message)
            except:
                continue

while client_connecte:
    liste_lu, liste_acce_ecrit, exception = select.select(socket_objs, [], socket_objs)

    for socket_obj in liste_lu:
        if socket_obj == serveur:
            client, adresse = serveur.accept()
            socket_objs.add(client)
            print(f"Nouvelle connexion de {adresse}")

            # Ajouter l'utilisateur à la liste des utilisateurs connectés
            clients[client] = None  # Vous pouvez stocker plus d'informations sur l'utilisateur si nécessaire

            # Envoyer la liste des utilisateurs connectés
            usernames = ", ".join([str(clients[client]) for client in clients])
            client.send(f"Utilisateurs connectés: {usernames}\n".encode("utf-8"))

        else:
            try:
                donnees_recues = socket_obj.recv(128).decode("utf-8")
                if donnees_recues:
                    username, *rest = donnees_recues.split(":")
                    message = ":".join(rest)
                    timestamp = datetime.now().strftime("%H:%M")
                    new_message = f"{timestamp} {username}: {message}"

                    # Gérer les messages privés
                    if len(rest) > 1 and rest[0] in clients:
                        private_recipient = rest[0]
                        private_message = f"(Privé à {private_recipient}) {message}"
                        private_message = f"{timestamp} {username}: {private_message}"
                        private_message = private_message.encode("utf-8")
                        clients[private_recipient].send(private_message)

                    # Ajouter le message à la liste des messages
                    if username not in messages:
                        messages[username] = []
                    messages[username].append(new_message)

                    # Afficher le message côté serveur
                    print(new_message)

                    # Envoyer le message à tous les clients, y compris l'expéditeur
                    message_to_send = new_message.encode("utf-8")
                    broadcast(message_to_send, socket_obj)

            except:
                # Gérer la déconnexion d'un participant
                print(f"Un participant s'est déconnecté: {clients[socket_obj]}")
                socket_objs.remove(socket_obj)
                del clients[socket_obj]
                broadcast(f"{clients[socket_obj]} s'est déconnecté.\n".encode("utf-8"), socket_obj)

    print(f"{len(socket_objs) - 1} participants restants")

if __name__ == '__main__':
    socketio.run(app, debug=True)