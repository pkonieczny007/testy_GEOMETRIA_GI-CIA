#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import os
import re
import glob
import sys

def parse_outline_value(value_str):
    """
    Z pliku Delem (np. '4 0 6.613518 200 6.613518 false ...') 
    wyciąga pary (x, y) i zwraca listę krotek [(x1,y1), (x2,y2), ...].
    Pomija słowa 'true'/'false'.
    """
    tokens = value_str.split()
    numeric_vals = []
    for t in tokens:
        if t.lower() in ['outline', 'true', 'false']:
            continue
        try:
            numeric_vals.append(float(t))
        except ValueError:
            pass
    if not numeric_vals:
        return []
    segment_count = int(numeric_vals[0])
    coords = numeric_vals[1:]
    points = []
    for i in range(0, len(coords), 2):
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

def process_file(filename, output_dir):
    if not os.path.isfile(filename):
        print(f"Brak pliku: {filename}")
        return
    
    try:
        tree = ET.parse(filename)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Błąd parsowania pliku {filename}: {e}")
        return
    
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
            try:
                angle_val = float(elem.get("value", "0"))
            except ValueError:
                angle_val = 0.0
        if tag_name.endswith("workpiecethickness"):
            try:
                thickness_val = float(elem.get("value", "0"))
            except ValueError:
                thickness_val = 0.0
        if tag_name.endswith("preferredinnerradius"):
            try:
                radius_val = float(elem.get("value", "0"))
            except ValueError:
                radius_val = 0.0
        
        # Odczyt Outline/Hull -> bounding box
        if tag_name.endswith("staticcomponent"):
            wp_name = elem.find("./WorkpieceComponentName")
            if wp_name is not None:
                comp_name = wp_name.get("value", "")
                
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
            wp_name = elem.find("./WorkpieceComponentName")
            if wp_name is not None:
                comp_name = wp_name.get("value", "")
                if comp_name == "DC00":
                    hulls_elem = elem.find("./VDeformableComponentHulls")
                    if hulls_elem is not None:
                        val_str = hulls_elem.get("value", "")
                        coords = parse_outline_value(val_str)
                        box = bounding_box(coords)
                        bb_dc00 = box
    
    # Sprawdzamy odczyty
    if thickness_val is None or radius_val is None:
        print(f"Plik {filename}: Brak odczytu grubości lub promienia.")
        return
    if angle_val is None:
        print(f"Plik {filename}: Brak odczytu kąta gięcia.")
        return
    if bb_mainplane is None:
        print(f"Plik {filename}: Nie znaleziono bounding boxa dla MainPlane.")
        return
    if bb_sc00 is None:
        print(f"Plik {filename}: Nie znaleziono bounding boxa dla SC00.")
        return
    if bb_dc00 is None:
        print(f"Plik {filename}: Nie znaleziono bounding boxa dla DC00 (łuku?).")
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
    mp_a = max(mp_width, mp_height)
    sc_b = min(sc_width, sc_height)
    dc_arc = min(dc_width, dc_height)
    
    # Obliczenie offsetu (jeśli Outside i chcemy go dodać):
    offset = radius_val + thickness_val
    
    # Jeśli plik jest "Outside", możemy uznać, że a, b
    # to już wartości uwzględniające offset, 
    # ale w niektórych projektach robimy a_ext = mp_a + offset.
    if dimension_type == "Outside":
        a_ext = mp_a
        b_ext = sc_b
    else:
        a_ext = mp_a + offset
        b_ext = sc_b + offset
    
    # Prosta formuła na rozwinięcie (wielkie uproszczenie!): a + b + arc
    extension_length = mp_a + sc_b + dc_arc
    
    # Przygotowanie wyników
    wynik = []
    wynik.append("=== Odczyt z pliku DLD (metoda bounding box) ===")
    wynik.append(f"WorkpieceDimensions = {dimension_type}")
    wynik.append(f"Kąt gięcia          = {angle_val}°")
    wynik.append(f"Grubość             = {thickness_val} mm")
    wynik.append(f"Promień wewn.       = {radius_val} mm")
    wynik.append("-------------------------------------------")
    wynik.append(f"[MainPlane] width={mp_width:.6f}  height={mp_height:.6f} => a={mp_a:.6f}")
    wynik.append(f"[SC00]      width={sc_width:.6f} height={sc_height:.6f} => b={sc_b:.6f}")
    wynik.append(f"[DC00]      width={dc_width:.6f} height={dc_height:.6f} => łuk={dc_arc:.6f}")
    wynik.append(f"Offset (r+g)        = {offset:.6f} mm")
    wynik.append("-------------------------------------------")
    wynik.append(f"a (zewn.) = {a_ext:.6f} mm")
    wynik.append(f"b (zewn.) = {b_ext:.6f} mm")
    wynik.append(f"Rozwinięcie (a+b+łuk) = {extension_length:.6f} mm")
    
    wynik_text = "\n".join(wynik)
    
    # Wyświetlenie wyników w konsoli
    print(f"\n=== Wyniki dla pliku: {os.path.basename(filename)} ===")
    print(wynik_text)
    
    # Zapis do pliku txt
    base_name = os.path.splitext(os.path.basename(filename))[0]
    output_filename = os.path.join(output_dir, f"wynik_{base_name}.txt")
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(wynik_text)
        print(f"Wyniki zapisano do pliku: {output_filename}")
    except IOError as e:
        print(f"Błąd zapisu pliku {output_filename}: {e}")

def main():
    # Określ folder z plikami .dld
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = os.getcwd()  # Bieżący katalog
    
    if not os.path.isdir(folder):
        print(f"Podany folder nie istnieje: {folder}")
        return
    
    # Utwórz folder na wyniki, jeśli nie istnieje
    output_dir = os.path.join(folder, "wyniki")
    os.makedirs(output_dir, exist_ok=True)
    
    # Znajdź wszystkie pliki .dld w folderze
    pattern = os.path.join(folder, "*.dld")
    files = glob.glob(pattern)
    
    if not files:
        print(f"Nie znaleziono żadnych plików .dld w folderze: {folder}")
        return
    
    print(f"Znaleziono {len(files)} plików .dld w folderze: {folder}\n")
    
    # Przetwarzaj każdy plik
    for file in files:
        process_file(file, output_dir)
    
    print("\nPrzetwarzanie zakończone.")

if __name__ == "__main__":
    main()
