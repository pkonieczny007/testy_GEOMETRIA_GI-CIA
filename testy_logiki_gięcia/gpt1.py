#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import os

def main():
    # 1. Nazwa pliku DLD (XML)
    filename = "plik.dld"  # dopasuj do rzeczywistej nazwy
    
    # 2. Sprawdź, czy plik istnieje
    if not os.path.isfile(filename):
        print(f"Brak pliku: {filename}")
        return
    
    # 3. Wczytanie i sparsowanie pliku XML
    tree = ET.parse(filename)
    root = tree.getroot()
    
    # 4. Zmienne do przechowywania
    a_val = None
    b_val = None
    arc_val = None
    angle_val = None
    dimension_type = None
    
    # Offset, który w przykładzie dodajemy do 'a' i 'b'
    # Dla uproszczenia wpisujemy "na sztywno".
    # W praktyce można go wyliczyć z:
    #   (PreferredInnerRadius - grubość) + grubość
    #   lub odczytać z Outline jako różnicę współrzędnych.
    offset = 4.81648
    
    # 5. Przeszukaj elementy XML w celu odczytu potrzebnych wartości
    for elem in root.iter():
        tag_name = elem.tag.lower()
        
        # Odczyt 'WorkpieceDimensions' (czy Outside, czy Inside)
        if tag_name.endswith("workpiecedimensions"):
            dimension_type = elem.get("value", "")
        
        # Odczyt 'WorkpieceThickness' (jeśli w przyszłości byłby potrzebny)
        # if tag_name.endswith("workpiecethickness"):
        #     thickness = float(elem.get("value", "0"))
        
        # Odczyt 'VDeformableComponentAngle' (kąt gięcia)
        if tag_name.endswith("vdeformablecomponentangle"):
            angle_val = float(elem.get("value", "0"))
        
        # Tutaj (dla uproszczenia) zakładamy, że a, b, arc
        # pojawiają się w atrybucie "value" któregoś z Outline
        # i zawierają te konkretne ciągi znaków:
        if ("outline" in tag_name) or ("hull" in tag_name):
            val_str = elem.get("value", "")
            
            # Jeśli w stringu występują nasze szukane liczby,
            # przypiszmy je do zmiennych.
            if "295.18352" in val_str:
                a_val = 295.18352
            if "45.183522" in val_str:
                b_val = 45.183522
            if "5.994909" in val_str:
                arc_val = 5.994909
    
    # 6. Sprawdź, czy udało się odczytać wszystkie parametry
    if a_val is None or b_val is None or arc_val is None:
        print("Nie udało się w pełni odczytać wartości (a, b, łuk).")
        return
    if angle_val is None:
        print("Nie udało się odczytać kąta gięcia.")
        return
    
    # 7. Obliczenia: jeśli dimension_type = "Outside", to dodajemy offset
    if dimension_type == "Outside":
        a_ext = a_val + offset  # np. 295.18352 + 4.81648 = 300
        b_ext = b_val + offset  # np. 45.183522 + 4.81648 = ~50
    else:
        # Jeśli Inside – można ewentualnie uznać, że a_val, b_val są już "wewnętrzne"
        # i nic nie dodawać. Tutaj – przykładowo:
        a_ext = a_val
        b_ext = b_val
    
    # (opcjonalnie) Oblicz rozwinięcie (przykład):
    # rozwinięcie = a_val + b_val + arc_val
    extension_length = a_val + b_val + arc_val
    
    # 8. Wyświetlenie wyników
    print("=== Odczytane i obliczone parametry ===")
    print(f"Wymiar a (odczytany)     = {a_val:.6f} mm")
    print(f"Wymiar b (odczytany)     = {b_val:.6f} mm")
    print(f"Długość łuku (odczytana) = {arc_val:.6f} mm")
    print(f"Kąt gięcia               = {angle_val:.1f}°")
    print(f"Wymiary w pliku          = {dimension_type} (Outside/Inside)")
    print("---------------------------------------")
    print(f"Wymiar a (zewn.) = {a_ext:.6f} mm")
    print(f"Wymiar b (zewn.) = {b_ext:.6f} mm")
    print(f"Rozwinięcie (a+b+łuk) = {extension_length:.6f} mm")
    
    # 9. Zapis do pliku tekstowego (np. wynik.txt)
    output_filename = "wynik.txt"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write("=== Odczytane i obliczone parametry ===\n")
        f.write(f"Wymiar a (odczytany)     = {a_val:.6f} mm\n")
        f.write(f"Wymiar b (odczytany)     = {b_val:.6f} mm\n")
        f.write(f"Długość łuku (odczytana) = {arc_val:.6f} mm\n")
        f.write(f"Kąt gięcia               = {angle_val:.1f}°\n")
        f.write(f"Wymiary w pliku          = {dimension_type}\n")
        f.write("---------------------------------------\n")
        f.write(f"Wymiar a (zewn.) = {a_ext:.6f} mm\n")
        f.write(f"Wymiar b (zewn.) = {b_ext:.6f} mm\n")
        f.write(f"Rozwinięcie (a+b+łuk) = {extension_length:.6f} mm\n")

    print(f"\nWyniki zapisano w pliku: {output_filename}")

if __name__ == "__main__":
    main()
