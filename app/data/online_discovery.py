"""
Scraping du catalogue ANMV (IRCP) — Base publique des médicaments vétérinaires autorisés en France.
Source : https://www.ircp.anmv.anses.fr/

Fournit :
  - scrape_anmv(progress_callback)  → scrape complet et mise en cache SQLite
  - get_anmv_by_dci(dci_keyword)    → produits en ligne pour une molécule
  - get_absent_from_catalog(dci_keyword) → produits ANMV absents du catalogue Centravet
  - get_last_scrape_date()          → date de la dernière sync
  - get_all_anmv_dci()              → liste unique de DCI disponibles en ligne
"""

import re
import html
import unicodedata
import urllib.request
import urllib.parse
from datetime import date
from typing import Optional

from app.database.db import get_connection

# ---------------------------------------------------------------------- #
#  Utilitaires                                                            #
# ---------------------------------------------------------------------- #

def normalize(text):
    """Minuscule + suppression des accents."""
    text = text.lower().strip()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text


def _extract_brand_keyword(nom_anmv):
    """
    Extrait le premier mot du nom commercial (= marque déposée).
    Gère les codes type « T 61 » → « t61 ». Ignore les marques < 3 car.
    (évite les faux positifs LIKE '%t%' sur tout le catalogue).
    """
    # Ex : "MELOSUS 0,5 MG/ML ..." → "melosus"
    parts = [p for p in re.split(r'[\s,]+', nom_anmv.strip()) if p]
    if not parts:
        return ''
    word = parts[0]
    if len(word) <= 2 and len(parts) > 1 and parts[1][:1].isdigit():
        word = word + parts[1]
    word = normalize(word)
    if len(word) < 3:
        return ''
    return word


def _http_get(url, timeout=12):
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'VetoPrix/1.0 (comparateur de prix vétérinaires)'}
    )
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp.read().decode('utf-8', errors='replace')


# ---------------------------------------------------------------------- #
#  Scraping ANMV                                                          #
# ---------------------------------------------------------------------- #

_LETTERS = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ') + ['0']
_BASE_URL = 'https://www.ircp.anmv.anses.fr/index.aspx'
_RCP_URL  = 'https://www.ircp.anmv.anses.fr/fiche.aspx?NomMedicament={}'


def _scrape_letter(letter):
    """Scrape une page lettre de l'IRCP. Retourne une liste de dicts."""
    url = f'{_BASE_URL}?letter={letter}'
    content = _http_get(url)
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', content, re.DOTALL)
    results = []
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) < 9:
            continue
        clean = [html.unescape(re.sub(r'<[^>]+>', '', c)).strip() for c in cells]
        nom = clean[2]
        if not nom:
            continue
        # Extraire le lien RCP depuis cell[2]
        link_m = re.search(r'href=["\']([^"\']*fiche\.aspx[^"\']*)["\']', cells[2], re.I)
        url_rcp = ''
        if link_m:
            url_rcp = 'https://www.ircp.anmv.anses.fr/' + html.unescape(link_m.group(1))

        dci_raw = clean[8] if len(clean) > 8 else ''
        results.append({
            'nom': nom,
            'laboratoire': clean[3] if len(clean) > 3 else '',
            'numero_amm': clean[4] if len(clean) > 4 else '',
            'forme': clean[7] if len(clean) > 7 else '',
            'dci': dci_raw,
            'dci_norm': normalize(dci_raw),
            'especes': clean[9] if len(clean) > 9 else '',
            'url_rcp': url_rcp,
        })
    return results


