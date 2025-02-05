import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import pandas as pd
import os
import shutil

# ------------ KONFIGURACJA ------------
BASE_PATH = r"C:\PYTHON\PROJEKT_GEOMETRIA_GIĘCIA\testy_MANAGER_GIECIA"
PATH_EXCEL = os.path.join(BASE_PATH, "ListaElementow.xlsx")

PATH_NOWE = os.path.join(BASE_PATH, "Nowe")
PATH_W_TRAKCIE = os.path.join(BASE_PATH, "W_trakcie")
PATH_GOTOWE = os.path.join(BASE_PATH, "Gotowe")
PATH_ARCHIWUM = os.path.join(BASE_PATH, "Archiwum")

LIMIT_W_TRAKCIE = 10  # maks. liczba plików w folderze W_trakcie

# Lista folderów w kolejności priorytetowej (pomocna do skanowania)
FOLDERS_STATUS = [
    (PATH_NOWE, "Nowe"),
    (PATH_W_TRAKCIE, "W trakcie"),
    (PATH_GOTOWE, "Gotowe"),
    (PATH_ARCHIWUM, "Archiwum")
]

def przenies_do_folderu(src, dst):
    """Przenosi plik z src do dst (jeśli istnieje)."""
    shutil.move(src, dst)

class ManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Manager Gięcia - tkinter (pełna synchronizacja)")

        # Górny panel przycisków
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Button(self.button_frame, text="Odśwież", command=self.odswiez).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Przenieś do W_trakcie", command=self.przenies_do_w_trakcie).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Przenieś do Gotowe", command=self.przenies_do_gotowe).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Przenieś do Archiwum", command=self.przenies_do_archiwum).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Edytuj nazwę pliku", command=self.edytuj_nazwe_pliku).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Wyjście", command=self.root.destroy).pack(side=tk.RIGHT, padx=5)

        # Główna ramka + Canvas (przewijana tabela)
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.main_frame)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = tk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Ramka na tabelę
        self.table_frame = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.table_frame, anchor="nw")

        # Zasoby do tabeli
        self.df = None
        self.example_data = []
        self.row_indices = []
        self.check_vars = []

        self.table_frame.bind("<Configure>", self.on_frame_configure)

        # Inicjalnie: odśwież
        self.odswiez()

    def on_frame_configure(self, event):
        """Ustawia region przewijania canvasa po zmianie."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # ------------------------------------------------------------------------------
    # 1. Skan folderów i synchronizacja z plikiem Excel
    # ------------------------------------------------------------------------------

    def sync_with_folders(self):
        """
        Pełna synchronizacja folderów z plikiem Excel.
        1) Wczytuje df z Excela (jeśli brak kolumn, tworzy je).
        2) Skanuje foldery:
           - Jeśli znajdzie nowy plik .dld, który nie jest w df -> tworzy nowy wiersz
           - Ustawia status wiersza na podstawie folderu, w którym jest plik
        3) Jeśli w df jest wiersz, którego plik nie istnieje w żadnym folderze -> Status = 'Nie znaleziono'
        4) Zapisuje df do pliku Excel.
        """
        # 1) Wczytanie lub utworzenie df
        if os.path.exists(PATH_EXCEL):
            self.df = pd.read_excel(PATH_EXCEL)
        else:
            # Tworzymy pustego DataFrame
            self.df = pd.DataFrame(columns=["ID", "Nazwa elementu", "Nazwa pliku", "Status"])

        # Upewnij się, że kolumny są na pewno w df:
        for col in ["ID", "Nazwa elementu", "Nazwa pliku", "Status"]:
            if col not in self.df.columns:
                self.df[col] = ""

        # 2) Skan folderów i zbierz wszystkie pliki .dld
        found_files = {}  # dict: {nazwa_pliku: (folder, status_folderu)}
        for folder_path, status_name in FOLDERS_STATUS:
            if not os.path.exists(folder_path):
                os.makedirs(folder_path, exist_ok=True)
            for fname in os.listdir(folder_path):
                if fname.lower().endswith(".dld"):
                    # jeśli ten plik był już znaleziony w innym folderze, pomijamy
                    # (teoretycznie plik nie powinien być w kilku folderach naraz)
                    if fname not in found_files:
                        found_files[fname] = (folder_path, status_name)

        # 3) Zaktualizuj / dodaj wiersze w df na podstawie found_files
        for fname, (fpath, fstatus) in found_files.items():
            # Szukamy w df wiersza z 'Nazwa pliku' == fname
            mask = (self.df["Nazwa pliku"] == fname)
            if mask.any():
                # Istnieje wiersz -> update Status
                idx = self.df[mask].index[0]
                self.df.loc[idx, "Status"] = fstatus
            else:
                # Nowy plik w folderze, a nie ma go w Excelu -> dodajemy
                new_id = None
                # Znajdź najwyższe ID i dodaj 1
                if pd.api.types.is_numeric_dtype(self.df["ID"]):
                    if self.df["ID"].dropna().size > 0:
                        new_id = int(self.df["ID"].dropna().max()) + 1
                    else:
                        new_id = 100  # np. start od 100
                else:
                    # jeśli kolumna ID nie jest numeryczna, wymuś
                    new_id = 100

                new_row = {
                    "ID": new_id,
                    "Nazwa elementu": "",   # domyślnie puste, do uzupełnienia
                    "Nazwa pliku": fname,
                    "Status": fstatus
                }
                self.df = self.df.append(new_row, ignore_index=True)

        # 4) Dla wierszy, których plik nie występuje w found_files, ustaw 'Nie znaleziono'
        for idx in self.df.index:
            fname = self.df.loc[idx, "Nazwa pliku"]
            if fname not in found_files:
                self.df.loc[idx, "Status"] = "Nie znaleziono"

        # 5) Zapis
        self.df.to_excel(PATH_EXCEL, index=False)

    # ------------------------------------------------------------------------------
    # 2. Główna metoda odświeżająca widok w tkinter
    # ------------------------------------------------------------------------------

    def odswiez(self):
        """
        - Pełna synchronizacja z folderami i Excel (sync_with_folders).
        - Wczytanie df i zbudowanie listy checkbox + etykiet w table_frame.
        """
        self.sync_with_folders()  # najpierw zsynchronizuj

        # Ponownie wczytaj (można od razu używać self.df, ale wczytanie potwierdzi zapis)
        self.df = pd.read_excel(PATH_EXCEL)

        # Konwersja do listy rekordów
        self.example_data = self.df.to_dict("records")
        self.row_indices = self.df.index.tolist()

        # Wyczyść table_frame
        for w in self.table_frame.winfo_children():
            w.destroy()
        self.check_vars.clear()

        # Nagłówek
        headers = ["", "ID", "Nazwa elementu", "Nazwa pliku", "Status"]
        for col_idx, col_name in enumerate(headers):
            tk.Label(self.table_frame, text=col_name, font=("Arial", 10, "bold")).grid(
                row=0, column=col_idx, padx=5, pady=5, sticky="w"
            )

        # Wiersze
        for i, row_data in enumerate(self.example_data, start=1):
            var = tk.BooleanVar(value=False)
            self.check_vars.append(var)

            # Checkbox
            chk = tk.Checkbutton(self.table_frame, variable=var)
            chk.grid(row=i, column=0, padx=5, pady=2, sticky="w")

            # ID
            tk.Label(self.table_frame, text=row_data.get("ID", "")).grid(row=i, column=1, padx=5, pady=2, sticky="w")
            # Nazwa elementu
            tk.Label(self.table_frame, text=row_data.get("Nazwa elementu", "")).grid(row=i, column=2, padx=5, pady=2, sticky="w")
            # Nazwa pliku
            tk.Label(self.table_frame, text=row_data.get("Nazwa pliku", "")).grid(row=i, column=3, padx=5, pady=2, sticky="w")
            # Status
            tk.Label(self.table_frame, text=row_data.get("Status", "")).grid(row=i, column=4, padx=5, pady=2, sticky="w")

        self.on_frame_configure(None)

    def get_selected_indices(self):
        """Zwraca listę indeksów w self.df odpowiadających zaznaczonym checkboxom."""
        selected = []
        for idx, var in enumerate(self.check_vars):
            if var.get():
                selected.append(idx)
        return selected

    # ------------------------------------------------------------------------------
    # 3. Funkcje do przenoszenia plików
    # ------------------------------------------------------------------------------

    def przenies_do_w_trakcie(self):
        """
        Zaznaczone pliki przenosimy z 'Nowe' do 'W_trakcie', o ile fizycznie tam są
        i nie przekroczymy limitu 10 w W_trakcie.
        """
        selected_indices = self.get_selected_indices()

        # Policz, ile jest obecnie plików w W_trakcie
        wtr_files = [f for f in os.listdir(PATH_W_TRAKCIE) if f.lower().endswith(".dld")]
        current_count = len(wtr_files)

        moved_count = 0

        for s_idx in selected_indices:
            df_idx = self.row_indices[s_idx]
            nazwa_pliku = self.df.loc[df_idx, "Nazwa pliku"]
            status = self.df.loc[df_idx, "Status"]

            if status != "Nowe":
                print(f"[INFO] Plik '{nazwa_pliku}' nie jest w folderze Nowe (status={status}). Pomijam.")
                continue

            if current_count >= LIMIT_W_TRAKCIE:
                messagebox.showwarning("Limit", f"Osiągnięto limit {LIMIT_W_TRAKCIE} plików w W_trakcie!")
                break

            src_path = os.path.join(PATH_NOWE, nazwa_pliku)
            dst_path = os.path.join(PATH_W_TRAKCIE, nazwa_pliku)

            if os.path.exists(src_path):
                przenies_do_folderu(src_path, dst_path)
                current_count += 1
                moved_count += 1
            else:
                print(f"[UWAGA] Plik '{nazwa_pliku}' nie istnieje w folderze Nowe (zniknął?).")

        if moved_count > 0:
            messagebox.showinfo("OK", f"Przeniesiono {moved_count} plików do W_trakcie.")

        # Odśwież
        self.odswiez()

    def przenies_do_gotowe(self):
        """Zaznaczone pliki przenosimy z 'W_trakcie' do 'Gotowe', o ile tam fizycznie są."""
        selected_indices = self.get_selected_indices()
        moved_count = 0

        for s_idx in selected_indices:
            df_idx = self.row_indices[s_idx]
            nazwa_pliku = self.df.loc[df_idx, "Nazwa pliku"]
            status = self.df.loc[df_idx, "Status"]

            if status != "W trakcie":
                print(f"[INFO] Plik '{nazwa_pliku}' nie jest w W_trakcie (status={status}). Pomijam.")
                continue

            src_path = os.path.join(PATH_W_TRAKCIE, nazwa_pliku)
            dst_path = os.path.join(PATH_GOTOWE, nazwa_pliku)

            if os.path.exists(src_path):
                przenies_do_folderu(src_path, dst_path)
                moved_count += 1
            else:
                print(f"[UWAGA] Plik '{nazwa_pliku}' nie istnieje w folderze W_trakcie.")

        if moved_count > 0:
            messagebox.showinfo("OK", f"Przeniesiono {moved_count} plików do Gotowe.")

        self.odswiez()

    def przenies_do_archiwum(self):
        """
        Zaznaczone pliki przenosimy z 'Gotowe' do 'Archiwum', o ile tam fizycznie są.
        """
        selected_indices = self.get_selected_indices()
        moved_count = 0

        for s_idx in selected_indices:
            df_idx = self.row_indices[s_idx]
            nazwa_pliku = self.df.loc[df_idx, "Nazwa pliku"]
            status = self.df.loc[df_idx, "Status"]

            if status != "Gotowe":
                print(f"[INFO] Plik '{nazwa_pliku}' nie jest w Gotowe (status={status}). Pomijam.")
                continue

            src_path = os.path.join(PATH_GOTOWE, nazwa_pliku)
            dst_path = os.path.join(PATH_ARCHIWUM, nazwa_pliku)

            if os.path.exists(src_path):
                przenies_do_folderu(src_path, dst_path)
                moved_count += 1
            else:
                print(f"[UWAGA] Plik '{nazwa_pliku}' nie istnieje w Gotowe.")

        if moved_count > 0:
            messagebox.showinfo("OK", f"Przeniesiono {moved_count} plików do Archiwum.")

        self.odswiez()

    # ------------------------------------------------------------------------------
    # 4. Edycja nazwy pliku
    # ------------------------------------------------------------------------------

    def edytuj_nazwe_pliku(self):
        """
        Edytujemy nazwę pliku .dld (fizycznie i w Excelu) tylko dla jednego zaznaczonego wiersza.
        - Szukamy go w folderze, w którym ma status, i zmieniamy nazwę pliku.
        """
        selected_indices = self.get_selected_indices()
        if len(selected_indices) == 0:
            messagebox.showinfo("Info", "Nie zaznaczono żadnego wiersza do edycji.")
            return
        if len(selected_indices) > 1:
            messagebox.showinfo("Info", "Wybierz tylko jeden wiersz do edycji nazwy pliku.")
            return

        s_idx = selected_indices[0]
        df_idx = self.row_indices[s_idx]

        stara_nazwa = self.df.loc[df_idx, "Nazwa pliku"]
        status = self.df.loc[df_idx, "Status"]

        # Zapytanie o nową nazwę
        nowa_nazwa = simpledialog.askstring(
            "Edycja nazwy pliku",
            f"Obecna nazwa: {stara_nazwa}\nPodaj nową nazwę (z rozszerzeniem .dld):"
        )
        if not nowa_nazwa:
            return

        # Spróbujmy zmienić fizyczną nazwę w folderze odpowiadającym statusowi
        folder_path = None
        if status == "Nowe":
            folder_path = PATH_NOWE
        elif status == "W trakcie":
            folder_path = PATH_W_TRAKCIE
        elif status == "Gotowe":
            folder_path = PATH_GOTOWE
        elif status == "Archiwum":
            folder_path = PATH_ARCHIWUM
        else:
            # Jesli "Nie znaleziono", to nie wiemy, w którym jest folderze
            folder_path = None

        file_renamed = False
        if folder_path is not None and os.path.exists(os.path.join(folder_path, stara_nazwa)):
            old_path = os.path.join(folder_path, stara_nazwa)
            new_path = os.path.join(folder_path, nowa_nazwa)
            os.rename(old_path, new_path)
            file_renamed = True
        else:
            # Jeśli w folderze teoretycznym nie ma pliku, to może jest w innym?
            # Albo w ogóle "Nie znaleziono"
            # Możesz tu dodać skan wszystkich folderów. Dla przykładu:
            for fpath, _fstatus in FOLDERS_STATUS:
                old_path = os.path.join(fpath, stara_nazwa)
                if os.path.exists(old_path):
                    new_path = os.path.join(fpath, nowa_nazwa)
                    os.rename(old_path, new_path)
                    file_renamed = True
                    break

        # Zaktualizuj w Excelu
        self.df.loc[df_idx, "Nazwa pliku"] = nowa_nazwa
        self.df.to_excel(PATH_EXCEL, index=False)

        if file_renamed:
            messagebox.showinfo("OK", f"Zmieniono nazwę pliku '{stara_nazwa}' na '{nowa_nazwa}'.")
        else:
            messagebox.showwarning("Uwaga", f"Nie udało się odnaleźć pliku '{stara_nazwa}' w folderach.\n"
                                            "Zmieniono tylko nazwę w Excelu.")

        # Pełne odświeżenie
        self.odswiez()


def main():
    root = tk.Tk()
    app = ManagerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
