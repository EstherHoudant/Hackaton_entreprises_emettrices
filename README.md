## Manuel d'utilisation du projet


Pré-requis : 
- tous les fichiers du git
- le fichier StockEtablissement_utf8.csv


Partie extraction :   
Il suffit de copier le dossier puis de lancer le script pour réaliser l'extraction des données pour chaque entreprise sur internet. On récupère alors le fichier output_icpe_clean.csv utilisé dans la suite.
ATTENTION ! l'execution du programme prend entre 4 et 5h et ne peut être mis en pause.
Pour éviter de relancer le programme à chaque fois, le fichier output_icpe_clean.csv est le résultat obtenu le 30/06/26


Etablissement des bases de données : 
Pour obtenir les bases de données, il suffit de lancer le notebook Traitement_donnees_EDF.ipynb. 
ATTENTION ! le fichier StockEtablissement_utf8.csv est à ajouter à la main dans le bon dossier (ne peut être mis sur git car trop volumineux)
Le fichier est téléchargeable sur ce lien : https://static.data.gouv.fr/resources/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/20260701-092157/stock-stocketablissement-csv.zip


Vérification des numéros de Siret : 
Il suffit de lancer le notebook Lecture_de_doc.ipynb pour obtenir une colonne validant ou non les codes Siret. 
Il faut cependant avoir déjà lancé les notebook précédent car les fichiers obtenus en lancant les notebook sont nécessaires à l'execution de ce notebook.

```python

```
