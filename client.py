import socket
import threading
from cryptography.fernet import Fernet

# Clé de chiffrement partagée avec le serveur
server_public_key = b'mdp_chiffrage'
cipher_suite = Fernet(server_public_key)

def ecouter_messages(socket_client):
    while True:
        try:
            # Recevoir et déchiffrer le message
            encrypted_message = socket_client.recv(128)
            decrypted_message = cipher_suite.decrypt(encrypted_message).decode("utf-8")

            print(decrypted_message)
        except Exception as e:
            print(f"Erreur lors de la réception du message: {e}")
            break

def envoyer_messages(socket_client, username):
    while True:
        try:
            # Saisir le message à envoyer
            message = input("Votre message: ")
            
            # Ajouter le nom d'utilisateur au message
            message = f"{username}: {message}"

            # Chiffrer et envoyer le message
            encrypted_message = cipher_suite.encrypt(message.encode("utf-8"))
            socket_client.send(encrypted_message)
        except Exception as e:
            print(f"Erreur lors de l'envoi du message: {e}")
            break

# Création d'un socket client
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host, port = "127.0.0.1", 4000

# Connexion au serveur
client.connect((host, port))
print("Connecté au serveur!")

# Obtenir le nom d'utilisateur du client
username = input("Entrez votre nom d'utilisateur: ")

# Lancer des threads pour écouter et envoyer des messages
thread_ecoute = threading.Thread(target=ecouter_messages, args=(client,))
thread_envoi = threading.Thread(target=envoyer_messages, args=(client, username))

# Démarrer les threads
thread_ecoute.start()
thread_envoi.start()

try:
    # Attendre que les threads se terminent (peut être interrompu par KeyboardInterrupt)
    thread_ecoute.join()
    thread_envoi.join()
except KeyboardInterrupt:
    pass  # Ignorer l'exception KeyboardInterrupt

# Fermer la connexion
client.close()
