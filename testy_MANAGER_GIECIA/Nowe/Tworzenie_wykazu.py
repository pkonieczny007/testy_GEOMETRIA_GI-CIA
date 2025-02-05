import pandas as pd
import os

# Pobierz listę plików w bieżącym katalogu (pomijamy podkatalogi)
pliki = [plik for plik in os.listdir('.') if os.path.isfile(plik)]

# Utwórz DataFrame z wymaganymi kolumnami:
# - ID: numeracja od 1,
# - Nazwa elementu: pusta (do uzupełnienia),
# - Nazwa pliku: nazwa pliku (z rozszerzeniem),
# - Status: pusta (do uzupełnienia)
df = pd.DataFrame({
    'ID': range(1, len(pliki) + 1),
    'Nazwa elementu': ['' for _ in pliki],
    'Nazwa pliku': pliki,
    'Status': ['' for _ in pliki]
})

# Zapisz DataFrame do pliku Excel
df.to_excel('wykaz.xlsx', index=False)

print("Plik Excel 'wykaz.xlsx' został stworzony.")
