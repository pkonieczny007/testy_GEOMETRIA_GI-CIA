import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import pandas as pd
import os
import shutil

# --- KONFIGURACJE ŚCIEŻEK ---
BASE_PATH = r"C:\PYTHON\PROJEKT_GEOMETRIA_GIĘCIA\testy_MANAGER_GIECIA"
PATH_EXCEL = os.path.join(BASE_PATH, "ListaElementow.xlsx")

PATH_NOWE = os.path.join(BASE_PATH, "Nowe")
PATH_W_TRAKCIE = os.path.join(BASE_PATH, "W_trakcie")
PATH_GOTOWE = os.path.join(BASE_PATH, "Gotowe")
PATH_ARCHIWUM = os.path.join(BASE_PATH, "Archiwum")

# LIMIT plików w W_trakcie
LIMIT_W_TRAKCIE = 10

def przenies_do_folderu(src, dst):
    """Przenosi plik z src do dst."""
    shutil.move(src, dst)

class ManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Manager Gięcia - tkinter")

        # Ramka główna (przyciski) na górze
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(fill=tk.X, padx=5, pady=5)

        # Przyciski
        tk.Button(self.button_frame, text="Odśwież", command=self.odswiez).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Przenieś do W_trakcie", command=self.przenies_do_w_trakcie).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Przenieś do Gotowe", command=self.przenies_do_gotowe).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Przenieś do Archiwum", command=self.przenies_do_archiwum).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Edytuj nazwę pliku", command=self.edytuj_nazwe_pliku).pack(side=tk.LEFT, padx=5)
        tk.Button(self.button_frame, text="Wyjście", command=self.root.destroy).pack(side=tk.RIGHT, padx=5)

        # Ramka główna z Canvas (przewijanie)
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.main_frame)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = tk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Ramka wewnętrzna, gdzie trafia tabela (checkboxy + dane)
        self.table_frame = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.table_frame, anchor="nw")

        # Zmienne do przechowywania DataFrame
        self.df = None
        self.example_data = []
        self.row_indices = []
        self.check_vars = []  # BooleanVar dla każdego wiersza

        # Bind do przewijania
        self.table_frame.bind("<Configure>", self.on_frame_configure)

        # Na starcie odświeżamy dane
        self.odswiez()

    def on_frame_configure(self, event):
        """Aktualizuje obszar przewijania canvasa."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def odswiez(self):
        """
        Przycisk ODŚWIEŻ: wczytuje ponownie dane z Excela,
        usuwa stare elementy z table_frame i tworzy od nowa checkboxy + etykiety.
        """
        # Wczytanie df z pliku
        try:
            self.df = pd.read_excel(PATH_EXCEL)
        except FileNotFoundError:
            messagebox.showerror("Błąd", f"Nie znaleziono pliku: {PATH_EXCEL}")
            return

        # Konwersja do listy słowników + zapamiętanie oryginalnych indeksów
        self.example_data = self.df.to_dict('records')
        self.row_indices = self.df.index.tolist()  # np. [0,1,2,...]

        # Czyścimy table_frame
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        self.check_vars.clear()

        # Tworzymy nagłówek
        headers = ["", "ID", "Nazwa elementu", "Nazwa pliku", "Status"]
        for col_idx, col_name in enumerate(headers):
            lbl = tk.Label(self.table_frame, text=col_name, font=("Arial", 10, "bold"))
            lbl.grid(row=0, column=col_idx, padx=5, pady=5, sticky="w")

        # Generujemy wiersze z checkboxami
        for i, row_data in enumerate(self.example_data, start=1):
            var = tk.BooleanVar(value=False)
            self.check_vars.append(var)

            chk = tk.Checkbutton(self.table_frame, variable=var)
            chk.grid(row=i, column=0, padx=5, pady=2, sticky="w")

            # ID
            tk.Label(self.table_frame, text=row_data.get("ID", "")).grid(
                row=i, column=1, padx=5, pady=2, sticky="w"
            )
            # Nazwa elementu
            tk.Label(self.table_frame, text=row_data.get("Nazwa elementu", "")).grid(
                row=i, column=2, padx=5, pady=2, sticky="w"
            )
            # Nazwa pliku
            tk.Label(self.table_frame, text=row_data.get("Nazwa pliku", "")).grid(
                row=i, column=3, padx=5, pady=2, sticky="w"
            )
            # Status
            tk.Label(self.table_frame, text=row_data.get("Status", "")).grid(
                row=i, column=4, padx=5, pady=2, sticky="w"
            )

        # Odśwież scrollregion
        self.on_frame_configure(None)

    def get_selected_indices(self):
        """
        Zwraca listę indeksów (w self.example_data / self.row_indices)
        dla zaznaczonych (checkbox) wierszy.
        """
        selected = []
        for idx, var in enumerate(self.check_vars):
            if var.get():
                selected.append(idx)
        return selected

    def przenies_do_w_trakcie(self):
        selected_indices = self.get_selected_indices()

        # Sprawdź ile jest już plików w folderze W_trakcie
        w_trakcie_files = [f for f in os.listdir(PATH_W_TRAKCIE) if f.endswith('.dld')]
        current_count = len(w_trakcie_files)

        for s_idx in selected_indices:
            # Czy mamy jeszcze miejsce? (limit 10)
            if current_count >= LIMIT_W_TRAKCIE:
                messagebox.showwarning("Limit", f"Osiągnięto limit {LIMIT_W_TRAKCIE} plików w W_trakcie!")
                break

            df_idx = self.row_indices[s_idx]
            nazwa_pliku = self.df.loc[df_idx, "Nazwa pliku"]

            src_path = os.path.join(PATH_NOWE, nazwa_pliku)
            dst_path = os.path.join(PATH_W_TRAKCIE, nazwa_pliku)

            if os.path.exists(src_path):
                przenies_do_folderu(src_path, dst_path)
                self.df.loc[df_idx, "Status"] = "W trakcie"
                current_count += 1
            else:
                print(f"[UWAGA] Plik {src_path} nie istnieje!")

        # Zapis do Excela i ponowne odświeżenie
        self.df.to_excel(PATH_EXCEL, index=False)
        self.odswiez()

    def przenies_do_gotowe(self):
        selected_indices = self.get_selected_indices()
        for s_idx in selected_indices:
            df_idx = self.row_indices[s_idx]
            nazwa_pliku = self.df.loc[df_idx, "Nazwa pliku"]

            src_path = os.path.join(PATH_W_TRAKCIE, nazwa_pliku)
            dst_path = os.path.join(PATH_GOTOWE, nazwa_pliku)

            if os.path.exists(src_path):
                przenies_do_folderu(src_path, dst_path)
                self.df.loc[df_idx, "Status"] = "Gotowe"
            else:
                print(f"[UWAGA] Plik {src_path} nie istnieje!")

        self.df.to_excel(PATH_EXCEL, index=False)
        self.odswiez()

    def przenies_do_archiwum(self):
        """
        Funkcja przenosząca zaznaczone elementy (np. z Gotowe)
        do folderu Archiwum i ustawiająca Status = 'Archiwum'.
        Można ją zmodyfikować zależnie od stanu wyjściowego.
        """
        selected_indices = self.get_selected_indices()
        for s_idx in selected_indices:
            df_idx = self.row_indices[s_idx]
            nazwa_pliku = self.df.loc[df_idx, "Nazwa pliku"]
            status_aktualny = self.df.loc[df_idx, "Status"]

            # Załóżmy, że przenosimy z folderu Gotowe do Archiwum:
            src_path = os.path.join(PATH_GOTOWE, nazwa_pliku)
            dst_path = os.path.join(PATH_ARCHIWUM, nazwa_pliku)

            if os.path.exists(src_path):
                przenies_do_folderu(src_path, dst_path)
                self.df.loc[df_idx, "Status"] = "Archiwum"
            else:
                print(f"[UWAGA] Plik {src_path} nie istnieje (może jest w innym folderze?).")

        self.df.to_excel(PATH_EXCEL, index=False)
        self.odswiez()

    def edytuj_nazwe_pliku(self):
        """
        Prosta metoda edycji nazwy pliku dla *jednego* zaznaczonego wiersza.
        Pojawia się okienko dialogowe z Entry, w którym użytkownik wpisuje nową nazwę.
        """
        selected_indices = self.get_selected_indices()
        if len(selected_indices) == 0:
            messagebox.showinfo("Info", "Nie zaznaczono żadnego wiersza do edycji.")
            return
        if len(selected_indices) > 1:
            messagebox.showinfo("Info", "Zaznacz tylko jeden wiersz, aby edytować nazwę pliku.")
            return

        s_idx = selected_indices[0]   # jedyny wybrany
        df_idx = self.row_indices[s_idx]
        stara_nazwa = self.df.loc[df_idx, "Nazwa pliku"]

        # Zapytaj o nową nazwę
        nowa_nazwa = simpledialog.askstring("Edycja nazwy pliku", f"Obecna nazwa: {stara_nazwa}\nPodaj nową nazwę:")
        if not nowa_nazwa:
            return  # user kliknął Anuluj lub pusty

        # Jeżeli chcemy też fizycznie zmienić nazwę pliku w folderze, to:
        # 1) Szukamy, w którym folderze jest plik (Nowe, W_trakcie, Gotowe?).
        #    Dla uproszczenia – sprawdzamy w kilku folderach i przenosimy go z starą nazwą na nową.
        possible_folders = [PATH_NOWE, PATH_W_TRAKCIE, PATH_GOTOWE, PATH_ARCHIWUM]
        file_moved = False

        for folder in possible_folders:
            old_path = os.path.join(folder, stara_nazwa)
            new_path = os.path.join(folder, nowa_nazwa)
            if os.path.exists(old_path):
                # Zmień nazwę
                os.rename(old_path, new_path)
                file_moved = True
                break

        # Zaktualizuj w DataFrame
        self.df.loc[df_idx, "Nazwa pliku"] = nowa_nazwa
        self.df.to_excel(PATH_EXCEL, index=False)

        if file_moved:
            messagebox.showinfo("Sukces", f"Zmieniono nazwę pliku z '{stara_nazwa}' na '{nowa_nazwa}'.")
        else:
            messagebox.showinfo("Uwaga", f"Zaktualizowano nazwę w Excelu, ale nie znaleziono pliku '{stara_nazwa}' w folderach.")

        # Odśwież widok
        self.odswiez()

def main():
    root = tk.Tk()
    app = ManagerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
