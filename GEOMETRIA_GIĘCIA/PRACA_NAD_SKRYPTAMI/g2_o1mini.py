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
    Pomija słowa 'true'/'false' oraz inne nie-numeryczne tokeny.
    """
    tokens = value_str.split()
    numeric_vals = []
    for t in tokens:
        if t.lower() in ['outline', 'true', 'false', 'line']:
            continue
        try:
            numeric_vals.append(float(t))
        except ValueError:
            pass
    if not numeric_vals:
        return []
    # Nie używamy segment_count, więc pomijamy pierwszy token
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

def process_file(filename, output_dir, namespaces):
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
    segments = []             # Lista na informacje o segmentach
    bends = []                # Lista na informacje o gięciach

    # Przeszukujemy XML
    for elem in root.iter():
        tag = elem.tag
        # Ignorujemy namespace w tagu
        if '}' in tag:
            tag_name = tag.split('}', 1)[1].lower()
        else:
            tag_name = tag.lower()

        # Atrybuty ogólne
        if tag_name == "workpiecedimensions":
            dimension_type = elem.get("value", "")  # "Outside" / "Inside"
        elif tag_name == "workpiecethickness":
            try:
                thickness_val = float(elem.get("value", "0"))
            except ValueError:
                thickness_val = 0.0
        elif tag_name == "preferredinnerradius":
            try:
                radius_val = float(elem.get("value", "0"))
            except ValueError:
                radius_val = 0.0

        # Odczyt Outline/Hull -> bounding box dla StaticComponents
        elif tag_name == "staticcomponent":
            # Przykładowa ścieżka z namespace
            wp_name = elem.find("delem:WorkpieceComponentName", namespaces=namespaces)
            if wp_name is not None:
                comp_name = wp_name.get("value", "")
                
                hull_elem = elem.find("delem:StaticComponentPart/delem:StaticComponentHull", namespaces=namespaces)
                if hull_elem is not None:
                    val_str = hull_elem.get("value", "")
                    coords = parse_outline_value(val_str)
                    box = bounding_box(coords)
                    width, height = width_height_from_box(*box)
                    a = max(width, height)
                    b = min(width, height)
                    
                    segments.append({
                        "name": comp_name,
                        "box": box,
                        "width": width,
                        "height": height,
                        "a": a,
                        "b": b
                    })

        # Deformowalny komponent - Gięcie
        elif tag_name == "vdeformablecomponent":
            wp_name = elem.find("delem:WorkpieceComponentName", namespaces=namespaces)
            if wp_name is not None:
                comp_name = wp_name.get("value", "")
                # Zakładamy, że gięcia mają nazwy zaczynające się od "DC"
                if re.match(r'^DC\d+', comp_name):
                    hulls_elem = elem.find("delem:VDeformableComponentHulls", namespaces=namespaces)
                    if hulls_elem is not None:
                        val_str = hulls_elem.get("value", "")
                        coords = parse_outline_value(val_str)
                        box = bounding_box(coords)
                        width, height = width_height_from_box(*box)
                        arc = min(width, height)
                        
                        # Pobranie wartości kąta
                        angle_elem = elem.find("delem:VDeformableComponentAngle", namespaces=namespaces)
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
    if not segments:
        missing_info.append("brak segmentów (MainPlane, SC00, SC01, ...)")
    if not bends:
        missing_info.append("brak gięć (DC00, DC01, ...)")
    
    if dimension_type is None:
        missing_info.append("WorkpieceDimensions")
    # thickness_val i radius_val są zawsze zainicjalizowane na 0.0, więc nie ma potrzeby sprawdzania

    if missing_info:
        print(f"Plik {filename}: Brak odczytu: {', '.join(missing_info)}.")
        return

    # Przygotowanie wyników
    wynik = []
    wynik.append("=== Odczyt z pliku DLD (metoda bounding box) ===")
    wynik.append(f"WorkpieceDimensions = {dimension_type}")
    wynik.append(f"Grubość             = {thickness_val} mm")
    wynik.append(f"Promień wewn.       = {radius_val} mm")
    wynik.append("-------------------------------------------")
    
    # Informacje o segmentach
    total_a = 0.0
    total_b = 0.0
    for segment in segments:
        name = segment["name"]
        width = segment["width"]
        height = segment["height"]
        a = segment["a"]
        b = segment["b"]
        wynik.append(f"[{name}] width={width:.6f}  height={height:.6f} => a={a:.6f}, b={b:.6f}")
        total_a += a
        total_b += b
    
    # Informacje o gięciach
    total_extension = total_a + total_b
    total_offset = 0.0
    if bends:
        for bend in bends:
            name = bend["name"]
            width = bend["width"]
            height = bend["height"]
            arc = bend["arc"]
            angle = bend["angle"]
            wynik.append(f"[{name}] width={width:.6f} height={height:.6f} => łuk={arc:.6f}, kąt={angle:.2f}°")
            total_extension += arc
            # Obliczenie offsetu dla każdego gięcia
            offset = bend["radius"] + bend["thickness"]
            total_offset += offset
    else:
        wynik.append("Brak gięć do przetworzenia.")
    
    wynik.append("-------------------------------------------")
    wynik.append(f"Offset (r+g)        = {total_offset:.6f} mm")
    wynik.append("-------------------------------------------")
    
    # Obliczenie a_ext i b_ext
    if dimension_type.lower() == "outside":
        a_ext = total_a
        b_ext = total_b
    else:
        a_ext = total_a + total_offset
        b_ext = total_b + total_offset
    
    wynik.append(f"a (zewn.) = {a_ext:.6f} mm")
    wynik.append(f"b (zewn.) = {b_ext:.6f} mm")
    wynik.append(f"Rozwinięcie (sum a + sum b + sum łuków) = {total_extension:.6f} mm")
    
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
    
    # Zdefiniuj przestrzeń nazw
    namespaces = {'delem': 'http://www.delem.com/delem'}
    
    # Znajdź wszystkie pliki .dld w folderze
    pattern = os.path.join(folder, "*.dld")
    files = glob.glob(pattern)
    
    if not files:
        print(f"Nie znaleziono żadnych plików .dld w folderze: {folder}")
        return
    
    print(f"Znaleziono {len(files)} plików .dld w folderze: {folder}\n")
    
    # Przetwarzaj każdy plik
    for file in files:
        process_file(file, output_dir, namespaces)
    
    print("\nPrzetwarzanie zakończone.")

if __name__ == "__main__":
    main()
