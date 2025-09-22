"""
Le but de ce module est de définir un ensemble de classes pour les configurations météo.
Les classes sont :
Position : elle encapsule la latitude, longitude, altitude, fuseau horaire
Requetes : paramètres de l'horizon, pas de temps, fréquences de mise à jour
Features : encapsule les bool des fonctionnalités
Features_details : appelé si une fonctionnalité utilisée, afin de donner les détails sur ces fonctionnalités.
panneau_pvlib : stocke les configs des panneaux si on souhaite utiliser PVlib
panneau_basic : stocke les configs de rendement global, surface et infos panneaux d'orientation... 
Auteur : @anaselb
"""
#IMPORTANT !!!!!!!!!!!!!!!! : IL FAUT AJOUTER ICI LA LOGIQUE INTERNE DE CHAQUE CLASSE 
#------------------------------------------------------------------------------------
class Position :
    def __init__(self, latitude, longitude, altitude, timezone = "Europe/Paris") :
        self.latitude = latitude      #En degrés décimales
        self.longitude = longitude # En degrés décimales
        self.altitude = altitude # En mètres
        self.timezone = timezone    #"Europe/Paris" c'est le seul fuseau dans lequel on travaille.

class Requetes :
    def __init__(self, horizon = 36, pas_temps = 15, frequence_rafraichissement = 240) :
        self.horizon = horizon                                          #Horieon des prévisions APIs
        self.pas_temps = pas_temps                                      #Pas de temps dans les prévisions
        self.frequence_rafraichissement = frequence_rafraichissement    #Fréquence de mises à jour météo (en minutes)

class Features : 
    class Features_details :
        def __init__(self, fournisseur : str = None , auto_fournisseur : str = None , cle_API : str = None) :
            self.fournisseur = fournisseur            #Si selection_fournisseur est true, ici on indique ce que c'est ce fournisseur
            self.auto_fournisseur = auto_fournisseur  #Si auto_fournisseur est activé, ici on indique lequel des autofournisseurs est activé
            self.cle_API = cle_API                    #La clé API si l'auto fournisseur est activé.
    
    def __init__(self, selection_fournisseur : bool , ajusteur_ranking : bool, ajusteur_parametres : bool , fournisseur_propre_auto : bool, saisie_manuelle : bool, IA_feature : bool , details : Features_details) :
        self.selection_fournisseur = selection_fournisseur                          #true ou false selon si l'user choisit le fournisseur d'irradiance
        self.ajusteur_ranking = ajusteur_ranking                                    #true ou false si l'user veut qu'on adapte le classement 
        self.ajusteur_parametres = ajusteur_parametres  #true ou false si l'user veut qu'on adapte les coefficients d'efficacité 
        self.fournisseur_propre_auto = fournisseur_propre_auto                              #true ou false selon si l'user dispose d'un contrat avec API et veut gérer ça automatiquement
        self.saisie_manuelle = saisie_manuelle                                      #True ou false selon si l'utilisateur veut saisir à la main la production PV prévue.
        self.IA_feature = IA_feature     #true ou false sleon si surcouche correction AI activée ou non
        self.details = details                                            #C'est une instance de la classe Features_details, qui sera remplie si l'utilisateur utilise une des fonctionnalités.


class Installation_PV : # C'est la classe qui encapsule les infos de l'installation PV.
    class Panneau :
        def __init__(self, 
                     azimuth : float, 
                     tilt : float, 
                     surface_panneau : float | None = None, 
                     puissance_nominale : float | None = None
                     ) : 
            self.azimuth = azimuth                          #Azimuth du panneau
            self.tilt = tilt                                #Tilt du panneau 
            self.surface_panneau = surface_panneau          #Surface du panneau (utile si PVlib ne marche pas) 
            self.puissance_nominale = puissance_nominale    #Watts crête du panneau
               

    class Onduleur :
        def __init__(self,
                     plafond_puissance : float | None = None, 
                     efficacite_nominale : float | None = None,
                     pertes_cables : float | None = None
                     ) :
            self.plafond_puissance = plafond_puissance    #Clipping de l'induleur, nécessaire dans PVLIb
            self.efficacite_nominale = efficacite_nominale   #Efficacité nominale de l'onduleur
            self.pertes_cables = pertes_cables #Les pertes des câbles (entre 0 et 1) 
        
    def __init__(self, liste_panneaux : list[Panneau], onduleur : Onduleur, rendement_global : float | None = None) : 
        self.liste_panneaux = liste_panneaux  #C'est une liste d'instances de la classe panneau
        self.onduleur = onduleur              #C'est une instance de la classe onduleur 
        self.rendement_global = rendement_global        #rendement global de l'installation (utilisable si PVLib ne marche pas   

