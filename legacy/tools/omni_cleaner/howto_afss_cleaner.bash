cd AFSS

# JSON file anonymisieren
python tools/omni_cleaner/afss_cleaner.py clean config/artists.json

# Filetree anonymisieren
python tools/omni_cleaner/afss_cleaner.py clean config/category_1_tree.txt

# Wiederherstellen
python tools/omni_cleaner/afss_cleaner.py declean config/artists_cleaned.json





python tools/omni_cleaner/afss_cleaner.py clean config/Filetrees/filetree_an.txt
