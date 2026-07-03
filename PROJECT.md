Explication du projet: 

L'enjeu de ce projet est de récupérer et de mettre sous un format facilement exploitable par EDF un ensemble de données disponibles en ligne concernant les entreprises françaises. Notre but premier était de parvenir à associer dans un unique fichier l'ensemble des codes ICPE de ces entreprises avec leur code NAF à cinq chiffes.Puis le second enjeu était de parvenir à récupérer les numéros d'inspection de chaque entreprise. Enfin, il fallait s'appuyer sur une liste de composants fournis par EDF pour ensuite caractériser les flux de matériaux au sein de chaque entreprise.

1) Acquisition d'une première base de données:
   On a tout d'abord récupéré sur le site georisques.gouv.fr un premier fichier au format csv contenant un ensemble d'informations sur les entreprises: nom, adresse, numéro ICPE, statut SEVESO,... On a récupéré un deuxième fichier sur ce même site qui recensait des informations complémentaires (coordonnées GPS, code NAF à deux chiffres, URL vers la fiche géorisques). On a donc procédé à une fusion des deux fichiers, en conservant l'exhaustitivité des données mais en éliminant les colonnes redondantes/communes aux deux fichiers. On a donc finalement obtenu une énorme base de données de 137 456 lignes, recensant des informations pécises sur l'ensemble des entreprises.

2) Récupération des codes NAF à cinq chiffres:
   L'enjeu était de récupérer un code NAF à cinq chiffres pour chaque numéro ICPE d'entreprise. Le code que nous avons mis en place automatise l'enrichissement de notre base de données ICPE en utilisant une approche par requêtes API et scraping web, grâce aux bibliothèques pandas : il parcourt chaque ligne du tableau, extrait le numéro SIRET pour interroger en temps réel l'API officielle de l'État (SIRENE) afin de récupérer le code NAF précis à 5 chiffres, et utilise simultanément une technique de scraping pour analyser le code source des pages Géorisques associées à chaque établissement pour y détecter et isoler des liens pointant vers des rapports d'inspection. On a donc récupéré une base de données associant chaque numéro ICPE à un code NAF à cinq chiffres et un numéro SIRET, et donnant l'adresse, la localisation GPS, le lien URL et le statut SEVESO.

3) Echec de la récupération du numéro d'inspection:
   Le code élaboré ne nous a pas permis de récupérer les numéros d'inspection. Ceux-ci sont en effet peu ou pas disponibles en ligne, ou alors dans des fichiers propres à chaque entreprise dont npus n'avons pas réussi à automatiser l'ouverture et la lecture.

4) Utilisation de la liste des composants:
   EDF nous a fourni une liste de composants chimiques, et le but est d'identifier les composants utilisés par chaque entreprise et d'en caractériser les flux (en entrée et sortie). 


# Workflow du projet : #

1) Extraire les données d'internet

• Les données Géorisques : 
- Le programme python extract_icpe.py dans le dossier extraction permet de collecter des fichiers excel propre à chaque entreprise sur le site du gouvernement géorisques. On obtient ainsi deux fichiers csv : output_icpe.csv (les données brutes) et output_icpe_clean.csv (le fichier .csv un peu nettoyé). ATTENTION : il faut quelques heures (envrion 4) pour que le programme charge toutes les données. C'est pourquoi dans ce notebook vous trouverez un fichier output.csv déjà présent pour vous éviter d'attendre. Mais si vous souhaitez une mise à jour de certaines données, il suffit de le refaire tourner pour télécharger les nouvelles informations. 

- Pour automatiser le téléchargement des données sur géorisques nous avons besoin de l'identifiant de chaque entreprise. Pour ce faire il faut le document export.csv dans le dossier extraction. Il se trouve à l'adresse suivante : https://www.georisques.gouv.fr/webappReport/ws/installations/sitesdetails/detailsites_2026-07-03.csv?&fieldOrderBy=etab&orderByAsc=true&size=10&isExport=true&start=0&size=0 (ou alors aller à l'adresse suivante : https://www.georisques.gouv.fr/risques/installations/donnees?page=1 , faire une recherche sans filtre en bas de page et télécharger le fichier).

- Pour télécharger le fichier result : https://mapsref.brgm.fr/wxs/georisques/georisques_dl?&service=wfs&version=2.0.0&request=getfeature&typename=InstallationsClassees&outputformat=CSVTEXT (ou alors aller sur le site https://www.georisques.gouv.fr/donnees/bases-de-donnees/installations-industrielles, en bas de la page : nationale -> csv -> télécharger)

• SIREN : 
- Il suffit de cliquer sur le lien au début du notebook pour télécharger la base de données SIREN et placer le fichier à l'endroit indiqué. 

2) Traiter les données 

Une fois output_icpe_clean.csv récupéré il faut faire tourner le notebook Traitement_données_EDF2.ipynb pour lancer le traitement des données. Ce notebook utilise les bases de données récupérées sur georisques.gouv.fr. Le notebook épure les données puis s'intéresse aux trois colonnes présentant les codes ICPE associées à chaque entreprise. Il sépare ces codes en dupliquant les informations relatives à l'entreprise pour avoir une ligne par entreprise et par code ICPE. Ensuite, la base de donnée est liée à la nomenclature ICPE qui pour chaque ligne ayant un code ICPE, associe sa description officielle. Enfin, les deux bases de données souhaitées sont construites et enregistrées dans le dossier résultat. 

3) Estimation de l'erreur

Faire tourner le notebook Lecture_de_docs en entier. Il retourne un fichier csv ,identique à résultats_table_1 à une colonne près, qui contient un booléen notant la confiance du siret et des codes postaux. 

# Problèmes rencontrés #

Le principe du projet était de relier une liste de composant EDF avec les rubriques ICPE du gouvernement. Malgré nos longues recherches nous n'avons pas pu trouver de table de correspondance entre les deux jeux de données. Il aurait donc fallu faire une correspondance manuellement mais cela aurait pris un temps considérable. C'est pourquoi, avec l'accord de notre encadrante, nous avons utiliser ClaudeAI Pro pour effectuer ce travail. Les documents transmis, le prompt ainsi que les documents et la réponse sont dans le notebook Prompt_ClaudeAI.ipynb . 
