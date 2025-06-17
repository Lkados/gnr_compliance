#!/bin/bash

# Définition des couleurs
ROUGE='\033[0;31m'
VERT='\033[0;32m'
JAUNE='\033[0;33m'
BLEU='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BLANC='\033[1;37m'
RESET='\033[0m'
GRAS='\033[1m'

# Fonction pour afficher un séparateur
separateur() {
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
}

# Fonction pour afficher une étape
etape() {
    echo -e "${JAUNE}[${CYAN}●${JAUNE}] ${BLANC}${GRAS}$1${RESET}"
}

# Fonction pour afficher un message de succès
succes() {
    echo -e "${VERT}[✓] $1${RESET}"
}

# Bannière de démarrage
separateur
echo -e "${CYAN}${GRAS}                                                                ${RESET}"
echo -e "${CYAN}${GRAS}    INSTALLATION GNR COMPLIANCE                            ${RESET}"
echo -e "${CYAN}${GRAS}                                                                ${RESET}"
separateur
echo ""

# Suppression des anciennes installations
etape "Suppression des installations précédentes..."

# Liste des conteneurs
CONTENEURS=(
    "erpnext-frontend-1"
    "erpnext-scheduler-1"
    "erpnext-websocket-1"
    "erpnext-queue-long-1"
    "erpnext-queue-short-1"
    "erpnext-backend-1"
)
# Nettoyer chaque conteneur
for CONTENEUR in "${CONTENEURS[@]}"; do
    echo -e "${BLEU}⟹ Nettoyage sur ${JAUNE}$CONTENEUR${RESET}"
    docker exec $CONTENEUR bash -c '
        rm -rf /home/frappe/frappe-bench/apps/gnr_compliance 2>/dev/null
        rm -rf /home/frappe/frappe-bench/apps/Josseaume-Energie-Calendar 2>/dev/null
        echo "Dossiers nettoyés"
    '
done

succes "Nettoyage des installations précédentes terminé"
echo ""

# Installation de l'application sur chaque conteneur
for CONTENEUR in "${CONTENEURS[@]}"; do
    etape "Installation sur ${CONTENEUR}..."
    echo -e "${BLEU}⟹ Exécution : ${JAUNE}docker exec ${CONTENEUR} bench get-app${RESET}"
    docker exec $CONTENEUR bench get-app https://github.com/Lkados/gnr_compliance
    succes "Installation sur ${CONTENEUR} terminée"
    echo ""
done

# Installation de l'app sur le site et migration
etape "Finalisation de l'installation..."
echo -e "${BLEU}⟹ Exécution : ${JAUNE}docker exec erpnext-backend-1 bench --site erp.josseaume-energies.com install-app${RESET}"
docker exec erpnext-backend-1 bench --site erp.josseaume-energies.com install-app josseaume_energies
succes "App josseaume_energies installée sur le site"

echo -e "${BLEU}⟹ Exécution : ${JAUNE}docker exec erpnext-backend-1 bench --site erp.josseaume-energies.com migrate${RESET}"
docker exec erpnext-backend-1 bench --site erp.josseaume-energies.com migrate
succes "Migration effectuée"
echo ""

# Redémarrage de tous les conteneurs
separateur
etape "Redémarrage de tous les conteneurs..."
echo -e "${ROUGE}⚠ Redémarrage des services en cours... ⚠${RESET}"
docker restart $(docker ps -q)
echo ""

# Fin du script
separateur
echo -e "${VERT}${GRAS}✅ INSTALLATION DE JOSSEAUME ENERGIES TERMINÉE AVEC SUCCÈS ! ✅${RESET}"
separateur
