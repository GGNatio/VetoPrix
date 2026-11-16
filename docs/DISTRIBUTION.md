# Distribution & mises à jour (accueil Windows)

## Vue d’ensemble

```
Toi (Mac)                    GitHub                         PC accueil (Windows)
─────────                    ──────                         ────────────────────
Ajoute CSV dans tarifs/  →   push + tag vX.Y.Z         →   bouton MAJ / auto-check
Bump VERSION                 Actions build .zip            télécharge VetoPrix-windows.zip
                             Release avec installateur     remplace l’app (garde data/)
                                                           importe les nouveaux CSV
```

## 1. Première installation sur un PC Windows

1. Va sur https://github.com/GGNatio/VetoPrix/releases
2. Télécharge **`VetoPrix-windows.zip`** (dernière release)
3. Dézippe dans un dossier stable, ex. `C:\VetoPrix\`
4. Lance `VetoPrix.exe`
5. (Optionnel) crée un raccourci Bureau

> Pas besoin d’installer Python.

## 2. Publier une nouvelle version (toi)

### Cas A — Nouveau tarif du mois

```bash
# 1. Copier le CSV Centravet
cp ~/Downloads/centravet_tarif_20261101_c_s_.csv tarifs/

# 2. Version
echo "0.2.1" > VERSION   # incrémenter

# 3. Commit + tag
git add tarifs VERSION
git commit -m "Tarif novembre 2026"
git push
git tag v0.2.1
git push origin v0.2.1
```

GitHub Actions compile automatiquement Windows et **attache** `VetoPrix-windows.zip` à la release `v0.2.1`.

### Cas B — Correction de code seulement

Même chose : bump `VERSION`, tag, push. Les tarifs déjà présents restent dans le zip.

## 3. Sur les PC de l’accueil

Au lancement (ou clic **MAJ**) :

1. L’app compare sa version à la dernière release GitHub
2. Si plus récente → **propose** la MAJ (pas forcée)
3. Télécharge `VetoPrix-windows.zip`, remplace les fichiers, **conserve `data/`** (historique)
4. Au redémarrage → import auto des CSV dans `tarifs/`

## 4. Vérifier le build Actions

https://github.com/GGNatio/VetoPrix/actions

Le job **Build Windows release** doit être vert ; le zip apparaît dans la release.

## Notes

- Repo **public** requis pour que les PC téléchargent sans token
- Les CSV hors `tarifs/` ne sont pas versionnés (gitignore)
- La base SQLite locale n’est jamais écrasée par une MAJ
