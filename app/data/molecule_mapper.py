"""
Synchronisation molécules → produits Centravet via données ANMV.
"""
import re
import unicodedata
from app.database.db import get_connection


def _normalize(text):
    text = text.lower().strip()
    text = unicodedata.normalize('NFD', text)
    return ''.join(c for c in text if unicodedata.category(c) != 'Mn')


def _extract_brand_keyword(nom_anmv):
    """
    Premier mot du nom commercial (= marque).
    Gère les codes type « T 61 » → « t61 ». Ignore les marques trop courtes
    (< 3 car.) qui provoqueraient des faux positifs via LIKE '%x%'.
    """
    parts = [p for p in re.split(r'[\s,]+', nom_anmv.strip()) if p]
    if not parts:
        return ''
    word = parts[0]
    # « T 61 … » → coller lettre + chiffres
    if len(word) <= 2 and len(parts) > 1 and parts[1][:1].isdigit():
        word = word + parts[1]
    word = _normalize(word)
    if len(word) < 3:
        return ''
    return word


def sync_molecules_from_anmv():
    """
    Construit dynamiquement la table molecules + molecule_produits
    à partir du catalogue ANMV déjà scrapé dans anmv_catalogue.

    Algorithme :
      - Pour chaque ligne ANMV, décomposer la DCI en molécules unitaires
      - Pour chaque molécule, trouver les produits Centravet dont le nom
        contient la marque du médicament ANMV (premier mot du nom commercial)
      - Lier en DB
    """
    conn = get_connection()

    # Récupérer le catalogue ANMV
    anmv_rows = conn.execute(
        "SELECT nom, dci FROM anmv_catalogue WHERE dci != ''"
    ).fetchall()

    if not anmv_rows:
        conn.close()
        return 0  # Pas encore scrapé

    # Construire mapping dci_norm → set(brand_keywords)
    from collections import defaultdict
    dci_to_brands = defaultdict(set)

    for row in anmv_rows:
        nom = row['nom']
        dci_raw = row['dci']
        brand = _extract_brand_keyword(nom)
        if not brand:
            continue
        # Décomposer les DCI multiples
        for part in dci_raw.split(','):
            part = part.strip()
            if not part:
                continue
            # Nettoyer dosages: "Méloxicam 5mg" → "meloxicam"
            dci_clean = re.sub(r'\s+\d[\d,./\s]*(?:mg|µg|ui|%|ml).*$', '', part, flags=re.I).strip()
            dci_norm = _normalize(dci_clean)
            if dci_norm and len(dci_norm) > 2:
                dci_to_brands[dci_norm].add(brand)

    nb_linked = 0
    with conn:
        for dci_norm, brands in dci_to_brands.items():
            # Upsert molécule (stocker le nom DCI normalisé)
            conn.execute(
                "INSERT OR IGNORE INTO molecules (nom_dci) VALUES (?)", (dci_norm,)
            )
            mol_row = conn.execute(
                "SELECT id FROM molecules WHERE nom_dci=?", (dci_norm,)
            ).fetchone()
            mol_id = mol_row['id']

            # Trouver les produits Centravet dont le nom contient la marque
            # (en début de mot pour limiter les sous-chaînes accidentelles)
            for brand in brands:
                if len(brand) < 3:
                    continue
                produits = conn.execute(
                    "SELECT id FROM produits WHERE "
                    "LOWER(nom) LIKE ? OR LOWER(nom) LIKE ?",
                    (f'{brand}%', f'% {brand}%')
                ).fetchall()
                for p in produits:
                    conn.execute(
                        "INSERT OR IGNORE INTO molecule_produits (molecule_id, produit_id) VALUES (?,?)",
                        (mol_id, p['id'])
                    )
                    nb_linked += 1

    conn.close()
    return nb_linked


def sync_molecules_to_db():
    """Alias conservé pour compatibilité — utilise exclusivement le catalogue ANMV."""
    return sync_molecules_from_anmv()

