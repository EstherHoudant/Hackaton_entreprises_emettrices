#!/usr/bin/env python3
"""
extract_icpe.py — Extraction automatisée des données ICPE depuis Géorisques
Récupère la liste de tous les établissements via l'API, télécharge les fichiers
Excel associés et les consolide en un seul CSV.

Usage:
    python extract_icpe.py

Dépendances:
    pip install requests pandas xlrd tqdm
"""

import os
import sys
import time
import logging
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

import config

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler("extract_icpe.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ── 1. Récupération de la liste des établissements ────────────────────────────

def fetch_etablissements() -> list[dict]:
    """
    Interroge l'API Géorisques page par page et retourne la liste complète
    des établissements ICPE selon les filtres définis dans config.py.
    """
    etablissements = []
    page = 1
    page_size = 1000
    total = None
    session = requests.Session()

    log.info("Récupération de la liste des établissements depuis l'API Géorisques…")

    while True:
        params = {
            "page": page,
            "page_size": page_size,
        }

        # Filtres optionnels
        if config.FILTRE_DEPARTEMENT:
            params["code_departement"] = config.FILTRE_DEPARTEMENT
        if config.FILTRE_REGIME:
            params["regime"] = config.FILTRE_REGIME
        if config.FILTRE_SEVESO:
            params["seveso"] = config.FILTRE_SEVESO
        if config.FILTRE_IED is not None:
            params["ied"] = str(config.FILTRE_IED).lower()

        try:
            resp = session.get(config.API_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.error(f"Erreur API page {page}: {e}")
            break

        # Gestion des différents formats de réponse de l'API Géorisques
        records = []
        if isinstance(data, dict):
            records = data.get("data", data.get("results", data.get("features", [])))
            if total is None:
                total = data.get("total", data.get("count", "?"))
        elif isinstance(data, list):
            records = data

        if not records:
            break

        etablissements.extend(records)
        log.info(f"  Page {page} — {len(etablissements)} établissements récupérés (total: {total})")

        if config.MAX_ETABLISSEMENTS and len(etablissements) >= config.MAX_ETABLISSEMENTS:
            etablissements = etablissements[: config.MAX_ETABLISSEMENTS]
            log.info(f"  Limite MAX_ETABLISSEMENTS={config.MAX_ETABLISSEMENTS} atteinte.")
            break

        if len(records) < page_size:
            break

        page += 1
        time.sleep(config.REQUEST_DELAY)

    log.info(f"  → {len(etablissements)} établissements à traiter.")
    return etablissements


def extract_id(etab: dict) -> str | None:
    """Extrait l'identifiant numérique de l'établissement depuis la réponse API."""
    for key in ("num_etablissement", "id", "identifiant", "numEtablissement",
                "properties", "code_s3ic"):
        val = etab.get(key)
        if val and isinstance(val, dict):  # GeoJSON feature
            return extract_id(val)
        if val and str(val).strip():
            return str(val).strip().zfill(10)
    return None


# ── 2. Téléchargement des fichiers Excel ──────────────────────────────────────

def download_xls(num_etab: str, session: requests.Session) -> Path | None:
    """
    Télécharge le fichier XLS d'un établissement et le sauvegarde dans
    XLS_CACHE_DIR. Retourne le chemin du fichier ou None en cas d'échec.
    """
    cache_dir = Path(config.XLS_CACHE_DIR)
    cache_dir.mkdir(exist_ok=True)
    dest = cache_dir / f"{num_etab}.xls"

    if dest.exists():
        return dest  # Déjà téléchargé

    url = config.XLS_URL_TEMPLATE.format(num=num_etab)

    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=30, allow_redirects=True)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            return dest
        except requests.RequestException as e:
            if attempt < config.MAX_RETRIES:
                time.sleep(2 ** attempt)
            else:
                log.warning(f"  Échec téléchargement {num_etab} après {config.MAX_RETRIES} tentatives: {e}")
                return None


def download_worker(args):
    """Worker utilisé par ThreadPoolExecutor."""
    num_etab, session = args
    time.sleep(config.REQUEST_DELAY)
    return num_etab, download_xls(num_etab, session)


# ── 3. Extraction et normalisation des feuilles Excel ─────────────────────────

def parse_entete(df_raw: pd.DataFrame) -> dict:
    """
    Transforme la feuille 'Entete' (format clé/valeur vertical)
    en un dictionnaire plat.
    """
    result = {}
    for _, row in df_raw.iterrows():
        # La colonne 1 contient le label, la colonne 2 la valeur
        if len(row) >= 3:
            label = str(row.iloc[1]).strip().rstrip(":").strip() if pd.notna(row.iloc[1]) else ""
            valeur = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
            if label and label.lower() not in ("nan", ""):
                # Normalise le nom de colonne
                col = (label
                       .lower()
                       .replace("é", "e").replace("è", "e").replace("ê", "e")
                       .replace("à", "a").replace("â", "a")
                       .replace("î", "i").replace("ô", "o").replace("ù", "u")
                       .replace(" ", "_").replace("'", "_").replace("(", "")
                       .replace(")", "").replace("/", "_").replace(":", "")
                       .replace(",", "").strip("_"))
                result[f"entete_{col}"] = valeur
    return result


def parse_situation_admin(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Transforme la feuille 'Situation administrative' (tableau)
    en DataFrame normalisé.
    """
    if df_raw.empty:
        return pd.DataFrame()

    # La première ligne non-vide est le header
    df = df_raw.copy()

    # Cherche la ligne d'en-tête (contient "Code rubrique")
    header_idx = None
    for i, row in df.iterrows():
        row_vals = [str(v).strip() for v in row if pd.notna(v)]
        if any("rubrique" in v.lower() for v in row_vals):
            header_idx = i
            break

    if header_idx is None:
        # Pas de header trouvé, on utilise la première ligne
        header_idx = 0

    raw_headers = list(df.iloc[header_idx])
    # Supprime la première colonne si elle est vide/NaN (artefact du format Géorisques)
    if raw_headers and (not str(raw_headers[0]).strip() or str(raw_headers[0]).strip().lower() == "nan"):
        raw_headers = raw_headers[1:]
        # Supprime aussi la colonne correspondante dans les données
        df = df.iloc[:, 1:]
    headers = [str(v).strip() if pd.notna(v) else f"col_{j}"
               for j, v in enumerate(raw_headers)]
    headers = [h for h in headers if h and h.lower() != "nan"]

    data_rows = df.iloc[header_idx + 1 :].dropna(how="all")

    if data_rows.empty:
        return pd.DataFrame()

    # Aligne les colonnes
    n_headers = len(headers)
    result_rows = []
    for _, row in data_rows.iterrows():
        vals = [str(v).strip() if pd.notna(v) else "" for v in row]
        # Supprime la première colonne si elle est vide (artefact du format)
        if vals and vals[0] == "":
            vals = vals[1:]
        # Tronque ou complète selon le nombre de colonnes
        vals = (vals + [""] * n_headers)[:n_headers]
        result_rows.append(dict(zip(headers, vals)))

    df_out = pd.DataFrame(result_rows)
    # Renomme les colonnes
    df_out.columns = [
        c.lower()
        .replace("é", "e").replace("è", "e").replace("ê", "e")
        .replace("à", "a").replace("â", "a")
        .replace(" ", "_").replace("'", "_").replace("(", "")
        .replace(")", "").replace("/", "_")
        for c in df_out.columns
    ]
    return df_out


def parse_derniere_inspection(df_raw: pd.DataFrame) -> str | None:
    """
    Transforme la feuille 'Inspections' et retourne la date de la
    dernière inspection (la plus récente), au format YYYY-MM-DD.
    Retourne None si la feuille est vide ou ne contient aucune date exploitable.
    """
    if df_raw.empty:
        return None

    # Repère la ligne d'en-tête (qui contient "Date Inspection"),
    # puis la colonne juste après pour récupérer les dates.
    header_idx = None
    date_col = None
    for i, row in df_raw.iterrows():
        for j, v in enumerate(row):
            if pd.notna(v) and "date" in str(v).strip().lower():
                header_idx = i
                date_col = j
                break
        if header_idx is not None:
            break

    if header_idx is None or date_col is None:
        return None

    dates = pd.to_datetime(
        df_raw.iloc[header_idx + 1 :, date_col], errors="coerce"
    ).dropna()

    if dates.empty:
        return None

    return dates.max().strftime("%Y-%m-%d")


def parse_xls(path: Path, num_etab: str) -> list[dict]:
    """
    Lit le fichier XLS, extrait toutes les feuilles et retourne
    une liste de lignes (une par rubrique ICPE, avec les métadonnées entete).
    """
    try:
        xl = pd.ExcelFile(str(path), engine="xlrd")
    except Exception as e:
        log.warning(f"  Impossible de lire {path}: {e}")
        return []

    feuilles_dispo = xl.sheet_names
    feuilles_a_lire = config.FEUILLES or feuilles_dispo

    entete_data = {}
    autres_data = {}

    for feuille in feuilles_a_lire:
        if feuille not in feuilles_dispo:
            continue
        try:
            df_raw = pd.read_excel(str(path), sheet_name=feuille,
                                   engine="xlrd", header=None)
        except Exception as e:
            log.warning(f"  Erreur lecture feuille '{feuille}' de {path}: {e}")
            continue

        if feuille.lower() == "entete":
            entete_data = parse_entete(df_raw)
        elif feuille.lower() == "inspections":
            entete_data["derniere_date_inspection"] = parse_derniere_inspection(df_raw)
        else:
            df_parsed = parse_situation_admin(df_raw)
            if not df_parsed.empty:
                autres_data[feuille] = df_parsed

    # Construit les lignes de sortie
    lignes = []
    base = {"num_etablissement": num_etab, **entete_data}

    if autres_data:
        for feuille, df in autres_data.items():
            for _, row in df.iterrows():
                ligne = {**base}
                for col, val in row.items():
                    ligne[f"{feuille.lower().replace(' ', '_')}_{col}"] = val
                lignes.append(ligne)
    else:
        # Pas de données tabulaires, on sauvegarde quand même le header
        lignes.append(base)

    return lignes


# ── 4. Pipeline principal ─────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("  Extraction ICPE Géorisques")
    log.info("=" * 60)

    # — Étape 1 : Récupérer les identifiants
    etablissements = fetch_etablissements()
    if not etablissements:
        log.error("Aucun établissement récupéré. Vérifiez la config et la connexion.")
        sys.exit(1)

    ids = [extract_id(e) for e in etablissements]
    ids = [i for i in ids if i]
    log.info(f"{len(ids)} identifiants valides extraits.")

    # — Étape 2 : Télécharger les XLS en parallèle
    log.info(f"Téléchargement des fichiers XLS (workers={config.WORKERS})…")
    session = requests.Session()
    session.headers.update({"User-Agent": "ICPE-Extractor/1.0 (étude empreinte énergétique)"})

    xls_paths = {}
    args = [(num_id, session) for num_id in ids]

    with ThreadPoolExecutor(max_workers=config.WORKERS) as executor:
        futures = {executor.submit(download_worker, a): a[0] for a in args}
        for future in tqdm(as_completed(futures), total=len(futures),
                           desc="Téléchargement", unit="fichier"):
            num_id, path = future.result()
            if path:
                xls_paths[num_id] = path

    log.info(f"  → {len(xls_paths)}/{len(ids)} fichiers téléchargés avec succès.")

    # — Étape 3 : Parser les XLS et agréger
    log.info("Extraction et consolidation des données…")
    all_rows = []

    for num_id, path in tqdm(xls_paths.items(), desc="Extraction", unit="fichier"):
        rows = parse_xls(path, num_id)
        all_rows.extend(rows)

    if not all_rows:
        log.error("Aucune donnée extraite. Vérifiez le format des fichiers XLS.")
        sys.exit(1)

    # — Étape 4 : Sauvegarder en CSV
    df_final = pd.DataFrame(all_rows)

    # Colonnes souhaitées : infos légales + codes ICPE + volume
    COLONNES_SOUHAITEES = [
        # Identifiant
        "num_etablissement",
        # Infos légales
        "entete_nom",
        "entete_siret",
        "entete_etat_d_activite",
        "entete_regime_en_vigueur_de_l_etablissement_2",
        "entete_statut_seveso",
        "entete_ied_-_mtd",
        "derniere_date_inspection",
        # Rubriques ICPE
        "situation_administrative_code_rubrique",
        "situation_administrative_alinea",
        "situation_administrative_libelle_rubrique",
        "situation_administrative_regime_autorise",
        "situation_administrative_volume",
    ]
    colonnes_presentes = [c for c in COLONNES_SOUHAITEES if c in df_final.columns]
    df_final = df_final[colonnes_presentes]

    df_final.to_csv(config.OUTPUT_CSV, index=False, encoding="utf-8-sig")

    log.info(f"\n✓ CSV sauvegardé : {config.OUTPUT_CSV}")
    log.info(f"  {len(df_final)} lignes × {len(df_final.columns)} colonnes")
    log.info(f"  Établissements traités : {df_final['num_etablissement'].nunique()}")
    log.info("\nAperçu des colonnes :")
    for col in df_final.columns[:20]:
        log.info(f"  - {col}")
    if len(df_final.columns) > 20:
        log.info(f"  ... et {len(df_final.columns) - 20} autres colonnes")


def get_ids_from_csv(file_path):
    df= pd.read_csv(file_path, sep=";")
    num_etab = df["Numéro d'établissement"].astype(str)
    df['id'] = num_etab.str.rjust(10, '0')
    return df['id']

if __name__ == "__main__":
    # 1. Chargement de la liste locale
    log.info("Chargement de la liste locale des identifiants d'établissements...")
    mes_ids = get_ids_from_csv("export.csv")
    
    # On utilise une clé que la fonction `extract_id` sait lire (ex: "identifiant")
    etablissements = [{"identifiant": num_id} for num_id in mes_ids]
    log.info(f"→ {len(etablissements)} établissements configurés manuellement.")

    # Extraction et nettoyage des IDs valides
    ids = [extract_id(e) for e in etablissements]
    ids = [i for i in ids if i]
    log.info(f"{len(ids)} identifiants valides extraits.")

    # — Étape 2 : Téléchargement des fichiers XLS (Correction ici)
    log.info(f"Début du téléchargement des fichiers Excel (workers={config.WORKERS})…")
    session = requests.Session()
    session.headers.update({"User-Agent": "ICPE-Extractor/1.0 (étude empreinte énergétique)"})

    xls_paths = {}
    args = [(num_id, session) for num_id in ids]

    # Utilisation correcte du ThreadPoolExecutor comme dans main()
    with ThreadPoolExecutor(max_workers=config.WORKERS) as executor:
        futures = {executor.submit(download_worker, a): a[0] for a in args}
        for future in tqdm(as_completed(futures), total=len(futures),
                           desc="Téléchargement", unit="fichier"):
            num_id, path = future.result()
            if path:
                xls_paths[num_id] = path

    log.info(f"→ {len(xls_paths)}/{len(ids)} fichiers téléchargés avec succès.")

    # — Étape 3 : Parser les XLS et agréger
    log.info("Extraction et consolidation des données…")
    all_rows = []
    for num_id, path in tqdm(xls_paths.items(), desc="Extraction", unit="fichier"):
        rows = parse_xls(path, num_id)
        all_rows.extend(rows)

    if not all_rows:
        log.error("Aucune donnée extraite. Vérifiez le format des fichiers XLS.")
        sys.exit(1)

    # — Étape 4 : Sauvegarder en CSV
    df_final = pd.DataFrame(all_rows)

    # Colonnes souhaitées : infos légales + codes ICPE + volume
    COLONNES_SOUHAITEES = [
        "num_etablissement",
        "entete_nom",
        "entete_siret",
        "entete_etat_d_activite",
        "entete_regime_en_vigueur_de_l_etablissement_2",
        "entete_statut_seveso",
        "entete_ied_-_mtd",
        "derniere_date_inspection",
        "situation_administrative_code_rubrique",
        "situation_administrative_alinea",
        "situation_administrative_libelle_rubrique",
        "situation_administrative_regime_autorise",
        "situation_administrative_volume",
    ]
    colonnes_presentes = [c for c in COLONNES_SOUHAITEES if c in df_final.columns]
    df_final = df_final[colonnes_presentes]

    df_final.to_csv(config.OUTPUT_CSV, index=False, encoding="utf-8-sig")
    log.info(f"\n✓ CSV sauvegardé : {config.OUTPUT_CSV}")

# Nettoyage du csv enregistré
df = pd.read_csv("output_icpe.csv", dtype={'entete_siret': str})
df = df.dropna(subset=['situation_administrative_code_rubrique'])
num_etab = df["num_etablissement"].astype(str)
df['situation_administrative_code_rubrique'] = df['situation_administrative_code_rubrique'].astype(int)
df['num_etablissement'] = num_etab.str.rjust(10, '0')
df.to_csv("output_icpe_clean.csv", index=False)
print("Le CSV a été nettoyé et enregisté avec succès ! ;)")