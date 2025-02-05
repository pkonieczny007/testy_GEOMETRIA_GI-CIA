import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import pandas as pd
import os
import shutil

# Potrzebne do dopasowywania kolumn (autofit):
from openpyxl.utils import get_column_letter

# ------------ KONFIGURACJA ------------
BASE_PATH = r"C:\PYTHON\PROJEKT_GEOMETRIA_GIĘCIA\testy_MANAGER_GIECIA"
PATH_EXCEL = os.path.join(BASE_PATH, "ListaElementow.xlsx")

PATH_NOWE = os.path.join(BASE_PATH, "Nowe")
PATH_W_TRAKCIE = os.path.join(BASE_PATH, "W_trakcie")
PATH_GOTOWE = os.path.join(BASE_PATH, "Gotowe")
PATH_ARCHIWUM = os.path.join(BASE_PATH, "Archiwum")

LIMIT_W_TRAKCIE = 10  # maks. liczba plików w folderze W_trakcie

# Lista folderów w kolejności priorytetowej (pomocna do szukania pliku)
FOLDERS_STATUS = [
    (PATH_NOWE, "Nowe"),
    (PATH_W_TRAKCIE, "W trakcie"),
    (PATH_GOTOWE, "Gotowe"),
    (PATH_ARCHIWUM, "Archiwum")
]

def przenies_do_folderu(src, dst):
    """Przenosi plik z src do dst."""
    shutil.move(src, dst)

class ManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Manager Gięcia - tkinter (z autofitem w Excelu)")

        # --- Panel przycisków (góra) ---
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Button(self.button_frame, text="Odśwież", command=self.odswiez).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Przenieś do W_trakcie", command=self.przenies_do_w_trakcie).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Przenieś do Gotowe", command=self.przenies_do_gotowe).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Przenieś do Archiwum", command=self.przenies_do_archiwum).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Edytuj nazwę pliku", command=self.edytuj_nazwe_pliku).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Wyjście", command=self.root.destroy).pack(side=tk.RIGHT, padx=5)

        # --- Ramka główna + Canvas (przewijana tabela) ---
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

        # Na start - odśwież
        self.odswiez()

    def on_frame_configure(self, event):
        """Aktualizuje region przewijania canvasa."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # -------------------------------------------------------------------------
    # FUNKCJA ZAPISUJĄCA DF DO EXCELA Z AUTOFITEM
    # -------------------------------------------------------------------------
    def save_excel_autofit(self, df: pd.DataFrame, path: str):
        """
        Zapisuje DataFrame do pliku Excel z automatycznym dopasowaniem szerokości kolumn.
        Wykorzystuje engine='openpyxl'.
        """
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Sheet1', index=False)
            ws = writer.sheets['Sheet1']

            # Autofit columns
            for col_idx, col in enumerate(ws.columns, start=1):
                max_length = 0
                for cell in col:
                    val = cell.value
                    if val is not None:
                        length = len(str(val))
                        if length > max_length:
                            max_length = length
                col_letter = get_column_letter(col_idx)
                # Dodaj mały margines, np. +2
                ws.column_dimensions[col_letter].width = max_length + 2

            writer.save()

    # -------------------------------------------------------------------------
    # 1. Skan folderów i synchronizacja z plikiem Excel
    # -------------------------------------------------------------------------
    def sync_with_folders(self):
        """
        Pełna synchronizacja folderów z plikiem Excel.
        1) Wczytuje df z Excela (lub tworzy).
        2) Skanuje foldery i ustawia status w df (dodając nowe wiersze, jeśli plik .dld nie istnieje w Excelu).
        3) Jeśli w df jest plik, którego nie ma w żadnym folderze -> Status="Nie znaleziono".
        4) Zapisuje df z autofitem.
        """
        if os.path.exists(PATH_EXCEL):
            self.df = pd.read_excel(PATH_EXCEL)
        else:
            self.df = pd.DataFrame(columns=["ID", "Nazwa elementu", "Nazwa pliku", "Status"])

        # Upewnij się, że kolumny istnieją
        for col in ["ID", "Nazwa elementu", "Nazwa pliku", "Status"]:
            if col not in self.df.columns:
                self.df[col] = ""

        found_files = {}
        # Skan wszystkich folderów
        for folder_path, status_name in FOLDERS_STATUS:
            if not os.path.exists(folder_path):
                os.makedirs(folder_path, exist_ok=True)
            for fname in os.listdir(folder_path):
                if fname.lower().endswith(".dld"):
                    if fname not in found_files:
                        found_files[fname] = (folder_path, status_name)

        # Update / add
        for fname, (fpath, fstatus) in found_files.items():
            mask = (self.df["Nazwa pliku"] == fname)
            if mask.any():
                idx = self.df[mask].index[0]
                self.df.loc[idx, "Status"] = fstatus
            else:
                # nowy wiersz
                new_id = 100
                if pd.api.types.is_numeric_dtype(self.df["ID"]):
                    if self.df["ID"].dropna().size > 0:
                        new_id = int(self.df["ID"].dropna().max()) + 1
                new_row = {
                    "ID": new_id,
                    "Nazwa elementu": "",
                    "Nazwa pliku": fname,
                    "Status": fstatus
                }
                self.df = self.df.append(new_row, ignore_index=True)

        # Pliki w df, których nie ma w found_files -> Nie znaleziono
        for idx in self.df.index:
            fname = self.df.loc[idx, "Nazwa pliku"]
            if fname not in found_files:
                self.df.loc[idx, "Status"] = "Nie znaleziono"

        # Zapis z autofitem
        self.save_excel_autofit(self.df, PATH_EXCEL)

    def odswiez(self):
        """
        Synchronizacja z folderami i przebudowa widoku w table_frame.
        """
        self.sync_with_folders()

        # Ponownie wczytaj (aby mieć pewność zapisu)
        self.df = pd.read_excel(PATH_EXCEL)
        self.example_data = self.df.to_dict("records")
        self.row_indices = self.df.index.tolist()

        # Czyścimy table_frame
        for w in self.table_frame.winfo_children():
            w.destroy()
        self.check_vars.clear()

        # Nagłówki
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

    # ------------------------------------------------------------------------------
    # POMOC: Znajdź plik w dowolnym folderze
    # ------------------------------------------------------------------------------
    def find_file_in_any_folder(self, filename):
        """
        Zwraca ścieżkę do pliku 'filename' w jednym z folderów
        (Nowe, W_trakcie, Gotowe, Archiwum), jeśli istnieje.
        W przeciwnym razie None.
        """
        for folder, _st in FOLDERS_STATUS:
            path = os.path.join(folder, filename)
            if os.path.exists(path):
                return path
        return None

    def get_selected_indices(self):
        selected = []
        for idx, var in enumerate(self.check_vars):
            if var.get():
                selected.append(idx)
        return selected

    # ------------------------------------------------------------------------------
    # PRZENOSZENIE DO W_TRAKCIE, GOTOWE, ARCHIWUM
    # ------------------------------------------------------------------------------
    def przenies_do_w_trakcie(self):
        selected_indices = self.get_selected_indices()
        wtrakcie_files = [f for f in os.listdir(PATH_W_TRAKCIE) if f.lower().endswith(".dld")]
        current_count = len(wtrakcie_files)

        moved_count = 0
        for s_idx in selected_indices:
            df_idx = self.row_indices[s_idx]
            nazwa_pliku = self.df.loc[df_idx, "Nazwa pliku"]

            if current_count >= LIMIT_W_TRAKCIE:
                messagebox.showwarning("Limit", f"Osiągnięto limit {LIMIT_W_TRAKCIE} plików w W_trakcie!")
                break

            old_path = self.find_file_in_any_folder(nazwa_pliku)
            if old_path is None:
                print(f"[UWAGA] Plik '{nazwa_pliku}' nie istnieje w żadnym folderze.")
                continue

            if os.path.dirname(old_path) == PATH_W_TRAKCIE:
                print(f"[INFO] Plik '{nazwa_pliku}' już jest w W_trakcie.")
                continue

            new_path = os.path.join(PATH_W_TRAKCIE, nazwa_pliku)
            shutil.move(old_path, new_path)
            current_count += 1
            moved_count += 1

        if moved_count > 0:
            messagebox.showinfo("OK", f"Przeniesiono {moved_count} plików do W_trakcie.")

        self.odswiez()

    def przenies_do_gotowe(self):
        selected_indices = self.get_selected_indices()
        moved_count = 0
        for s_idx in selected_indices:
            df_idx = self.row_indices[s_idx]
            nazwa_pliku = self.df.loc[df_idx, "Nazwa pliku"]

            old_path = self.find_file_in_any_folder(nazwa_pliku)
            if old_path is None:
                print(f"[UWAGA] Plik '{nazwa_pliku}' nie istnieje w żadnym folderze.")
                continue

            if os.path.dirname(old_path) == PATH_GOTOWE:
                print(f"[INFO] Plik '{nazwa_pliku}' już jest w Gotowe.")
                continue

            new_path = os.path.join(PATH_GOTOWE, nazwa_pliku)
            shutil.move(old_path, new_path)
            moved_count += 1

        if moved_count > 0:
            messagebox.showinfo("OK", f"Przeniesiono {moved_count} plików do Gotowe.")

        self.odswiez()

    def przenies_do_archiwum(self):
        selected_indices = self.get_selected_indices()
        moved_count = 0
        for s_idx in selected_indices:
            df_idx = self.row_indices[s_idx]
            nazwa_pliku = self.df.loc[df_idx, "Nazwa pliku"]

            old_path = self.find_file_in_any_folder(nazwa_pliku)
            if old_path is None:
                print(f"[UWAGA] Plik '{nazwa_pliku}' nie istnieje w żadnym folderze.")
                continue

            if os.path.dirname(old_path) == PATH_ARCHIWUM:
                print(f"[INFO] Plik '{nazwa_pliku}' już jest w Archiwum.")
                continue

            new_path = os.path.join(PATH_ARCHIWUM, nazwa_pliku)
            shutil.move(old_path, new_path)
            moved_count += 1

        if moved_count > 0:
            messagebox.showinfo("OK", f"Przeniesiono {moved_count} plików do Archiwum.")

        self.odswiez()

    # ------------------------------------------------------------------------------
    # EDYCJA NAZWY PLIKU
    # ------------------------------------------------------------------------------
    def edytuj_nazwe_pliku(self):
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

        nowa_nazwa = simpledialog.askstring(
            "Edycja nazwy pliku",
            f"Obecna nazwa: {stara_nazwa}\nPodaj nową nazwę (z rozszerzeniem .dld):"
        )
        if not nowa_nazwa:
            return

        old_path = self.find_file_in_any_folder(stara_nazwa)
        file_renamed = False
        if old_path:
            new_path = os.path.join(os.path.dirname(old_path), nowa_nazwa)
            if not os.path.exists(new_path):
                os.rename(old_path, new_path)
                file_renamed = True
            else:
                print(f"[UWAGA] Plik '{nowa_nazwa}' już istnieje w tym folderze!")

        # Zaktualizuj w df
        self.df.loc[df_idx, "Nazwa pliku"] = nowa_nazwa
        # Tu też używamy zapisu z autofit
        self.save_excel_autofit(self.df, PATH_EXCEL)

        if file_renamed:
            messagebox.showinfo("OK", f"Zmieniono nazwę pliku '{stara_nazwa}' na '{nowa_nazwa}'.")
        else:
            messagebox.showwarning("Uwaga", f"Nie udało się przenieść pliku '{stara_nazwa}' (może nie istnieje?),\n"
                                            "ale zaktualizowano nazwę w Excelu.")

        self.odswiez()


def main():
    root = tk.Tk()
    app = ManagerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
