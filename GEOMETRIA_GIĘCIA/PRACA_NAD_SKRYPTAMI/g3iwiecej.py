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
    
    # Zmienne ogólne
    dimension_type = None
    thickness_val = 0.0       # Inicjalizacja grubości
    radius_val = 0.0          # Inicjalizacja promienia wewn.
    mainplane_info = {}
    sc00_info = {}
    bends = []  # Lista na informacje o gięciach
    
    # Przeszukujemy XML
    for elem in root.iter():
        tag_name = elem.tag.lower()
        
        # Atrybuty ogólne
        if tag_name.endswith("workpiecedimensions"):
            dimension_type = elem.get("value", "")  # "Outside" / "Inside"
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
        
        # Odczyt Outline/Hull -> bounding box dla MainPlane i SC00
        if tag_name.endswith("staticcomponent"):
            wp_name = elem.find("./WorkpieceComponentName")
            if wp_name is not None:
                comp_name = wp_name.get("value", "")
                
                hull_elem = elem.find("./StaticComponentPart/StaticComponentHull")
                if hull_elem is not None:
                    val_str = hull_elem.get("value", "")
                    coords = parse_outline_value(val_str)
                    box = bounding_box(coords)
                    width, height = width_height_from_box(*box)
                    a = max(width, height)
                    b = min(width, height)
                    
                    if comp_name == "MainPlane":
                        mainplane_info = {
                            "box": box,
                            "width": width,
                            "height": height,
                            "a": a
                        }
                    elif comp_name == "SC00":
                        sc00_info = {
                            "box": box,
                            "width": width,
                            "height": height,
                            "b": b
                        }
        
        # Deformowalny komponent - Gięcie
        if tag_name.endswith("vdeformablecomponent"):
            wp_name = elem.find("./WorkpieceComponentName")
            if wp_name is not None:
                comp_name = wp_name.get("value", "")
                # Zakładamy, że gięcia mają nazwy zaczynające się od "DC"
                if re.match(r'^DC\d+', comp_name):
                    hulls_elem = elem.find("./VDeformableComponentHulls")
                    if hulls_elem is not None:
                        val_str = hulls_elem.get("value", "")
                        coords = parse_outline_value(val_str)
                        box = bounding_box(coords)
                        width, height = width_height_from_box(*box)
                        arc = min(width, height)
                        
                        # Pobranie wartości kąta, grubości i promienia
                        angle_elem = elem.find("./VDeformableComponentAngle")
                        # thickness_val i radius_val są już zdefiniowane wcześniej
                        
                        try:
                            angle = float(angle_elem.get("value", "0")) if angle_elem is not None else 0.0
                        except ValueError:
                            angle = 0.0
                        
                        bends.append({
                            "name": comp_name,
                            "angle": angle,
                            "thickness": thickness_val,  # Używamy ogólnej grubości
                            "radius": radius_val,        # Używamy ogólnego promienia
                            "box": box,
                            "width": width,
                            "height": height,
                            "arc": arc
                        })
    
    # Sprawdzamy odczyty
    missing_info = []
    if not mainplane_info:
        missing_info.append("MainPlane")
    if not sc00_info:
        missing_info.append("SC00")
    if not bends:
        missing_info.append("brak gięć (DC00, DC01, ...)")
    
    if dimension_type is None:
        missing_info.append("WorkpieceDimensions")
    # thickness_val i radius_val są zawsze zainicjalizowane na 0.0, więc nie ma potrzeby sprawdzania
    
    if missing_info:
        print(f"Plik {filename}: Brak odczytu: {', '.join(missing_info)}.")
        return
    
    # Wyliczenia dla MainPlane i SC00
    mp_a = mainplane_info["a"]
    sc_b = sc00_info["b"]
    
    # Przygotowanie wyników
    wynik = []
    wynik.append("=== Odczyt z pliku DLD (metoda bounding box) ===")
    wynik.append(f"WorkpieceDimensions = {dimension_type}")
    wynik.append(f"Grubość             = {thickness_val} mm")
    wynik.append(f"Promień wewn.       = {radius_val} mm")
    wynik.append("-------------------------------------------")
    wynik.append(f"[MainPlane] width={mainplane_info['width']:.6f}  height={mainplane_info['height']:.6f} => a={mp_a:.6f}")
    wynik.append(f"[SC00]      width={sc00_info['width']:.6f} height={sc00_info['height']:.6f} => b={sc_b:.6f}")
    
    # Przetwarzanie gięć
    total_extension = mp_a + sc_b
    total_offset = 0.0
    if bends:
        for idx, bend in enumerate(bends, start=1):
            wynik.append(f"[{bend['name']}] width={bend['width']:.6f} height={bend['height']:.6f} => łuk={bend['arc']:.6f}")
            total_extension += bend['arc']
            # Obliczenie offsetu dla każdego gięcia
            offset = bend['radius'] + bend['thickness']
            total_offset += offset
    else:
        wynik.append("Brak gięć do przetworzenia.")
    
    wynik.append("-------------------------------------------")
    wynik.append(f"Offset (r+g)        = {total_offset:.6f} mm")
    wynik.append("-------------------------------------------")
    
    # Obliczenie a_ext i b_ext
    if dimension_type.lower() == "outside":
        a_ext = mp_a
        b_ext = sc_b
    else:
        a_ext = mp_a + total_offset
        b_ext = sc_b + total_offset
    
    wynik.append(f"a (zewn.) = {a_ext:.6f} mm")
    wynik.append(f"b (zewn.) = {b_ext:.6f} mm")
    wynik.append(f"Rozwinięcie (a + b + łuki) = {total_extension:.6f} mm")
    
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
