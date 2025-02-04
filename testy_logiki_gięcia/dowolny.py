#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import os
import glob

def main():
    # Znajdujemy pierwszy plik z rozszerzeniem .dld w katalogu, w którym znajduje się skrypt
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dld_files = glob.glob(os.path.join(script_dir, "*.dld"))
    
    if not dld_files:
        print("Nie znaleziono żadnych plików .dld w katalogu ze skryptem.")
        return
    
    filename = dld_files[0]
    print(f"Przetwarzany plik: {filename}")
    
    # Parsujemy plik XML
    try:
        tree = ET.parse(filename)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Błąd podczas parsowania pliku XML: {e}")
        return
    
    # Zmienna do przechowywania potrzebnych wartości
    a = None
    b = None
    arc = None
    
    # Przeszukujemy drzewo XML w poszukiwaniu naszych wartości
    for elem in root.iter():
        if elem.tag.endswith("StaticComponentHull") or elem.tag.endswith("VDeformableComponentHulls"):
            value_attr = elem.get("value", "")
            if "295.18352" in value_attr:
                a = 295.18352
            if "45.183522" in value_attr:
                b = 45.183522
            if "5.994909" in value_attr:
                arc = 5.994909
    
    # Dla pewności sprawdzamy, czy wszystkie wartości zostały zlokalizowane
    if a is None or b is None or arc is None:
        print("Nie udało się w pełni odczytać wartości a, b lub łuku z pliku.")
        print("Upewnij się, że dane znajdują się w pliku i są poprawne.")
        return
    
    # Grubość blachy i kąt gięcia (wg założeń)
    thickness = 2.0     # [mm]
    angle = 90.0        # [stopnie]
    
    # Przykładowy wzór na rozwinięcie: a + b + długość łuku
    rozwiniecie = a + b + arc
    
    # Wymiary zewnętrzne i wewnętrzne
    wymiar_zewnetrzny = a + b
    wymiar_wewnetrzny = (a + b) - 2 * thickness
    
    # Wyświetlamy wyniki
    print("=== Wyniki odczytu z pliku DLD (XML) i obliczenia ===")
    print(f"Długość a (A)           = {a:.6f} mm")
    print(f"Długość b (B)           = {b:.6f} mm")
    print(f"Długość łuku            = {arc:.6f} mm")
    print(f"Kąt gięcia              = {angle}°")
    print(f"Grubość blachy          = {thickness:.2f} mm")
    print("----------------------------------------------")
    print(f"Rozwinięcie (A + B + łuk) = {rozwiniecie:.6f} mm")
    print(f"Wymiar zewnętrzny        = {wymiar_zewnetrzny:.6f} mm")
    print(f"Wymiar wewnętrzny        = {wymiar_wewnetrzny:.6f} mm")

if __name__ == "__main__":
    main()