def scrape_anmv(progress_callback=None):
    """
    Scrape le catalogue ANMV complet (27 pages A-Z + 0-9).
    progress_callback(current, total, letter) appelé à chaque lettre.
    Retourne {'nb_produits': int, 'date': str}.
    """
    today = date.today().isoformat()
    conn = get_connection()

    with conn:
        # Vider l'ancien catalogue
        conn.execute("DELETE FROM anmv_catalogue")

        total_letters = len(_LETTERS)
        nb_total = 0

        for idx, letter in enumerate(_LETTERS):
            if progress_callback:
                progress_callback(idx, total_letters, letter)
            try:
                meds = _scrape_letter(letter)
                for m in meds:
                    conn.execute("""
                        INSERT INTO anmv_catalogue
                            (nom, laboratoire, dci, dci_norm, especes, forme, numero_amm, url_rcp, date_scrape)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        m['nom'], m['laboratoire'], m['dci'], m['dci_norm'],
                        m['especes'], m['forme'], m['numero_amm'],
                        m['url_rcp'], today
                    ))
                nb_total += len(meds)
            except Exception:
                pass  # Lettre non disponible, on continue

    if progress_callback:
        progress_callback(total_letters, total_letters, 'done')

    conn.close()
    return {'nb_produits': nb_total, 'date': today}


# ---------------------------------------------------------------------- #
#  Requêtes sur le catalogue en cache                                     #
# ---------------------------------------------------------------------- #

def get_last_scrape_date():
    """Retourne la date de la dernière sync ANMV, ou None."""
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT date_scrape FROM anmv_catalogue ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return row['date_scrape'] if row else None
    except Exception:
        return None


def get_all_anmv_dci():
    """
    Retourne la liste triée des DCI uniques présentes dans le catalogue ANMV.
    Chaque DCI peut contenir plusieurs substances (associations) séparées par virgule.
    On décompose pour obtenir des molécules unitaires.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT dci FROM anmv_catalogue WHERE dci != '' ORDER BY dci"
    ).fetchall()
    conn.close()

    # Décomposer les DCI multiples (ex: "Amoxicilline, Acide clavulanique")
    molecules = set()
    for row in rows:
        for part in row['dci'].split(','):
            part = part.strip()
            if part and len(part) > 2:
                # Nettoyer les dosages éventuels (ex: "Méloxicam 5mg")
                name = re.sub(r'\s+\d[\d,./\s]*(?:mg|µg|UI|%|ml).*$', '', part, flags=re.I).strip()
                if name:
                    molecules.add(name)

    return sorted(molecules)


def get_anmv_by_dci(dci_keyword):
    """
    Retourne les produits ANMV dont la DCI contient dci_keyword (insensible aux accents/casse).
    """
    try:
        kw_norm = normalize(dci_keyword)
        conn = get_connection()
        rows = conn.execute(
            "SELECT nom, laboratoire, dci, especes, forme, url_rcp FROM anmv_catalogue "
            "WHERE dci_norm LIKE ?",
            (f'%{kw_norm}%',)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_absent_from_catalog(dci_keyword):
    """
    Retourne les produits ANMV (pour cette DCI) qui ne sont PAS présents
    dans le catalogue Centravet importé.

    Logique de matching : si le premier mot du nom ANMV (la marque)
    se retrouve dans au moins un nom de produit Centravet → présent.
    Sinon → absent.

    Retourne une liste de dicts avec clés:
        nom, laboratoire, dci, especes, forme, url_rcp, brand_keyword
    """
    return [p for p in get_all_anmv_for_dci(dci_keyword) if not p['en_centrale']]


def get_all_anmv_for_dci(dci_keyword):
    """
    Retourne TOUS les produits ANMV pour cette DCI, chacun avec un champ
    'en_centrale' (bool) indiquant s'il est présent dans le catalogue Centravet.
    """
    anmv_products = get_anmv_by_dci(dci_keyword)
    if not anmv_products:
        return []

    try:
        conn = get_connection()
        rows = conn.execute("SELECT nom FROM produits").fetchall()
        conn.close()
        centravet_noms_norm = set(normalize(r['nom']) for r in rows)
    except Exception:
        centravet_noms_norm = set()

    result = []
    for p in anmv_products:
        brand = _extract_brand_keyword(p['nom'])
        # Présent si la marque apparaît en début de nom ou après un espace
        found = bool(
            brand and any(
                nom == brand or nom.startswith(brand + ' ') or f' {brand} ' in f' {nom} '
                for nom in centravet_noms_norm
            )
        )
        p['brand_keyword'] = brand
        p['en_centrale'] = found
        result.append(p)

    return result
