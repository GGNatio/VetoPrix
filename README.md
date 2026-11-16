# VetoPrix

Comparateur de prix de médicaments vétérinaires (tarifs Centravet + catalogue ANMV).

## Pour l’accueil (Windows) — sans Python

1. Télécharger **`VetoPrix-windows.zip`** sur  
   https://github.com/GGNatio/VetoPrix/releases
2. Dézipper → lancer `VetoPrix.exe`
3. Les mises à jour (nouvel exe + nouveaux tarifs) se proposent au démarrage

Guide complet : [docs/DISTRIBUTION.md](docs/DISTRIBUTION.md)

## Publier un nouveau tarif (toi)

```bash
cp /chemin/centravet_tarif_YYYYMMDD_….csv tarifs/
echo "0.2.1" > VERSION          # incrémenter
git add tarifs VERSION && git commit -m "Tarif mois…" && git push
git tag v0.2.1 && git push origin v0.2.1
```

→ GitHub Actions fabrique le zip Windows et l’attache à la release.

## Dev local (Mac / Python)

```bash
pip install -r requirements.txt
python3 main.py
# ou ./lancer.command
```

Build Mac embarqué : `./build_mac.sh` → `dist/VetoPrix.app`

## Fonctionnalités

- Import CSV Centravet (historique, pas d’écrasement) + **auto-import** du dossier `tarifs/`
- Recherche molécule / mot-clé, €/ml
- Sync ANMV, statistiques
- MAJ à distance via GitHub Releases (app Windows + tarifs)

## Structure utile

```
VERSION                 # version locale (doit matcher le tag GitHub)
tarifs/                 # CSV livrés aux PC via les releases
.github/workflows/      # build Windows automatique
app/update/             # vérif + téléchargement releases
```
