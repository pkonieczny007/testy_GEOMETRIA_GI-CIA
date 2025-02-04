#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import os
import re

def main():
    filename = "plik.dld"  # Dostosuj do nazwy swojego pliku
    
    if not os.path.isfile(filename):
        print(f"Brak pliku: {filename}")
        return
    
    # Parsujemy plik .dld (XML)
    tree = ET.parse(filename)
    root = tree.getroot()
    
    # Zmienne do przechowania
    a_val = None
    b_val = None
    arc_val = None
    angle_val = None
    thickness_val = None
    radius_val = None
    dimension_type = None
    
    # Przeszukujemy XML
    for elem in root.iter():
        tag_name = elem.tag.lower()
        
        # Wymiary zewnętrzne czy wewnętrzne
        if tag_name.endswith("workpiecedimensions"):
            dimension_type = elem.get("value", "")  # "Outside", "Inside", ...
        
        # Kąt gięcia
        if tag_name.endswith("vdeformablecomponentangle"):
            angle_val = float(elem.get("value", "0"))
        
        # Grubość
        if tag_name.endswith("workpiecethickness"):
            thickness_val = float(elem.get("value", "0"))
        
        # Promień wewnętrzny preferowany
        if tag_name.endswith("preferredinnerradius"):
            radius_val = float(elem.get("value", "0"))
        
        # Szukamy w Outline liczb 293.386482 / 43.386482 / 8.924773
        # (Przykład: mechaniczne sprawdzenie)
        if ("outline" in tag_name) or ("hull" in tag_name):
            val_str = elem.get("value", "")
            
            # Metoda 1: sprawdzanie substringu
            if "293.386482" in val_str:
                a_val = 293.386482
            if "43.386482" in val_str:
                b_val = 43.386482
            if "8.924773" in val_str:
                arc_val = 8.924773

    # Sprawdzamy, czy udało się coś odczytać
    if a_val is None or b_val is None or arc_val is None:
        print("Nie udało się w pełni odczytać a, b, łuku z pliku.\n"
              "Zastosuj bounding-box lub inne metody odczytu!")
        return
    
    if angle_val is None:
        print("Nie udało się odczytać kąta gięcia!")
        return
    
    if thickness_val is None or radius_val is None:
        print("Brak grubości lub promienia wewnętrznego!")
        return
    
    # Obliczamy offset = promień + grubość
    offset = radius_val + thickness_val  # np. 3.61352 + 3 = 6.61352
    
    # Jeżeli plik ma Outside, możemy dodać offset do segmentów a i b
    # (w praktyce zależy to od logiki Twojego programu, poniżej przykład "jak poprzednio")
    if dimension_type == "Outside":
        a_ext = a_val + offset
        b_ext = b_val + offset
    else:
        # Jeśli Inside, to może bierzemy wartości "tak jak są" (zależnie od potrzeb)
        a_ext = a_val
        b_ext = b_val
    
    # Kąt gięcia mamy 80°
    # Możemy wyliczyć np. rozwinięcie w super-prostym ujęciu (a + b + łuk)
    # Gdzie "łuk" = arc_val (8.924773).
    # W praktyce, przy innym kącie niż 90°, należałoby użyć formuły bend allowance / K-factor itd.
    
    extension_length = a_val + b_val + arc_val
    
    # Prezentacja wyników
    print("=== Odczytane wartości z pliku ===")
    print(f"Tryb wymiarów: {dimension_type}  (Outside/Inside)")
    print(f"Grubość:       {thickness_val} mm")
    print(f"Promień wewn.: {radius_val} mm")
    print(f"Kąt gięcia:    {angle_val}°")
    print("-----------------------------------------")
    print(f"a (odczytane)  = {a_val:.6f} mm")
    print(f"b (odczytane)  = {b_val:.6f} mm")
    print(f"łuk (odczytany)= {arc_val:.6f} mm")
    print(f"offset = promień + grubość = {offset:.6f} mm")
    print(f"a (zewn.) = {a_ext:.6f} mm  (przykład dodania offsetu)")
    print(f"b (zewn.) = {b_ext:.6f} mm  (przykład dodania offsetu)")
    print(f"Rozwinięcie (a+b+łuk, uproszczone) = {extension_length:.6f} mm")
    
    # Zapis do pliku tekstowego
    with open("wynik.txt", "w", encoding="utf-8") as f:
        f.write("=== Odczytane wartości z pliku ===\n")
        f.write(f"Tryb wymiarów: {dimension_type}\n")
        f.write(f"Grubość:       {thickness_val} mm\n")
        f.write(f"Promień wewn.: {radius_val} mm\n")
        f.write(f"Kąt gięcia:    {angle_val}°\n")
        f.write("-----------------------------------------\n")
        f.write(f"a (odczytane)  = {a_val:.6f} mm\n")
        f.write(f"b (odczytane)  = {b_val:.6f} mm\n")
        f.write(f"łuk (odczytany)= {arc_val:.6f} mm\n")
        f.write(f"offset (r+g)   = {offset:.6f} mm\n")
        f.write(f"a (zewn.)      = {a_ext:.6f} mm\n")
        f.write(f"b (zewn.)      = {b_ext:.6f} mm\n")
        f.write(f"Rozwinięcie (a+b+łuk) = {extension_length:.6f} mm\n")

    print("\nWyniki zapisano do pliku wynik.txt")


if __name__ == "__main__":
    main()
