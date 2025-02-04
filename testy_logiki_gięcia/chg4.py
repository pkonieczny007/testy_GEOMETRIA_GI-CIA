#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import os
import re

def parse_outline_value(value_str):
    """
    Z pliku Delem (np. '4 0 6.613518 200 6.613518 false ...') 
    wyciąga pary (x, y) i zwraca listę krotek [(x1,y1), (x2,y2), ...].
    Pomija słowa 'true'/'false'.
    """
    tokens = value_str.split()
    # Pierwszy token to liczba segmentów (np. '4' lub '1 Outline 4'), 
    # ale często bywa to zlepione. Rozbijmy i zbierzmy same liczby float, 
    # ignorując 'Outline', 'true', 'false' itd.
    
    numeric_vals = []
    for t in tokens:
        # Pomijamy 'Outline', 'true', 'false' itp.
        if t.lower() in ['outline', 'true', 'false']:
            continue
        # Spróbujmy skonwertować na float
        try:
            numeric_vals.append(float(t))
        except ValueError:
            # Jeśli się nie da (np. to może być 'Line' lub inny napis), ignorujemy
            pass
    
    # Teraz numeric_vals to ciąg liczb, np.
    # [4, 0, 6.613518, 200, 6.613518, 200, 6.613518, 200, 300, ... ]
    # Pierwsza liczba to z reguły ilość segmentów. 
    # My chcemy pary (x,y) z kolejnych liczb.
    
    if not numeric_vals:
        return []
    
    # Jeśli pierwsza liczba to segmentCount -> usuńmy ją
    # (często to '4' albo '1' w wypadku '1 Outline 4')
    segment_count = int(numeric_vals[0])
    coords = numeric_vals[1:]  # reszta
    
    # Czasem bywa, że jest '1 Outline 4' => segment_count = 1, 
    # a potem jest 4 (jako kolejna).
    # Bywa więc, że realnie ta pierwsza "1" wcale nie jest segmentCountem 
    # do samych współrzędnych. 
    # Dla pewności możesz wykryć, jeżeli w coords wciaż są np. 4 segmenty,
    # to nadpisz segment_count = 4. 
    # TUTAJ: uprościmy (bo w Delem różnie bywa). 
    # W razie czego możesz w pętli sprawdzać i adaptować.
    
    # Teraz z coords bierzemy parami (x, y)
    points = []
    # lecimy co 2
    for i in range(0, len(coords), 2):
        # Upewniamy się, że nie wyjdziemy poza listę
        if i+1 < len(coords):
            x = coords[i]
            y = coords[i+1]
            points.append((x, y))
    
    return points

def bounding_box(coords):
    """
    Dla listy punktów [(x1,y1), (x2,y2), ...] 
    zwraca (xmin, xmax, ymin, ymax).
    Jeśli brak punktów, zwraca (0,0,0,0).
    """
    if not coords:
        return 0, 0, 0, 0
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    return min(xs), max(xs), min(ys), max(ys)

def width_height_from_box(xmin, xmax, ymin, ymax):
    """Zwraca (width, height) = (xmax - xmin, ymax - ymin)."""
    return abs(xmax - xmin), abs(ymax - ymin)

