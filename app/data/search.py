"""
Recherche de produits par molécule ou mot-clé, avec comparaison de prix.
"""
from app.database.db import get_connection


def search_by_keyword(keyword: str, import_id=None) -> list:
    """
    Recherche les médicaments dont le nom contient le mot-clé.
    Si import_id est None, utilise le dernier import disponible.
    Retourne une liste de dicts triés par prix_par_unite ASC.
    """
    conn = get_connection()

    if import_id is None:
        row = conn.execute("SELECT id FROM imports ORDER BY date_import DESC LIMIT 1").fetchone()
        if row is None:
            conn.close()
            return []
        import_id = row['id']

    rows = conn.execute("""
        SELECT
            p.code,
            p.nom,
            p.fabricant,
            p.volume_ml,
            p.nb_comprimes,
            p.type_forme,
            ph.prix_ht,
            ph.tva,
            ROUND(ph.prix_ht * (1 + ph.tva / 100.0), 2) AS prix_ttc,
            ph.prix_par_unite,
            i.date_import,
            (SELECT COUNT(DISTINCT mp2.molecule_id)
             FROM molecule_produits mp2 WHERE mp2.produit_id = p.id) AS nb_molecules,
            (SELECT GROUP_CONCAT(mol.nom_dci, ' + ')
             FROM molecule_produits mp3
             JOIN molecules mol ON mol.id = mp3.molecule_id
             WHERE mp3.produit_id = p.id) AS molecules_dci
        FROM produits p
        JOIN prix_historique ph ON ph.produit_id = p.id
        JOIN imports i ON i.id = ph.import_id
        WHERE ph.import_id = ?
          AND p.nom LIKE ?
        ORDER BY
            CASE WHEN ph.prix_par_unite IS NULL THEN 1 ELSE 0 END,
            ph.prix_par_unite ASC
    """, (import_id, f'%{keyword}%')).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def search_by_molecule(molecule_id: int, import_id=None) -> list:
    """
    Recherche tous les produits liés à une molécule donnée.
    """
    conn = get_connection()

    if import_id is None:
        row = conn.execute("SELECT id FROM imports ORDER BY date_import DESC LIMIT 1").fetchone()
        if row is None:
            conn.close()
            return []
        import_id = row['id']

    rows = conn.execute("""
        SELECT
            p.code,
            p.nom,
            p.fabricant,
            p.volume_ml,
            p.nb_comprimes,
            p.type_forme,
            ph.prix_ht,
            ph.tva,
            ROUND(ph.prix_ht * (1 + ph.tva / 100.0), 2) AS prix_ttc,
            ph.prix_par_unite,
            i.date_import
        FROM produits p
        JOIN molecule_produits mp ON mp.produit_id = p.id
        JOIN prix_historique ph ON ph.produit_id = p.id
        JOIN imports i ON i.id = ph.import_id
        WHERE mp.molecule_id = ?
          AND ph.import_id = ?
        ORDER BY
            CASE WHEN ph.prix_par_unite IS NULL THEN 1 ELSE 0 END,
            ph.prix_par_unite ASC
    """, (molecule_id, import_id)).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def search_by_molecules(molecule_ids: list, import_id=None, mono_only: bool = False) -> list:
    """
    Recherche les produits liés à une OU plusieurs molécules.
    - molecule_ids : liste d'IDs de molécules (résultat = union)
    - mono_only    : si True, exclut les produits liés à plus d'une molécule
                     (associations fixes type amox+acide clav.)
    Retourne chaque produit une seule fois, avec nb_molecules indiquant
    combien de molécules sont associées au produit.
    """
    if not molecule_ids:
        return []

    conn = get_connection()

    if import_id is None:
        row = conn.execute("SELECT id FROM imports ORDER BY date_import DESC LIMIT 1").fetchone()
        if row is None:
            conn.close()
            return []
        import_id = row['id']

    placeholders = ','.join('?' * len(molecule_ids))
    having_clause = (
        "HAVING (SELECT COUNT(DISTINCT m2.molecule_id) "
        "        FROM molecule_produits m2 WHERE m2.produit_id = p.id) = 1"
        if mono_only else ""
    )

    rows = conn.execute(f"""
        SELECT
            p.code,
            p.nom,
            p.fabricant,
            p.volume_ml,
            p.nb_comprimes,
            p.type_forme,
            ph.prix_ht,
            ph.tva,
            ROUND(ph.prix_ht * (1 + ph.tva / 100.0), 2) AS prix_ttc,
            ph.prix_par_unite,
            i.date_import,
            (SELECT COUNT(DISTINCT m2.molecule_id)
             FROM molecule_produits m2 WHERE m2.produit_id = p.id) AS nb_molecules,
            (SELECT GROUP_CONCAT(mol.nom_dci, ' + ')
             FROM molecule_produits mp3
             JOIN molecules mol ON mol.id = mp3.molecule_id
             WHERE mp3.produit_id = p.id) AS molecules_dci
        FROM produits p
        JOIN molecule_produits mp ON mp.produit_id = p.id
        JOIN prix_historique ph   ON ph.produit_id = p.id
        JOIN imports i            ON i.id = ph.import_id
        WHERE mp.molecule_id IN ({placeholders})
          AND ph.import_id = ?
        GROUP BY p.id
        {having_clause}
        ORDER BY
            CASE WHEN ph.prix_par_unite IS NULL THEN 1 ELSE 0 END,
            ph.prix_par_unite ASC
    """, (*molecule_ids, import_id)).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def get_price_history(produit_code: str) -> list:
    """
    Retourne l'historique des prix d'un produit (toutes les dates d'import).
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            i.date_import,
            ph.prix_ht,
            ph.tva,
            ROUND(ph.prix_ht * (1 + ph.tva / 100.0), 2) AS prix_ttc,
            ph.prix_par_unite
        FROM prix_historique ph
        JOIN imports i ON i.id = ph.import_id
        JOIN produits p ON p.id = ph.produit_id
        WHERE p.code = ?
        ORDER BY i.date_import ASC
    """, (produit_code,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_molecules() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT id, nom_dci FROM molecules ORDER BY nom_dci").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_imports() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, date_import, filename, nb_produits FROM imports ORDER BY date_import DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_global_price_trend() -> list:
    """
    Retourne le prix moyen par ml (médicaments liquides uniquement) par date d'import.
    Permet d'observer la hausse globale des coûts.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            i.date_import,
            ROUND(AVG(ph.prix_par_unite), 4) AS prix_moyen_par_ml,
            COUNT(*) AS nb_produits
        FROM prix_historique ph
        JOIN imports i ON i.id = ph.import_id
        JOIN produits p ON p.id = ph.produit_id
        WHERE p.type_forme = 'liquide'
          AND ph.prix_par_unite IS NOT NULL
        GROUP BY i.date_import
        ORDER BY i.date_import ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
