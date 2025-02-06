import os
import pandas as pd
import re
from datetime import datetime

# Ścieżka katalogu z plikami gięcia (zmień na właściwą)
katalog_giecie = r"C:\PYTHON\PROJEKT_GEOMETRIA_GIĘCIA\baza"

# Domyślna ścieżka pliku wykazu
sciezka_wykazu = os.path.join(os.getcwd(), "wykaz.xlsx")

# Wczytanie pliku Excel
df = pd.read_excel(sciezka_wykazu)

# Zachowanie wszystkich kolumn oryginalnego wykazu
oryginalne_kolumny = df.columns.tolist()

# Tworzenie dodatkowych kolumn (jeśli ich nie ma, aby uniknąć błędów)
nowe_kolumny = [
    "plik_dld", "dane_plik_dld",
    "propozycja1", "dane_propozycja1",
    "propozycja2", "dane_propozycja2",
    "propozycja3", "dane_propozycja3",
    "inne_propozycja", "dane_inne_propozycja"
]

for kol in nowe_kolumny:
    if kol not in df.columns:
        df[kol] = ""

# Filtrujemy elementy gięte
df_giete = df[df["TECHNOLOGIA"].astype(str).str.contains(r'\bG\b|\bGS\b|\bGSO\b', na=False, regex=True)].copy()

# Funkcja do ekstrakcji rysunku i pozycji z NAZWA
def extract_drawing_and_position(nazwa):
    if isinstance(nazwa, str):  # Unikamy błędów, jeśli NAZWA jest pusta
        parts = nazwa.split("_")
        if len(parts) >= 4:
            rysunek = parts[2].replace("SL", "")  # Pominięcie "SL"
            pozycja = parts[3]
            return rysunek, pozycja
    return None, None

# Funkcja do znajdowania plików .dld
def find_dld_files(rysunek, pozycja):
    matching_files = []
    
    # Przeszukiwanie wszystkich podfolderów
    for root, _, files in os.walk(katalog_giecie):
        for file in files:
            if file.endswith(".dld") and rysunek in file:
                full_path = os.path.join(root, file)
                file_date = datetime.fromtimestamp(os.path.getmtime(full_path))
                file_name_without_ext = os.path.splitext(file)[0]  # Usunięcie rozszerzenia .dld
                matching_files.append((full_path, file_name_without_ext, file_date))
    
    # Sortowanie od najnowszych
    matching_files.sort(key=lambda x: x[2], reverse=True)

    # Grupowanie plików według pozycji
    propozycje = []
    inne = []
    
    for path, name, date in matching_files:
        if pozycja in name:
            propozycje.append((name, date))
        else:
            inne.append((name, date))

    return propozycje, inne

# Przetwarzanie każdego elementu giętego
for index, row in df_giete.iterrows():
    nazwa = row["NAZWA"]
    rysunek, pozycja = extract_drawing_and_position(nazwa)

    if rysunek:
        propozycje, inne = find_dld_files(rysunek, pozycja)

        # Wpisanie wyników do tabeli
        if propozycje:
            df.at[index, "plik_dld"] = propozycje[0][0]  # Najnowszy plik (bez rozszerzenia .dld)
            if len(propozycje) > 1:
                df.at[index, "propozycja1"] = propozycje[1][0]
            if len(propozycje) > 2:
                df.at[index, "propozycja2"] = propozycje[2][0]
            if len(propozycje) > 3:
                df.at[index, "propozycja3"] = propozycje[3][0]
        
        # Wpisanie innych propozycji
        if inne:
            df.at[index, "inne_propozycja"] = ", ".join([x[0] for x in inne[:5]])

# Zapis wyników do pliku Excel, zachowując oryginalny format
wynik_sciezka = os.path.join(os.getcwd(), "wynik.xlsx")
df.to_excel(wynik_sciezka, index=False)

print(f"Wyniki zapisane w: {wynik_sciezka}")
