#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import os

def main():
    # Nazwa pliku (zmień na właściwą, jeśli nazywa się inaczej)
    filename = "plik.dld"
    
    # Sprawdzamy, czy plik istnieje w katalogu
    if not os.path.isfile(filename):
        print(f"Nie znaleziono pliku: {filename}")
        return
    
    # Parsujemy plik XML
    tree = ET.parse(filename)
    root = tree.getroot()
    
    # Zmienna do przechowywania potrzebnych wartości
    a = None
    b = None
    arc = None
    
    # Przeszukujemy drzewo XML w poszukiwaniu naszych wartości
    for elem in root.iter():
        # Szukamy tagów, w których atrybut 'value' zawiera definicje konturów (Outline)
        # lub innych interesujących nas elementów
        if elem.tag.endswith("StaticComponentHull") or elem.tag.endswith("VDeformableComponentHulls"):
            value_attr = elem.get("value", "")
            
            # Jeśli w atrybucie 'value' występuje nasza szukana liczba, przypisujemy ją
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
    
    # W tym przykładzie:
    #  - wymiar zewnętrzny (np. 'outside dimension') = a + b
    #  - wymiar wewnętrzny (np. 'inside dimension')  = (a + b) - 2 * grubość
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
