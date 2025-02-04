import tkinter as tk
from tkinter import filedialog
import os
import shutil

chosen_file = 'dane.txt'  # Domyślny plik
chosen_folder = os.getcwd()  # Domyślny folder

def wczytaj_rysunki(plik):
    lista_rysunkow = []
    with open(plik, 'r') as f:
        for linia in f:
            lista_rysunkow.append(linia.strip())
    return lista_rysunkow

def przeksztalc_liste(lista):
    przeksztalcona_lista = []
    for element in lista:
        przeksztalcona_lista.append(element.strip())
    return przeksztalcona_lista

def choose_file():
    global chosen_file
    chosen_file = filedialog.askopenfilename(initialdir="/", title="Wybierz plik", filetypes=[('Text files', '*.txt')])
    if not chosen_file:
        chosen_file = 'dane.txt'

def choose_folder():
    global chosen_folder
    chosen_folder = filedialog.askdirectory(initialdir="/", title="Wybierz folder")
    if not chosen_folder:
        chosen_folder = os.getcwd()

def process_list():
    global chosen_file
    global chosen_folder

    lista_rysunkow = wczytaj_rysunki(chosen_file)
    nazwy_rysunkow = przeksztalc_liste(lista_rysunkow)
    
    folder_zrodlowy = chosen_folder
    folder_docelowy = "C:/tmp_rysunki/DXF"
    
    if not os.path.exists(folder_docelowy):
        os.makedirs(folder_docelowy)
    
    rozszerzenia = (".dxf")
    nieskopiowane_rysunki = []
    brakujace_rysunki = []

    for nazwa_rysunku in nazwy_rysunkow:
        znaleziono_rysunek = False
        for sciezka, foldery, pliki in os.walk(folder_zrodlowy):
            for plik in pliki:
                nazwa, rozszerzenie = os.path.splitext(plik)
                if rozszerzenie.lower() in rozszerzenia and nazwa_rysunku in nazwa:
                    znaleziono_rysunek = True
                    sciezka_zrodlowa = os.path.join(sciezka, plik)
                    sciezka_docelowa = os.path.join(folder_docelowy, plik)
                    try:
                        shutil.copy(sciezka_zrodlowa, sciezka_docelowa)
                    except shutil.Error:
                        nieskopiowane_rysunki.append(nazwa_rysunku)
                        break

        if not znaleziono_rysunek:
            brakujace_rysunki.append(nazwa_rysunku)
    
    result_box.config(state=tk.NORMAL)
    result_box.delete("1.0", tk.END)
    result_box.insert(tk.END, f"Dane pobrane \nz pliku: {chosen_file} \ni przetworzone.\n")
    
    if nieskopiowane_rysunki:
        result_box.insert(tk.END, "Nie udało się skopiować następujących rysunków:\n")
        result_box.insert(tk.END, "\n".join(nieskopiowane_rysunki) + "\n")
    if brakujace_rysunki:
        result_box.insert(tk.END, "Nie znaleziono następujących rysunków:\n")
        result_box.insert(tk.END, "\n".join(brakujace_rysunki) + "\n")
    
    result_box.config(state=tk.DISABLED)

window = tk.Tk()
window.title("Przetwarzanie listy rysunków")
window.geometry("500x500")

text_box = tk.Text(window, height=10, width=50)
text_box.pack()

choose_file_button = tk.Button(window, text="DANE - Wczytaj plik txt z DANYMI", command=choose_file)
choose_file_button.pack()

choose_folder_button = tk.Button(window, text="RYSUNKI - Wybierz folder", command=choose_folder)
choose_folder_button.pack()

process_button = tk.Button(window, text="Przetwórz", command=process_list)
process_button.pack()

result_box = tk.Text(window, height=10, width=50, state=tk.DISABLED)
result_box.pack()

window.mainloop()
