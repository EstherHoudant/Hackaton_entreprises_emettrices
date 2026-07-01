# ============================================================
#  config.py — Paramètres à adapter avant de lancer le script
# ============================================================

# --- Fichier de sortie ---
OUTPUT_CSV = "output_icpe.csv"
XLS_CACHE_DIR = "xls_cache"       # Dossier où les .xls sont stockés localement

# --- API Géorisques ---
# Endpoint liste des établissements ICPE
API_URL = "https://www.georisques.gouv.fr/api/v1/installations_classees"

# URL de téléchargement d'un fichier Excel (remplacer {num} par l'id)
XLS_URL_TEMPLATE = "https://www.georisques.gouv.fr/webappReport/ws/installations/etablissement/{num}/excel"

# --- Filtres (laisser None pour ne pas filtrer) ---
# Régime : "Autorisation", "Enregistrement", "Déclaration", None
FILTRE_REGIME = None

# Département (code à 2 chiffres, ex: "75", "13", "69"), None = toute la France
FILTRE_DEPARTEMENT = None

# Statut SEVESO : "Seuil haut", "Seuil bas", None
FILTRE_SEVESO = None

# IED (directive émissions industrielles) : True, False, None
FILTRE_IED = None

# Nombre max d'établissements à traiter (None = tous)
MAX_ETABLISSEMENTS = None

# --- Performance ---
WORKERS = 4          # Téléchargements en parallèle
REQUEST_DELAY = 0.3  # Délai entre requêtes (secondes) — respecter le serveur
MAX_RETRIES = 3      # Nombre de tentatives en cas d'erreur

# --- Feuilles Excel à extraire ---
# Toutes les feuilles connues : "Entete", "Situation administrative"
# Mettre None pour extraire toutes les feuilles disponibles
FEUILLES = None  # ou ex: ["Entete", "Situation administrative"]
