"""
Import et parsing du fichier CSV Centravet.
"""
import re
import sqlite3
from pathlib import Path
from datetime import date
from typing import Optional
from app.database.db import get_connection

# Regex pour extraire le volume depuis le nom du produit
_RE_MULTI = re.compile(r'(\d+)\s*[xX]\s*(\d+[\.,]?\d*)\s*ml', re.I)
_RE_SINGLE_ML = re.compile(r'(\d+[\.,]?\d*)\s*ml', re.I)
_RE_LITER = re.compile(r'(\d+[\.,]?\d*)\s*[Ll]\b')
_RE_COMPRIMES = re.compile(r'(\d+)\s*comprim', re.I)
_RE_GELULES = re.compile(r'(\d+)\s*g[eé]lule', re.I)


def extract_volume(nom: str) -> tuple:
    """
    Retourne (volume_ml, nb_comprimes, type_forme).
    """
    m = _RE_MULTI.search(nom)
    if m:
        vol = float(m.group(1)) * float(m.group(2).replace(',', '.'))
        return round(vol, 3), None, 'liquide'

    m = _RE_SINGLE_ML.search(nom)
    if m:
        vol = float(m.group(1).replace(',', '.'))
        return round(vol, 3), None, 'liquide'

    m = _RE_LITER.search(nom)
    if m:
        vol = float(m.group(1).replace(',', '.')) * 1000
        return round(vol, 3), None, 'liquide'

    m = _RE_COMPRIMES.search(nom) or _RE_GELULES.search(nom)
    if m:
        return None, int(m.group(1)), 'comprimes'

    return None, None, 'autre'


def parse_csv_line(line: str) -> Optional[dict]:
    """Parse une ligne du CSV Centravet. Retourne None si non médicament."""
    parts = line.strip().split(';')
    if len(parts) < 21:
        return None
    if parts[6].strip() != 'MED':
        return None

    code = parts[0].strip()
    nom = parts[5].strip()
    fabricant = parts[10].strip()
    try:
        tva = float(parts[17].strip())
    except ValueError:
        tva = 20.0
    try:
        prix_ht = float(parts[19].strip())
    except ValueError:
        return None

    if prix_ht <= 0 or not nom:
        return None

    volume_ml, nb_comprimes, type_forme = extract_volume(nom)

    if volume_ml and volume_ml > 0:
        prix_par_unite = round(prix_ht / volume_ml, 6)
    elif nb_comprimes and nb_comprimes > 0:
        prix_par_unite = round(prix_ht / nb_comprimes, 6)
    else:
        prix_par_unite = None

    return {
        'code': code,
        'nom': nom,
        'fabricant': fabricant,
        'tva': tva,
        'prix_ht': prix_ht,
        'volume_ml': volume_ml,
        'nb_comprimes': nb_comprimes,
        'type_forme': type_forme,
        'prix_par_unite': prix_par_unite,
    }


def import_csv(filepath: str, import_date: Optional[str] = None) -> dict:
    """
    Importe un fichier CSV Centravet dans la base de données.
    Retourne un dict avec les statistiques d'import.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")

    if import_date is None:
        # Tenter d'extraire la date du nom de fichier (ex: centravet_tarif_20260501_...)
        m = re.search(r'(\d{8})', filepath.name)
        if m:
            d = m.group(1)
            import_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        else:
            import_date = date.today().isoformat()

    with open(filepath, encoding='latin-1') as f:
        lines = f.readlines()

    # Dédoublonner par code : garder la première occurrence (prix unitaire, qté=1)
    seen_codes: set[str] = set()
    produits_parsed = []
    for line in lines:
        parsed = parse_csv_line(line)
        if parsed is None:
            continue
        if parsed['code'] in seen_codes:
            continue
        seen_codes.add(parsed['code'])
        produits_parsed.append(parsed)

    conn = get_connection()
    nb_nouveaux = 0
    nb_prix = 0

    with conn:
        # Créer l'entrée d'import
        cur = conn.execute(
            "INSERT INTO imports (date_import, filename, nb_produits) VALUES (?, ?, ?)",
            (import_date, filepath.name, len(produits_parsed))
        )
        import_id = cur.lastrowid

        for p in produits_parsed:
            # Upsert produit
            conn.execute("""
                INSERT INTO produits (code, nom, fabricant, volume_ml, nb_comprimes, type_forme)
                VALUES (:code, :nom, :fabricant, :volume_ml, :nb_comprimes, :type_forme)
                ON CONFLICT(code) DO UPDATE SET
                    nom=excluded.nom,
                    fabricant=excluded.fabricant,
                    volume_ml=excluded.volume_ml,
                    nb_comprimes=excluded.nb_comprimes,
                    type_forme=excluded.type_forme
            """, p)

            # Récupérer l'id du produit
            row = conn.execute("SELECT id FROM produits WHERE code=?", (p['code'],)).fetchone()
            produit_id = row['id']

            # Insérer le prix pour cet import
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO prix_historique
                        (produit_id, import_id, prix_ht, tva, prix_par_unite)
                    VALUES (?, ?, ?, ?, ?)
                """, (produit_id, import_id, p['prix_ht'], p['tva'], p['prix_par_unite']))
                nb_prix += 1
            except sqlite3.IntegrityError:
                pass

        nb_nouveaux = len(produits_parsed)

    conn.close()
    return {
        'import_id': import_id,
        'date_import': import_date,
        'nb_produits': nb_nouveaux,
        'nb_prix': nb_prix,
    }
