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
    Pomija słowa 'true'/'false' i 'Outline'.
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
    thickness_val = 0.0       # grubość
    radius_val = 0.0          # promień wewnętrzny

    mainplane_value = None     # długość (a)
    sc_components = {}         # np. {"SC00": float, "SC01": float, ...}
    bends = []                 # lista info o gięciach (DCxx)

    # --- Parsujemy strukturę XML ---
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

        # Odczyt Outline/Hull -> bounding box
        # dla MainPlane i wszystkich SCxx
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
                    # Według uwagi w przykładach – bierzemy MNIEJSZY wymiar
                    comp_val = min(width, height)

                    if comp_name == "MainPlane":
                        mainplane_value = comp_val
                    else:
                        # Jeśli nazwa to SCxx -> zapisz
                        if re.match(r'^SC\d+', comp_name):
                            sc_components[comp_name] = comp_val

        # Deformowalny komponent - Gięcie (DCxx)
        if tag_name.endswith("vdeformablecomponent"):
            wp_name = elem.find("./WorkpieceComponentName")
            if wp_name is not None:
                comp_name = wp_name.get("value", "")
                # gięcia mają nazwy DCxx
                if re.match(r'^DC\d+', comp_name):
                    hulls_elem = elem.find("./VDeformableComponentHulls")
                    if hulls_elem is not None:
                        val_str = hulls_elem.get("value", "")
                        coords = parse_outline_value(val_str)
                        box = bounding_box(coords)
                        width, height = width_height_from_box(*box)
                        # łuk = min(width, height)
                        arc = min(width, height)

                        angle_elem = elem.find("./VDeformableComponentAngle")
                        try:
                            angle = float(angle_elem.get("value", "0")) if angle_elem is not None else 0.0
                        except ValueError:
                            angle = 0.0

                        bends.append({
                            "name": comp_name,
                            "angle": angle,
                            "thickness": thickness_val,
                            "radius": radius_val,
                            "box": box,
                            "width": width,
                            "height": height,
                            "arc": arc
                        })

    # --- Sprawdzamy odczyty ---
    missing_info = []
    if mainplane_value is None:
        missing_info.append("MainPlane")
    if not sc_components:
        missing_info.append("SCxx (brak statycznych segmentów SC)")
    if not bends:
        missing_info.append("gięć DCxx")

    if dimension_type is None:
        missing_info.append("WorkpieceDimensions")

    if missing_info:
        print(f"Plik {filename}: Brak odczytu: {', '.join(missing_info)}.")
        return

    # --- Przygotowujemy informacje do wyświetlenia ---
    # Sortujemy SCxx wg numeru, aby potem je nazwać b, c, d, ...
    sorted_sc_names = sorted(sc_components.keys(), key=lambda x: int(x[2:]))  # sortowanie po numerze np. SC00, SC01,...
    sc_labels = {}  # np. {"SC00":"b", "SC01":"c", ...}

    # Zaczynamy etykietowanie SC od litery 'b'
    # b, c, d, e, ...
    import string
    letters = list(string.ascii_lowercase)  # ['a','b','c','d',...]
    # 'a' będzie wykorzystane dla MainPlane, więc SC zaczynamy od 'b'
    letter_index = letters.index('b')  # start od 'b'

    for sc_name in sorted_sc_names:
        sc_labels[sc_name] = letters[letter_index]
        letter_index += 1

    # Rozwinięcie = a + sum(SC) + sum(łuki)
    # a → mainplane_value
    # b, c, d... → sc_components
    # łuki → arcs z DCxx

    total_extension = mainplane_value  # od a
    arcs_sum = 0.0
    # sumujemy wszystkie SC
    for sc_name in sorted_sc_names:
        total_extension += sc_components[sc_name]

    # sumujemy wszystkie łuki
    for bend in bends:
        arcs_sum += bend["arc"]
    total_extension += arcs_sum

    # offset (r + g) wielokrotnie czy suma?
    # Obecnie sumujemy (promień + grubość) dla każdego DC
    total_offset = 0.0
    for bend in bends:
        total_offset += (bend["radius"] + bend["thickness"])

    # --- Tworzymy tekst wyjściowy ---
    wynik = []
    basename = os.path.basename(filename)

    wynik.append(f"=== Wyniki dla pliku: {basename} ===")
    wynik.append("=== Odczyt z pliku DLD (metoda bounding box) ===")
    wynik.append(f"WorkpieceDimensions = {dimension_type}")
    wynik.append(f"Grubość             = {thickness_val} mm")
    wynik.append(f"Promień wewn.       = {radius_val} mm")
    wynik.append("-------------------------------------------")

    # MainPlane
    # Żeby pokazać jeszcze width/height, musimy je znaleźć w pliku ponownie
    # ale mamy tylko 'mainplane_value = min(width,height)'.
    # Jeśli chcesz, możesz przechować tam też width,height.
    # Tu pokazujemy symbolicznie:
    wynik.append(f"[MainPlane] => a={mainplane_value:.6f}")

    # SCxx
    for sc_name in sorted_sc_names:
        sc_val = sc_components[sc_name]
        label = sc_labels[sc_name]  # b, c, d...
        wynik.append(f"[{sc_name}] => {label}={sc_val:.6f}")

    # DCxx (łuki)
    for bend in bends:
        wynik.append(f"[{bend['name']}] => łuk={bend['arc']:.6f}")

    wynik.append("-------------------------------------------")
    wynik.append(f"Offset (r+g)        = {total_offset:.6f} mm")
    wynik.append("-------------------------------------------")

    # Wyświetlamy końcowe nazwy a, b, c...
    # W przykładzie: a (zewn.), b (zewn.), c...
    # Tutaj – a = mainplane_value
    # b, c, d, ... z sc_labels
    # W przykładzie pokazywano „a (zewn.) = ...“, analogicznie:
    wynik.append(f"a (zewn.) = {mainplane_value:.6f} mm")
    for sc_name in sorted_sc_names:
        label = sc_labels[sc_name]
        sc_val = sc_components[sc_name]
        wynik.append(f"{label} (zewn.) = {sc_val:.6f} mm")

    # Rozwinięcie
    wynik.append(f"Rozwinięcie (a + b + c + ... + łuki) = {total_extension:.6f} mm")

    # Łączenie wszystkiego w jeden tekst
    wynik_text = "\n".join(wynik)

    # Wypis do konsoli
    print(wynik_text)

    # Zapis do pliku
    base_name = os.path.splitext(basename)[0]
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
