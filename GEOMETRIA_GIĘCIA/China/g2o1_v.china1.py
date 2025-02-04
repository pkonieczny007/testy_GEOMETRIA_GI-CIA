#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import os  # Dodano import modułu os
import re
import glob
import sys
import string

def parse_outline_value(value_str):
    """
    Z pliku Delem (np. '4 0 6.613518 200 6.613518 false ...')
    wyciąga pary (x, y) i zwraca listę krotek [(x1,y1), (x2,y2), ...].
    Pomija słowa 'outline', 'true', 'false'.
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
    # Pierwsza liczba to ilość punktów w Outline
    segment_count = int(numeric_vals[0])
    coords = numeric_vals[1:]
    points = []
    for i in range(0, len(coords), 2):
        if i + 1 < len(coords):
            x = coords[i]
            y = coords[i + 1]
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

def normalize_angle(angle_deg):
    """
    Zamienia kąt > 180 na kąt ujemny w zakresie [-180, 180].
    Przykłady:
      225 st => 225 - 360 = -135
      270 st => 270 - 360 = -90
    """
    if angle_deg > 180:
        return angle_deg - 360
    return angle_deg

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
    thickness_val = 0.0
    radius_val = 0.0

    mainplane_value = None       # a (z bounding box)
    sc_components = {}           # np. {"SC00": float, "SC01": float, ...}
    bends_info = []              # lista słowników z info o DC

    # Dodatkowo chcemy przechowywać kąty z gięć:
    bend_angles = []             # np. [90, -135, itp.]

    # --- Parsujemy strukturę XML ---
    for elem in root.iter():
        tag_name = elem.tag.lower()

        # Atrybuty ogólne
        if tag_name.endswith("workpiecedimensions"):
            dimension_type = elem.get("value", "")
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
                    width, height = width_height_from_box(*box)
                    value_min = min(width, height)

                    if comp_name == "MainPlane":
                        mainplane_value = value_min
                    else:
                        if re.match(r'^SC\d+', comp_name):
                            sc_components[comp_name] = value_min

        # Deformowalny komponent (VDeformableComponent) -> gięcia DCxx
        if tag_name.endswith("vdeformablecomponent"):
            wp_name = elem.find("./WorkpieceComponentName")
            if wp_name is not None:
                comp_name = wp_name.get("value", "")
                if re.match(r'^DC\d+', comp_name):
                    hulls_elem = elem.find("./VDeformableComponentHulls")
                    if hulls_elem is not None:
                        val_str = hulls_elem.get("value", "")
                        coords = parse_outline_value(val_str)
                        box = bounding_box(coords)
                        width, height = width_height_from_box(*box)
                        arc = min(width, height)

                    angle_elem = elem.find("./VDeformableComponentAngle")
                    angle_after = 0.0
                    if angle_elem is not None:
                        try:
                            angle_after = float(angle_elem.get("value", "0"))
                        except ValueError:
                            angle_after = 0.0

                    deformation_elem = elem.find("./VBendDeformation")
                    if deformation_elem is not None:
                        angle_after_elem = deformation_elem.find("./AngleAfter")
                        if angle_after_elem is not None:
                            try:
                                angle_after = float(angle_after_elem.get("value", "0"))
                            except ValueError:
                                pass

                    angle_normalized = normalize_angle(angle_after)

                    bends_info.append({
                        "name": comp_name,
                        "arc": arc,
                        "angle_raw": angle_after,
                        "angle_norm": angle_normalized
                    })

    # --- Sprawdzamy brakujące informacje ---
    missing_info = []
    if mainplane_value is None:
        missing_info.append("MainPlane")
    if not sc_components:
        missing_info.append("SCxx (brak segmentów SC)")
    if not bends_info:
        missing_info.append("DCxx (brak gięć)")

    if dimension_type is None:
        missing_info.append("WorkpieceDimensions")

    if missing_info:
        print(f"Plik {filename}: Brak odczytu: {', '.join(missing_info)}.")
        return

    # --- Przygotowanie do wyświetlenia ---
    sorted_sc_names = sorted(sc_components.keys(), key=lambda x: int(x[2:]))
    letters = list(string.ascii_lowercase)
    letter_index = letters.index('b')
    sc_labels = {}

    for sc_name in sorted_sc_names:
        sc_labels[sc_name] = letters[letter_index]
        letter_index += 1

    total_extension = mainplane_value
    for sc_name in sorted_sc_names:
        total_extension += sc_components[sc_name]
    sum_arcs = sum(b["arc"] for b in bends_info)
    total_extension += sum_arcs

    total_offset = 0.0
    for b in bends_info:
        offset_one_bend = radius_val + thickness_val
        total_offset += offset_one_bend

    # --- Budowa tekstu wyjściowego ---
    basename = os.path.basename(filename)
    wynik_lines = []
    wynik_lines.append(f"=== Wyniki dla pliku: {basename} ===")
    wynik_lines.append("=== Odczyt z pliku DLD (metoda bounding box) ===")
    wynik_lines.append(f"WorkpieceDimensions = {dimension_type}")
    wynik_lines.append(f"Grubość             = {thickness_val} mm")
    wynik_lines.append(f"Promień wewn.       = {radius_val} mm")
    wynik_lines.append("-------------------------------------------")

    wynik_lines.append(f"[MainPlane] => a={mainplane_value:.6f}")
    for sc_name in sorted_sc_names:
        label = sc_labels[sc_name]
        val = sc_components[sc_name]
        wynik_lines.append(f"[{sc_name}] => {label}={val:.6f}")

    for bend in bends_info:
        wynik_lines.append(f"[{bend['name']}] => łuk={bend['arc']:.6f}")

    wynik_lines.append("-------------------------------------------")
    wynik_lines.append(f"Offset (r+g)        = {total_offset:.6f} mm")
    wynik_lines.append("-------------------------------------------")

    wynik_lines.append(f"a (zewn.) = {mainplane_value:.6f} mm")
    for sc_name in sorted_sc_names:
        label = sc_labels[sc_name]
        val = sc_components[sc_name]
        wynik_lines.append(f"{label} (zewn.) = {val:.6f} mm")

    wynik_lines.append(f"Rozwinięcie (a + b + c + ... + łuki) = {total_extension:.6f} mm")

    # Obliczanie wymiarów zewnętrznych (out)
    wynik_lines.append("")
    wynik_lines.append("-------------------------------------------")
    out_values = {}
    a_out = int(round(mainplane_value + 2 * thickness_val))  # a (out) = a (zewn.) + 2 * grubość
    out_values["a"] = a_out

    for sc_name in sorted_sc_names:
        label = sc_labels[sc_name]
        val_zewn = sc_components[sc_name]
        val_out = int(round(val_zewn + 2 * thickness_val))  # b (out) = b (zewn.) + 2 * grubość
        out_values[label] = val_out

    wynik_lines.append(f"a (out) = {out_values['a']}")
    for sc_name in sorted_sc_names:
        label = sc_labels[sc_name]
        wynik_lines.append(f"{label} (out) = {out_values[label]}")

    wynik_lines.append("")
    wynik_lines.append("-----")

    # Obliczanie wymiarów wewnętrznych (in)
    wynik_lines.append("")
    in_values = {}
    a_in = out_values["a"] - 2 * thickness_val  # a (in) = a (out) - 2 * grubość
    in_values["a"] = a_in

    for sc_name in sorted_sc_names:
        label = sc_labels[sc_name]
        val_in = out_values[label] - 2 * thickness_val  # b (in) = b (out) - 2 * grubość
        in_values[label] = val_in

    wynik_lines.append(f"a (in) = {in_values['a']}")
    for sc_name in sorted_sc_names:
        label = sc_labels[sc_name]
        wynik_lines.append(f"{label} (in) = {in_values[label]}")

    wynik_lines.append("")
    wynik_lines.append("-----")

    # Sekcja: kąty
    wynik_lines.append("kąty")
    for bend in bends_info:
        wynik_lines.append(f"{bend['angle_norm']:.0f}")

    # Sklejamy do jednego tekstu
    wynik_text = "\n".join(wynik_lines)

    # Wyświetlenie w konsoli
    print(wynik_text)

    # Zapis do pliku w folderze wyniki_china
    output_dir_china = os.path.join(output_dir, "wyniki_china")
    os.makedirs(output_dir_china, exist_ok=True)  # Tworzymy folder, jeśli nie istnieje

    base_name = os.path.splitext(basename)[0]
    output_filename = os.path.join(output_dir_china, f"wynik_{base_name}.txt")
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(wynik_text)
        print(f"Wyniki zapisano do pliku: {output_filename}")
    except IOError as e:
        print(f"Błąd zapisu pliku {output_filename}: {e}")

def main():
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = os.getcwd()

    if not os.path.isdir(folder):
        print(f"Podany folder nie istnieje: {folder}")
        return

    # Utwórz folder na wyniki, jeśli nie istnieje
    output_dir = os.path.join(folder, "wyniki_china")
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