def main():
    filename = "china.dld"  # Dopasuj do nazwy swojego pliku
    
    if not os.path.isfile(filename):
        print(f"Brak pliku: {filename}")
        return
    
    # Parsujemy plik
    tree = ET.parse(filename)
    root = tree.getroot()
    
    # Zmienne: chcemy kąt, grubość, promień, tryb Outside/Inside
    angle_val = None
    thickness_val = None
    radius_val = None
    dimension_type = None
    
    # Bounding boxy dla poszczególnych komponentów
    bb_mainplane = None
    bb_sc00 = None
    bb_dc00 = None
    
    # Przeszukujemy XML
    for elem in root.iter():
        tag_name = elem.tag.lower()
        
        # Atrybuty ogólne
        if tag_name.endswith("workpiecedimensions"):
            dimension_type = elem.get("value", "")  # "Outside" / "Inside"
        if tag_name.endswith("vdeformablecomponentangle"):
            angle_val = float(elem.get("value", "0"))
        if tag_name.endswith("workpiecethickness"):
            thickness_val = float(elem.get("value", "0"))
        if tag_name.endswith("preferredinnerradius"):
            radius_val = float(elem.get("value", "0"))
        
        # Odczyt Outline/Hull -> bounding box
        if tag_name.endswith("staticcomponent"):
            # Sprawdzamy nazwę komponentu: MainPlane? SC00? itp.
            wp_name = elem.find("./WorkpieceComponentName")
            if wp_name is not None:
                comp_name = wp_name.get("value", "")
                
                # Szukamy <StaticComponentPart><StaticComponentHull ...> w tym komponencie
                hull_elem = elem.find("./StaticComponentPart/StaticComponentHull")
                if hull_elem is not None:
                    val_str = hull_elem.get("value", "")
                    coords = parse_outline_value(val_str)
                    box = bounding_box(coords)
                    
                    if comp_name == "MainPlane":
                        bb_mainplane = box
                    elif comp_name == "SC00":
                        bb_sc00 = box
        
        # Deformowalny komponent DC00
        if tag_name.endswith("vdeformablecomponent"):
            # Sprawdzamy, czy to jest DC00
            wp_name = elem.find("./WorkpieceComponentName")
            if wp_name is not None:
                comp_name = wp_name.get("value", "")
                if comp_name == "DC00":
                    # Znajdź <VDeformableComponentHulls ...>
                    hulls_elem = elem.find("./VDeformableComponentHulls")
                    if hulls_elem is not None:
                        val_str = hulls_elem.get("value", "")
                        coords = parse_outline_value(val_str)
                        box = bounding_box(coords)
                        bb_dc00 = box
    
    # Sprawdzamy odczyty
    if thickness_val is None or radius_val is None:
        print("Brak odczytu grubości lub promienia.")
        return
    if angle_val is None:
        print("Brak odczytu kąta gięcia.")
        return
    if bb_mainplane is None:
        print("Nie znaleziono bounding boxa dla MainPlane.")
        return
    if bb_sc00 is None:
        print("Nie znaleziono bounding boxa dla SC00.")
        return
    if bb_dc00 is None:
        print("Nie znaleziono bounding boxa dla DC00 (łuku?).")
        return
    
    # Rozpakowanie bounding boxów
    (mp_xmin, mp_xmax, mp_ymin, mp_ymax) = bb_mainplane
    (sc_xmin, sc_xmax, sc_ymin, sc_ymax) = bb_sc00
    (dc_xmin, dc_xmax, dc_ymin, dc_ymax) = bb_dc00
    
    # Wyliczamy szerokość i wysokość
    mp_width, mp_height = width_height_from_box(mp_xmin, mp_xmax, mp_ymin, mp_ymax)
    sc_width, sc_height = width_height_from_box(sc_xmin, sc_xmax, sc_ymin, sc_ymax)
    dc_width, dc_height = width_height_from_box(dc_xmin, dc_xmax, dc_ymin, dc_ymax)
    
    # Załóżmy, że "a" to większy z wymiarów (MainPlane),
    # "b" to mniejszy z wymiarów (SC00),
    # "łuk" to mniejszy z wymiarów (DC00).
    # (To przykład – w realnych sytuacjach może być inna logika.)
    
    mp_a = max(mp_width, mp_height)  # np. ~293.386...
    sc_b = min(sc_width, sc_height)  # np. ~43.386...
    dc_arc = min(dc_width, dc_height)  # np. ~8.924773
    
    # Obliczenie offsetu (jeśli Outside i chcemy go dodać):
    offset = radius_val + thickness_val  # np. 3.61352 + 3 = 6.61352
    
    # Jeśli plik jest "Outside", możemy uznać, że a, b
    # to już wartości uwzględniające offset, 
    # ale w niektórych projektach robimy a_ext = mp_a + offset.
    # Tutaj – przykład: 
    if dimension_type == "Outside":
        a_ext = mp_a  # bo bounding box już jest "zewnętrzny"? 
        b_ext = sc_b
    else:
        # Gdyby to było Inside, można by dodać offset. 
        # W Delem bywa różnie, to zależy od definicji. 
        # Dla przykładu odwróćmy logikę:
        a_ext = mp_a + offset
        b_ext = sc_b + offset
    
    # Prosta formuła na rozwinięcie (wielkie uproszczenie!): a + b + arc
    extension_length = mp_a + sc_b + dc_arc
    
    # Wypisanie
    print("=== Odczyt z pliku DLD (metoda bounding box) ===")
    print(f"WorkpieceDimensions = {dimension_type}")
    print(f"Kąt gięcia          = {angle_val}°")
    print(f"Grubość             = {thickness_val} mm")
    print(f"Promień wewn.       = {radius_val} mm")
    print("-------------------------------------------")
    print(f"[MainPlane] width={mp_width:.6f}  height={mp_height:.6f} => a={mp_a:.6f}")
    print(f"[SC00]      width={sc_width:.6f} height={sc_height:.6f} => b={sc_b:.6f}")
    print(f"[DC00]      width={dc_width:.6f} height={dc_height:.6f} => łuk={dc_arc:.6f}")
    print(f"Offset (r+g)        = {offset:.6f} mm")
    print("-------------------------------------------")
    print(f"a (zewn.) = {a_ext:.6f} mm")
    print(f"b (zewn.) = {b_ext:.6f} mm")
    print(f"Rozwinięcie (a+b+łuk) = {extension_length:.6f} mm")
    
    # Zapis do pliku txt
    with open("wynik.txt", "w", encoding="utf-8") as f:
        f.write("=== Odczyt z pliku DLD (metoda bounding box) ===\n")
        f.write(f"WorkpieceDimensions = {dimension_type}\n")
        f.write(f"Kąt gięcia          = {angle_val}°\n")
        f.write(f"Grubość             = {thickness_val} mm\n")
        f.write(f"Promień wewn.       = {radius_val} mm\n")
        f.write("-------------------------------------------\n")
        f.write(f"[MainPlane] width={mp_width:.6f}  height={mp_height:.6f} => a={mp_a:.6f}\n")
        f.write(f"[SC00]      width={sc_width:.6f} height={sc_height:.6f} => b={sc_b:.6f}\n")
        f.write(f"[DC00]      width={dc_width:.6f} height={dc_height:.6f} => łuk={dc_arc:.6f}\n")
        f.write(f"Offset (r+g)        = {offset:.6f} mm\n")
        f.write("-------------------------------------------\n")
        f.write(f"a (zewn.) = {a_ext:.6f} mm\n")
        f.write(f"b (zewn.) = {b_ext:.6f} mm\n")
        f.write(f"Rozwinięcie (a+b+łuk) = {extension_length:.6f} mm\n")
    
    print("\nWyniki zapisano do pliku: wynik.txt")

if __name__ == "__main__":
    main()
