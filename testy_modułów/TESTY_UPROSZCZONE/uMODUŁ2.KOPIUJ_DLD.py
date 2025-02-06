import os
import pandas as pd
import shutil

# Ścieżka bazy plików (gdzie szukamy plików DLD, przeszukiwanie rekurencyjne)
katalog_giecie = r"C:\PYTHON\PROJEKT_GEOMETRIA_GIĘCIA\baza"

# Ścieżka do pliku wynik.xlsx
sciezka_wynik = os.path.join(os.getcwd(), "wynik.xlsx")

# Foldery docelowe
sciezka_dld = os.path.join(os.getcwd(), "dld")
os.makedirs(sciezka_dld, exist_ok=True)

def find_file_in_baza(nazwa_pliku):
    """Szuka pliku w katalogu_giecie, dodając rozszerzenie .dld."""
    nazwa_pliku_dld = f"{nazwa_pliku}.dld"
    for root, _, files in os.walk(katalog_giecie):
        if nazwa_pliku_dld in files:
            full_path = os.path.join(root, nazwa_pliku_dld)
            print(f"🔍 Znaleziono plik '{nazwa_pliku_dld}' w '{root}'")
            return full_path
    return None

def kopiuj_pliki_do_dld():
    """Kopiuje pliki z bazy do folderu 'dld'."""
    if not os.path.exists(sciezka_wynik):
        print("❌ Plik 'wynik.xlsx' nie istnieje!")
        return
    
    df = pd.read_excel(sciezka_wynik)
    kolumny_plikow = ["plik_dld", "propozycja1", "propozycja2", "propozycja3", "inne_propozycja"]
    znalezione, brakujace = 0, 0
    
    print("\n🔍 Sprawdzanie plików do pobrania z bazy:")
    for kolumna in kolumny_plikow:
        if kolumna in df.columns:
            for wartosc in df[kolumna].dropna():
                lista_plikow = [p.strip() for p in str(wartosc).split(",")]
                for plik in lista_plikow:
                    sciezka_zrodlowa = find_file_in_baza(plik)
                    if sciezka_zrodlowa:
                        sciezka_docelowa = os.path.join(sciezka_dld, os.path.basename(sciezka_zrodlowa))
                        shutil.copy(sciezka_zrodlowa, sciezka_docelowa)
                        znalezione += 1
                        print(f"✅ Skopiowano: {plik}.dld -> {sciezka_docelowa}")
                    else:
                        brakujace += 1
                        print(f"⚠ Plik nie znaleziony w bazie: {plik}.dld")
    print(f"\n✅ Skopiowano {znalezione} plików.")
    print(f"⚠ Nie znaleziono {brakujace} plików.\n")

kopiuj_pliki_do_dld()
