import os
import pandas as pd
import shutil

# Ścieżka bazy plików (gdzie szukamy plików DLD, przeszukiwanie rekurencyjne)
katalog_giecie = r"C:\PYTHON\PROJEKT_GEOMETRIA_GIĘCIA\baza"

# Ścieżka do pliku wynik.xlsx (przyjmujemy, że już istnieje lub został wcześniej utworzony)
sciezka_wynik = os.path.join(os.getcwd(), "wynik.xlsx")

# Foldery docelowe (tworzone, jeśli nie istnieją)
sciezka_dld = os.path.join(os.getcwd(), "dld")
sciezka_plik_dld = os.path.join(os.getcwd(), "plik_dld")
sciezka_propozycje_dld = os.path.join(os.getcwd(), "propozycje_dld")

os.makedirs(sciezka_dld, exist_ok=True)
os.makedirs(sciezka_plik_dld, exist_ok=True)
os.makedirs(sciezka_propozycje_dld, exist_ok=True)

# Funkcja pomocnicza – rekurencyjne szukanie pliku w katalogu bazy
def find_file_in_baza(nazwa_pliku):
    for root, _, files in os.walk(katalog_giecie):
        if nazwa_pliku in files:
            full_path = os.path.join(root, nazwa_pliku)
            print(f"🔍 Znaleziono plik '{nazwa_pliku}' w '{root}'")
            return full_path
    return None

# Krok 1: Pobranie plików wymienionych w wynik.xlsx z bazy (katalog_giecie) do katalogu 'dld'
def kopiuj_pliki_do_dld():
    if not os.path.exists(sciezka_wynik):
        print("❌ Plik 'wynik.xlsx' nie istnieje! Najpierw utwórz lub zaktualizuj plik wynik.xlsx.")
        return
    
    df = pd.read_excel(sciezka_wynik)
    # Kolumny, w których spodziewamy się nazw plików
    kolumny_plikow = ["plik_dld", "propozycja1", "propozycja2", "propozycja3", "inne_propozycja"]
    znalezione = 0
    brakujace = 0

    print("\n🔍 Sprawdzanie plików do pobrania (z wynik.xlsx) z bazy:")
    for kolumna in kolumny_plikow:
        if kolumna in df.columns:
            for wartosc in df[kolumna].dropna():  # pomija puste komórki
                # Jeśli w komórce jest więcej niż jedna nazwa (rozdzielone przecinkiem)
                lista_plikow = [p.strip() for p in str(wartosc).split(",")]
                for plik in lista_plikow:
                    sciezka_zrodlowa = find_file_in_baza(plik)
                    if sciezka_zrodlowa:
                        sciezka_docelowa = os.path.join(sciezka_dld, plik)
                        shutil.copy(sciezka_zrodlowa, sciezka_docelowa)
                        znalezione += 1
                        print(f"✅ Skopiowano: {plik} -> {sciezka_docelowa}")
                    else:
                        brakujace += 1
                        print(f"⚠ Plik nie znaleziony w bazie: {plik}")
    print(f"\n✅ Skopiowano {znalezione} plików do katalogu 'dld'.")
    print(f"⚠ Nie znaleziono {brakujace} plików.\n")

# Krok 2: Funkcja kopiująca pliki z katalogu 'dld' do wybranego folderu (na podstawie kolumny w wynik.xlsx)
def kopiuj_pliki(kolumna, folder_docelowy):
    if not os.path.exists(sciezka_wynik):
        print("❌ Plik 'wynik.xlsx' nie istnieje! Najpierw utwórz lub zaktualizuj plik wynik.xlsx.")
        return

    df_wynik = pd.read_excel(sciezka_wynik)
    licznik_skopiowanych = 0
    licznik_brakujacych = 0

    print(f"\n📂 Kopiowanie plików z kolumny '{kolumna}' (źródło: katalog 'dld') do '{folder_docelowy}'...\n")
    for wartosc in df_wynik[kolumna].dropna():
        lista_plikow = [p.strip() for p in str(wartosc).split(",")]
        for plik in lista_plikow:
            sciezka_zrodlowa = os.path.join(sciezka_dld, plik)
            sciezka_docelowa = os.path.join(folder_docelowy, plik)
            if os.path.exists(sciezka_zrodlowa):
                shutil.copy(sciezka_zrodlowa, sciezka_docelowa)
                licznik_skopiowanych += 1
                print(f"✅ Skopiowano: {plik} -> {sciezka_docelowa}")
            else:
                licznik_brakujacych += 1
                print(f"⚠ Plik nie znaleziony w 'dld': {plik}")
    print(f"\n✅ Skopiowano {licznik_skopiowanych} plików do '{folder_docelowy}'.")
    print(f"⚠ Nie znaleziono {licznik_brakujacych} plików.\n")

# Krok 3: (opcjonalny) Aktualizacja pliku wynik.xlsx – jeżeli potrzebne
def aktualizuj_wynik():
    print("\n🔄 Aktualizowanie pliku wynik.xlsx...")
    # Tu można umieścić kod aktualizujący plik wynik.xlsx na podstawie innego źródła lub wyliczeń
    # Dla przykładu zapisujemy plik bez zmian:
    df = pd.read_excel(sciezka_wynik)
    df.to_excel(sciezka_wynik, index=False)
    print("✅ Plik wynik.xlsx został zaktualizowany.\n")

# Główne wykonanie – najpierw pobieramy pliki wymienione w wynik.xlsx z bazy do katalogu 'dld'
kopiuj_pliki_do_dld()

# MENU użytkownika
while True:
    print("\n=== MENU ===")
    print("0. Aktualizuj plik wynik.xlsx")
    print("1. Kopiuj pliki z 'plik_dld' (z katalogu 'dld') do folderu 'plik_dld'")
    print("2. Kopiuj pliki z 'propozycja1' do folderu 'propozycje_dld'")
    print("3. Kopiuj pliki z 'propozycja2' do folderu 'propozycje_dld'")
    print("4. Kopiuj pliki z 'propozycja3' do folderu 'propozycje_dld'")
    print("5. Kopiuj pliki z 'inne_propozycja' do folderu 'propozycje_dld'")
    print("6. Wyjście")
    
    wybor = input("Wybierz opcję (0-6): ").strip()

    if wybor == "0":
        aktualizuj_wynik()
    elif wybor == "1":
        kopiuj_pliki("plik_dld", sciezka_plik_dld)
    elif wybor == "2":
        kopiuj_pliki("propozycja1", sciezka_propozycje_dld)
    elif wybor == "3":
        kopiuj_pliki("propozycja2", sciezka_propozycje_dld)
    elif wybor == "4":
        kopiuj_pliki("propozycja3", sciezka_propozycje_dld)
    elif wybor == "5":
        kopiuj_pliki("inne_propozycja", sciezka_propozycje_dld)
    elif wybor == "6":
        print("🚪 Zamykanie programu.")
        break
    else:
        print("❌ Niepoprawny wybór. Wybierz opcję od 0 do 6.")
