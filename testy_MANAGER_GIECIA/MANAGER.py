import os
import shutil
import pandas as pd

# ŚCIEŻKA GŁÓWNA DO TESTÓW:
BASE_PATH = r"C:\PYTHON\PROJEKT_GEOMETRIA_GIĘCIA\testy_MANAGER_GIECIA"

# KONFIGURACJA FOLDERÓW
PATH_NOWE = os.path.join(BASE_PATH, "Nowe")
PATH_W_TRAKCIE = os.path.join(BASE_PATH, "W_trakcie")
PATH_GOTOWE = os.path.join(BASE_PATH, "Gotowe")
PATH_ARCHIWUM = os.path.join(BASE_PATH, "Archiwum")

# ŚCIEŻKA DO PLIKU EXCEL
PATH_EXCEL = os.path.join(BASE_PATH, "ListaElementow.xlsx")

# LIMIT plików do edycji (zgodnie z ograniczeniem licencji Delem)
LIMIT_W_TRAKCIE = 10

def init_directories():
    """
    Funkcja pomocnicza, która tworzy foldery,
    jeśli jeszcze nie istnieją. Dzięki temu
    unikniemy błędów w przypadku braku katalogu.
    """
    os.makedirs(PATH_NOWE, exist_ok=True)
    os.makedirs(PATH_W_TRAKCIE, exist_ok=True)
    os.makedirs(PATH_GOTOWE, exist_ok=True)
    os.makedirs(PATH_ARCHIWUM, exist_ok=True)

def wczytaj_liste_zlecen():
    """Wczytuje plik Excel do obiektu pandas DataFrame."""
    df = pd.read_excel(PATH_EXCEL)
    return df

def zapisz_liste_zlecen(df):
    """Zapisuje zaktualizowany DataFrame do pliku Excel."""
    df.to_excel(PATH_EXCEL, index=False)

def przenies_do_folderu(sciezka_zrodlowa, sciezka_docelowa):
    """Przenosi plik z jednego miejsca do drugiego."""
    shutil.move(sciezka_zrodlowa, sciezka_docelowa)

def wybierz_i_przenies_do_w_trakcie(df, lista_id):
    """
    Na podstawie listy ID elementów:
    1. Sprawdza, ile plików jest obecnie w W_trakcie.
    2. Jeżeli jest miejsce (poniżej limitu), przenosi plik z folderu Nowe do W_trakcie.
    3. Aktualizuje kolumnę 'Status' w Excelu na 'W trakcie'.
    """
    # Zlicz pliki .dld w folderze W_trakcie:
    pliki_w_trakcie = [p for p in os.listdir(PATH_W_TRAKCIE) if p.endswith('.dld')]
    ilosc_w_trakcie = len(pliki_w_trakcie)

    for element_id in lista_id:
        # Znajdź wiersz w df
        wiersz_df = df[df['ID'] == element_id]
        if wiersz_df.empty:
            print(f"[UWAGA] Nie znaleziono ID: {element_id} w Excelu!")
            continue

        wiersz = wiersz_df.iloc[0]
        nazwa_pliku = wiersz['Nazwa pliku']

        # Ścieżka źródłowa w folderze Nowe (jeśli tam faktycznie jest)
        sciezka_zrodlowa = os.path.join(PATH_NOWE, nazwa_pliku)
        sciezka_docelowa = os.path.join(PATH_W_TRAKCIE, nazwa_pliku)

        # Sprawdzamy limit
        if ilosc_w_trakcie < LIMIT_W_TRAKCIE:
            if os.path.exists(sciezka_zrodlowa):
                przenies_do_folderu(sciezka_zrodlowa, sciezka_docelowa)
                df.loc[df['ID'] == element_id, 'Status'] = 'W trakcie'
                ilosc_w_trakcie += 1
                print(f"Przeniesiono plik {nazwa_pliku} do W_trakcie.")
            else:
                print(f"[UWAGA] Plik {nazwa_pliku} nie istnieje w folderze Nowe!")
        else:
            print("Osiągnięto limit 10 plików w folderze W_trakcie!")
            break

    zapisz_liste_zlecen(df)

def oznacz_jako_gotowe(df, lista_id):
    """
    Po zakończeniu edycji w Delem przenosi pliki z W_trakcie do Gotowe
    i ustawia w Excelu 'Status' = 'Gotowe'.
    """
    for element_id in lista_id:
        wiersz_df = df[df['ID'] == element_id]
        if wiersz_df.empty:
            print(f"[UWAGA] Nie znaleziono ID: {element_id} w Excelu!")
            continue

        wiersz = wiersz_df.iloc[0]
        nazwa_pliku = wiersz['Nazwa pliku']

        sciezka_zrodlowa = os.path.join(PATH_W_TRAKCIE, nazwa_pliku)
        sciezka_docelowa = os.path.join(PATH_GOTOWE, nazwa_pliku)

        if os.path.exists(sciezka_zrodlowa):
            przenies_do_folderu(sciezka_zrodlowa, sciezka_docelowa)
            df.loc[df['ID'] == element_id, 'Status'] = 'Gotowe'
            print(f"Oznaczono plik {nazwa_pliku} jako Gotowe.")
        else:
            print(f"[UWAGA] Plik {nazwa_pliku} nie istnieje w W_trakcie!")

    zapisz_liste_zlecen(df)

def main():
    # Inicjalizacja katalogów
    init_directories()

    # Wczytanie listy elementów z Excela
    df = wczytaj_liste_zlecen()

    # Wyświetlamy elementy o statusie 'Nowe'
    print("=== ELEMENTY O STATUSIE 'Nowe' ===")
    nowe_df = df[df['Status'] == 'Nowe']
    print(nowe_df[['ID', 'Nazwa elementu', 'Nazwa pliku', 'Status']])

    # Przykład: wybieramy (ręcznie lub dynamicznie) ID elementów, które chcemy przenieść do W_trakcie
    lista_id_do_przeniesienia = [101, 102]
    print(f"\n>>> Przenosimy ID: {lista_id_do_przeniesienia} do W_trakcie...\n")
    wybierz_i_przenies_do_w_trakcie(df, lista_id_do_przeniesienia)

    # Symulujemy, że w Delem dokonaliśmy edycji i teraz chcemy oznaczyć np. element 101 jako 'Gotowe'
    lista_id_gotowe = [101]
    print(f"\n>>> Oznaczamy ID: {lista_id_gotowe} jako Gotowe...\n")
    oznacz_jako_gotowe(df, lista_id_gotowe)

    # Podgląd aktualnej listy zleceń
    print("\n=== AKTUALNY STAN LISTY PO OPERACJACH ===")
    df = wczytaj_liste_zlecen()
    print(df[['ID', 'Nazwa elementu', 'Nazwa pliku', 'Status']])

if __name__ == "__main__":
    main()
