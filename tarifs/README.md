# Tarifs Centravet

Place ici les fichiers CSV mensuels (`centravet_tarif_YYYYMMDD_….csv`).

Au démarrage, VetoPrix **importe automatiquement** les nouveaux fichiers
(ceux pas encore vus). Ils sont aussi inclus dans les releases GitHub :
après une MAJ sur les PC Windows de l’accueil, les nouveaux tarifs
arrivent sans import manuel.

## Workflow typique

1. Copier le nouveau CSV dans ce dossier
2. Incrémenter `VERSION` (ex. `0.2.0` → `0.2.1`)
3. `git add tarifs/ VERSION && git commit && git push`
4. Créer un tag `v0.2.1` (ou une Release GitHub) → Actions build le zip Windows
5. Sur les PC : ouvrir VetoPrix → accepter la MAJ → tarifs importés au prochain lancement
