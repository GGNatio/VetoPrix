"""
Gestion de la base de données SQLite locale.
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "vetoprix.db"


def get_connection() -> sqlite3.Connection:  # type: ignore
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Crée les tables si elles n'existent pas."""
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS imports (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date_import TEXT NOT NULL,
                filename    TEXT,
                nb_produits INTEGER,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS produits (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                code         TEXT,
                nom          TEXT NOT NULL,
                fabricant    TEXT,
                volume_ml    REAL,
                nb_comprimes INTEGER,
                type_forme   TEXT CHECK(type_forme IN ('liquide','comprimes','autre'))
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_produits_code ON produits(code);

            CREATE TABLE IF NOT EXISTS prix_historique (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                produit_id    INTEGER NOT NULL REFERENCES produits(id),
                import_id     INTEGER NOT NULL REFERENCES imports(id),
                prix_ht       REAL NOT NULL,
                tva           REAL,
                prix_par_unite REAL,
                UNIQUE(produit_id, import_id)
            );

            CREATE TABLE IF NOT EXISTS molecules (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                nom_dci TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS molecule_produits (
                molecule_id INTEGER NOT NULL REFERENCES molecules(id),
                produit_id  INTEGER NOT NULL REFERENCES produits(id),
                PRIMARY KEY (molecule_id, produit_id)
            );

            CREATE TABLE IF NOT EXISTS anmv_catalogue (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                nom          TEXT NOT NULL,
                laboratoire  TEXT,
                dci          TEXT,
                dci_norm     TEXT,
                especes      TEXT,
                forme        TEXT,
                numero_amm   TEXT,
                url_rcp      TEXT,
                date_scrape  TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_anmv_dci_norm ON anmv_catalogue(dci_norm);
        """)
    conn.close()
