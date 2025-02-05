import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import pandas as pd
import os
import shutil

# -- KONFIGURACJA ŚCIEŻEK I LIMITÓW --
BASE_PATH = r"C:\PYTHON\PROJEKT_GEOMETRIA_GIĘCIA\testy_MANAGER_GIECIA"
PATH_EXCEL = os.path.join(BASE_PATH, "ListaElementow.xlsx")

PATH_NOWE = os.path.join(BASE_PATH, "Nowe")
PATH_W_TRAKCIE = os.path.join(BASE_PATH, "W_trakcie")
PATH_GOTOWE = os.path.join(BASE_PATH, "Gotowe")
PATH_ARCHIWUM = os.path.join(BASE_PATH, "Archiwum")

# Limit plików w W_trakcie:
LIMIT_W_TRAKCIE = 10


def przenies_do_folderu(src, dst):
    """Przenosi plik z src do dst."""
    shutil.move(src, dst)


class ManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Manager Gięcia - tkinter (z automatycznym statusem)")

        # Górny panel przycisków
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Button(self.button_frame, text="Odśwież", command=self.odswiez).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Przenieś do W_trakcie", command=self.przenies_do_w_trakcie).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Przenieś do Gotowe", command=self.przenies_do_gotowe).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Przenieś do Archiwum", command=self.przenies_do_archiwum).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Edytuj nazwę pliku", command=self.edytuj_nazwe_pliku).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Wyjście", command=self.root.destroy).pack(side=tk.RIGHT, padx=5)

        # Główna ramka z Canvas (przewijanie)
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.main_frame)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = tk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Ramka, w której wyświetlimy tabelę z wierszami
        self.table_frame = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.table_frame, anchor="nw")

        # Zmienne do przechowywania DataFrame i checkboxów
        self.df = None
        self.example_data = []  # list of dict
        self.row_indices = []   # indeksy w df
        self.check_vars = []    # BooleanVar do checkboxów

        # Po zmianie rozmiaru table_frame uaktualniamy scroll
        self.table_frame.bind("<Configure>", self.on_frame_configure)

        # Na start odświeżamy
        self.odswiez()

    def on_frame_configure(self, event):
        """Aktualizuje obszar przewijania canvasa."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def odswiez(self):
        """
        Wczytuje df z Excela, dla każdego wiersza sprawdza fizyczną lokalizację pliku (.dld)
        i na tej podstawie ustawia kolumnę Status (Nowe / W_trakcie / Gotowe / Archiwum / Nie znaleziono).
        Zapisuje zaktualizowany df do Excela, a następnie buduje listę w GUI (checkbox + etykiety).
        """
        # 1. Wczytaj plik Excel
        try:
            self.df = pd.read_excel(PATH_EXCEL)
        except FileNotFoundError:
            messagebox.showerror("Błąd", f"Nie znaleziono pliku: {PATH_EXCEL}")
            return

        # 2. Sprawdź fizyczne położenie plików i uaktualnij kolumnę Status
        for idx in self.df.index:
            nazwa_pliku = self.df.loc[idx, "Nazwa pliku"]

            path_nowe = os.path.join(PATH_NOWE, nazwa_pliku)
            path_wtrakcie = os.path.join(PATH_W_TRAKCIE, nazwa_pliku)
            path_gotowe = os.path.join(PATH_GOTOWE, nazwa_pliku)
            path_arch = os.path.join(PATH_ARCHIWUM, nazwa_pliku)

            if os.path.exists(path_nowe):
                aktualny_status = "Nowe"
            elif os.path.exists(path_wtrakcie):
                aktualny_status = "W trakcie"
            elif os.path.exists(path_gotowe):
                aktualny_status = "Gotowe"
            elif os.path.exists(path_arch):
                aktualny_status = "Archiwum"
            else:
                aktualny_status = "Nie znaleziono"

            # Jeśli status w Excelu jest inny - nadpisz
            if self.df.loc[idx, "Status"] != aktualny_status:
                self.df.loc[idx, "Status"] = aktualny_status

        # 3. Zapisz zaktualizowany df do Excela
        self.df.to_excel(PATH_EXCEL, index=False)

        # 4. Odtwórz structure do wyświetlenia w GUI
        self.example_data = self.df.to_dict('records')
        self.row_indices = self.df.index.tolist()

        # 5. Wyczyść table_frame
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        self.check_vars.clear()

        # 6. Dodaj nagłówki
        headers = ["", "ID", "Nazwa elementu", "Nazwa pliku", "Status"]
        for col_idx, col_name in enumerate(headers):
            lbl = tk.Label(self.table_frame, text=col_name, font=("Arial", 10, "bold"))
            lbl.grid(row=0, column=col_idx, padx=5, pady=5, sticky="w")

        # 7. Generuj wiersze z checkboxami i etykietami
        for i, row_data in enumerate(self.example_data, start=1):
            var = tk.BooleanVar(value=False)
            self.check_vars.append(var)

            # Checkbutton (kolumna 0)
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

        # Odśwież scrollbar
        self.on_frame_configure(None)

    def get_selected_indices(self):
        """Zwraca listę indeksów wierszy zaznaczonych checkboxem."""
        selected = []
        for idx, var in enumerate(self.check_vars):
            if var.get():
                selected.append(idx)
        return selected

    def przenies_do_w_trakcie(self):
        """
        Przenosi zaznaczone pliki z folderu Nowe -> W_trakcie i aktualizuje status
        (zwróć uwagę na limit 10 plików w W_trakcie).
        """
        selected_indices = self.get_selected_indices()

        # Policz, ile mamy już plików w W_trakcie
        files_w_trakcie = [f for f in os.listdir(PATH_W_TRAKCIE) if f.endswith('.dld')]
        current_count = len(files_w_trakcie)

        for s_idx in selected_indices:
            if current_count >= LIMIT_W_TRAKCIE:
                messagebox.showwarning("Limit", f"Osiągnięto limit {LIMIT_W_TRAKCIE} plików w W_trakcie!")
                break

            df_idx = self.row_indices[s_idx]
            nazwa_pliku = self.df.loc[df_idx, "Nazwa pliku"]

            src_path = os.path.join(PATH_NOWE, nazwa_pliku)
            dst_path = os.path.join(PATH_W_TRAKCIE, nazwa_pliku)

            if os.path.exists(src_path):
                przenies_do_folderu(src_path, dst_path)
                # Nie musimy tu ręcznie ustawiać statusu,
                # bo i tak w odswiez() się zaktualizuje wg folderu
                current_count += 1
            else:
                print(f"[UWAGA] Nie znaleziono pliku w Nowe: {nazwa_pliku}")

        # Po operacji - odśwież widok i status
        self.odswiez()

    def przenies_do_gotowe(self):
        """
        Przenosi zaznaczone pliki z folderu W_trakcie -> Gotowe.
        """
        selected_indices = self.get_selected_indices()
        for s_idx in selected_indices:
            df_idx = self.row_indices[s_idx]
            nazwa_pliku = self.df.loc[df_idx, "Nazwa pliku"]

            src_path = os.path.join(PATH_W_TRAKCIE, nazwa_pliku)
            dst_path = os.path.join(PATH_GOTOWE, nazwa_pliku)

            if os.path.exists(src_path):
                przenies_do_folderu(src_path, dst_path)
            else:
                print(f"[UWAGA] Nie znaleziono pliku w W_trakcie: {nazwa_pliku}")

        # Odśwież
        self.odswiez()

    def przenies_do_archiwum(self):
        """
        Przenosi zaznaczone pliki z folderu Gotowe -> Archiwum.
        Można dostosować w zależności od tego, skąd przenosimy.
        """
        selected_indices = self.get_selected_indices()
        for s_idx in selected_indices:
            df_idx = self.row_indices[s_idx]
            nazwa_pliku = self.df.loc[df_idx, "Nazwa pliku"]

            src_path = os.path.join(PATH_GOTOWE, nazwa_pliku)
            dst_path = os.path.join(PATH_ARCHIWUM, nazwa_pliku)

            if os.path.exists(src_path):
                przenies_do_folderu(src_path, dst_path)
            else:
                print(f"[UWAGA] Nie znaleziono pliku w Gotowe: {nazwa_pliku}")

        self.odswiez()

    def edytuj_nazwe_pliku(self):
        """
        Pozwala zmienić nazwę pliku .dld w Excelu i (opcjonalnie) w folderach.
        Tylko dla jednego zaznaczonego wiersza jednocześnie.
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

        # Zapytanie o nową nazwę
        nowa_nazwa = simpledialog.askstring(
            "Edycja nazwy pliku",
            f"Obecna nazwa: {stara_nazwa}\nPodaj nową nazwę (z rozszerzeniem .dld):"
        )
        if not nowa_nazwa:
            return  # Anulowano lub pusty

        # Znajdź, w którym folderze jest aktualnie plik, i zmień jego nazwę
        possible_folders = [PATH_NOWE, PATH_W_TRAKCIE, PATH_GOTOWE, PATH_ARCHIWUM]
        file_renamed = False

        for folder in possible_folders:
            old_path = os.path.join(folder, stara_nazwa)
            new_path = os.path.join(folder, nowa_nazwa)
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
                file_renamed = True
                break

        # Zaktualizuj w DataFrame i zapisz
        self.df.loc[df_idx, "Nazwa pliku"] = nowa_nazwa
        self.df.to_excel(PATH_EXCEL, index=False)

        if file_renamed:
            messagebox.showinfo("OK", f"Zmieniono nazwę pliku na '{nowa_nazwa}'.")
        else:
            messagebox.showwarning("Uwaga", f"Plik {stara_nazwa} nie został znaleziony w folderach.\n"
                                            "Zaktualizowano tylko nazwę w Excelu.")

        # Odśwież widok
        self.odswiez()


def main():
    root = tk.Tk()
    app = ManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
