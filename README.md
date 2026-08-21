# VetoPrix

Comparateur de prix de médicaments vétérinaires (tarifs Centravet + catalogue ANMV).

## Prérequis

- Python 3.9+
- Dépendances : `pip install -r requirements.txt`

## Lancer

```bash
cd VetoPrix
python3 main.py
```

## Fonctionnalités

- Import de tarifs CSV Centravet (historique des prix, pas d’écrasement)
- Recherche par molécule / mot-clé, comparaison €/ml
- Sync catalogue ANMV (IRCP)
- Statistiques d’évolution des prix
- **Mise à jour à distance** via GitHub Releases (bouton `MAJ` dans le header)

## Structure

```
VetoPrix/
├── main.py                 # Point d’entrée
├── update_helper.py        # Processus de MAJ (après fermeture de l’app)
├── VERSION                 # Version locale (ex: 0.1.0)
├── requirements.txt
├── app/
│   ├── config.py           # Config centralisée (repo GitHub, chemins…)
│   ├── update/             # Vérif + téléchargement des releases
│   ├── database/           # SQLite
│   ├── data/               # Import CSV, recherche, ANMV, mapping
│   └── ui/                 # Interface PyQt6
└── data/                   # DB locale (non versionnée) — préservée aux MAJ
```

## Mise à jour (dev)

1. Modifier le code
2. Incrémenter `VERSION` (ex: `0.1.0` → `0.1.1`)
3. Commit + push sur `main`
4. Créer une **GitHub Release** taguée `v0.1.1` (le tag doit correspondre à VERSION)
5. Les utilisateurs cliquent **MAJ** dans l’app

La base `data/vetoprix.db` n’est **jamais** écrasée.

> **Important** : si le dépôt est **privé**, l’API GitHub renvoie 404 sans token.
> - Soit tu passes le repo en **public** (le plus simple pour la MAJ),
> - Soit tu définis la variable d’environnement `VETOPRIX_GITHUB_TOKEN` (PAT en lecture).

## Packaging Windows (.exe)

Voir [docs/PACKAGING.md](docs/PACKAGING.md).
