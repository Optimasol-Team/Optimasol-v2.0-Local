import paho.mqtt.client as mqtt 
from config_loader import load_config

host, port, username, password, client_id = load_config() #On charge la configuration MQTT. 

"""La fonction suivant est la fonction entrée qui doit être appelée pour envoyer un message
Elle doit être appelée sans appeler à chaque fois la fonction load config"""
def send(message, topic) :
    client = mqtt.Client(client_id="test123987456centrale")                  #On crée un client MQTT avec l'ID du logiciel (généralemet Optimasol) 
    try : #On essaie de se connecter au broker
        if username != None and password != None :          #Si le mot de passe est exigée on configure la connexion avec le broker
           client.username_pw_set(username, password)
           client.connect(host, port) 
           print("La connexion a été effectuée avec succès et avec identification.") 
        else :
              client.connect(host, port) 
              print("La connexion a été effectuée avec succès et sans identification car celle ci n'est pas exigée") 
    except :
        print("La connexion au broker a complètement échouée. Le message utilise le broker public test.mosquitto.org en port 1883.")
        client.connect("test.mosquitto.org", 1883) #On bascule vers le broker public test.mosquitto.org

    try : 
        client.publish(topic, message)
        client.disconnect()
        print("Le message a été envoyé avec succès et la déconnexion a été effectuée automatiquement.") 
    except :
        print("L'envoi du message a échoué. Il faut contacter l'équipe Optimasol Team") 

if __name__ == "__main__" :
    send("Bonjour, ceci est un message de test envoyé par le script sender.py du dossier mqtt_sender.", "test123987456centrale") 


    
    

