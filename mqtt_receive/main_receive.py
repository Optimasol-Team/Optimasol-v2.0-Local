""" Le but de ce scipt est de recevoir les messages de la part des routeurs, 
Il commence par charger les configurations à travers le programme config_loader (similaire de celui de l'envoi)
Ensuite on il est à l'écoute des messages MQTT qui viennent dans le topic configuré
Finalement il utilise le programme writer.py pour écrire les messages dans la base de données. 
 """
import sys 
import paho.mqtt.client as mqtt 
from config_loader import load_config
from writer import write_to_db


def main_receive() :
    try :
        host, port, username, password, client_id, topic = load_config() #On charge la configuration MQTT. 
        print("La configuration a été chargée avec succès.")
        print("Pour la réception, le broker sera %s, le port %s, le client_id %s et le topic %s." % (host, port, client_id, topic))
    except Exception:
        print("Le chargement de la configuration a échoué. Veuillez vérifier le fichier de configuration.")
        sys.exit(1) #On arrête le programme immédiatement si la configuration échoue. 


    def on_connect(client, userdata, flags, rc):
        if rc == 0: #Cela signifie que la conexion a réussi. 
            print("La connexion avec le broker %s a été résussie." % host) 
            client.subscribe(topic) #On s'abonne au topic configuré.
            print("Le client s'est abonné au topic %s avec succès." % topic)
        else :
            print("La connexion a échoué avec le code %d. Veuillez revoir les configurations de votre Broker MQTT" % rc)
            sys.exit(1) #On arrête le programme immédiatement si la connexion échoue.

    def on_message(client, userdata, msg) : 
        try : #On essaie de décoder le message et de l'écrire dans la BDD.
            message = msg.payload.decode() #On décode le message reçu.
            #message est maintenant une str JSON.
            print("Message reçu sur le topic %s : %s" % (msg.topic, message))
            write_to_db(message) #On écrit le message dans la base de données.
            print("Le message a été écrit dans la base de données avec succès.")
        except Exception :
            print("L'écriture du message dans la base de données ou bien le décodage du message a échoué ")


    #On a défini les fonction callback, maintenant on crée le client MQTT et on configure les callbacks.
    client = mqtt.Client(client_id=client_id) #On crée un client MQTT
    client.on_connect = on_connect #On configure la fonction callback pour la connexion.
    client.on_message = on_message #On configure la fonction callback pour la réception des messages.
    client.connect(host, port) #On se connecte au broker.
    client.loop_forever() #On entre dans une boucle infinie pour écouter les messages. 

    #Fin du script.

if __name__ == "__main__" : #Pour exécuter le scipt directement 
    main_receive()
