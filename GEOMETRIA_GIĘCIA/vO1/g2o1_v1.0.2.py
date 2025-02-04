#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import os
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
      225 st => -135
      270 st => -90
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

    mainplane_value = None       # a (z bounding box) => 'zewn.'
    sc_components = {}           # np. {"SC00": float, "SC01": float, ...} => 'zewn.'
    
    # Informacja o gięciach (DCxx). Przyjmujemy, że jedno DC "wpływa" na a lub b, ...
    bends_info = []              # [{"name":..., "arc":..., "angle":..., "angle_norm":...}, ...]

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
                    value_min = min(width, height)  # bierzemy mniejszy wymiar

                    if comp_name == "MainPlane":
                        mainplane_value = value_min
                    elif re.match(r'^SC\d+', comp_name):
                        sc_components[comp_name] = value_min

        # Deformowalny komponent (DCxx)
        if tag_name.endswith("vdeformablecomponent"):
            wp_name = elem.find("./WorkpieceComponentName")
            if wp_name is not None:
                comp_name = wp_name.get("value", "")
                if re.match(r'^DC\d+', comp_name):
                    # Łuk
                    hulls_elem = elem.find("./VDeformableComponentHulls")
                    arc_val = 0.0
                    if hulls_elem is not None:
                        val_str = hulls_elem.get("value", "")
                        coords = parse_outline_value(val_str)
                        box = bounding_box(coords)
                        w, h = width_height_from_box(*box)
                        arc_val = min(w, h)

                    # Kąt
                    angle_elem = elem.find("./VDeformableComponentAngle")
                    angle_after = 0.0
                    if angle_elem is not None:
                        try:
                            angle_after = float(angle_elem.get("value", "0"))
                        except ValueError:
                            angle_after = 0.0

                    # Ewentualnie w VBendDeformation/AngleAfter
                    deformation_elem = elem.find("./VBendDeformation")
                    if deformation_elem is not None:
                        angle_after_elem = deformation_elem.find("./AngleAfter")
                        if angle_after_elem is not None:
                            try:
                                angle_after = float(angle_after_elem.get("value", "0"))
                            except ValueError:
                                pass

                    angle_norm = normalize_angle(angle_after)

                    bends_info.append({
                        "name": comp_name,
                        "arc": arc_val,
                        "angle_raw": angle_after,
                        "angle_norm": angle_norm
                    })

    # Sprawdzamy brakujące
    missing_info = []
    if mainplane_value is None:
        missing_info.append("MainPlane")
    if not sc_components:
        missing_info.append("SCxx")
    if not bends_info:
        missing_info.append("DCxx")
    if dimension_type is None:
        missing_info.append("WorkpieceDimensions")

    if missing_info:
        print(f"Plik {filename}: Brak odczytu: {', '.join(missing_info)}.")
        return

    # Przygotowanie etykiet a, b, c,...
    sorted_sc_names = sorted(sc_components.keys(), key=lambda x: int(x[2:]))
    letters = list(string.ascii_lowercase)
    letter_index = letters.index('b')  # b => SC00, c => SC01...
    sc_labels = {}
    for sc_name in sorted_sc_names:
        sc_labels[sc_name] = letters[letter_index]
        letter_index += 1

    # Wyliczamy "zewn." i sumę rozwinięcia
    a_zewn = mainplane_value
    sc_zewn = {}
    for sc_name in sorted_sc_names:
        sc_zewn[sc_name] = sc_components[sc_name]

    # Suma rozwinięcia: a + (b + c + ...) + sum(łuków)
    total_extension = a_zewn + sum(sc_zewn.values()) + sum(b["arc"] for b in bends_info)

    # Oblicz offset = (r + g)
    offset_val = radius_val + thickness_val

    # ---
    # WYZNACZANIE (out) i (in) DLA PRZYKŁADOWEGO KĄTA 90°
    # ---
    # Załóżmy uproszczoną logikę:
    #   Jeżeli jest TYLKO JEDEN DC (albo koncentrujesz się na pierwszym DC w pliku),
    #   i jego kąt_norm = +/- 90°, to:
    #     a(out) = a_zewn + offset
    #     a(in)  = a_zewn + arc/2
    #
    # Ale co z b, c, ...? W realnym scenariuszu musisz wiedzieć,
    # które DC dotyczy a, które b, etc. W tym przykładzie
    # zastosujemy taką samą formułę dla "a" i dla każdego SC,
    # o ile dany DC = 90°. (W przykładach – zwykle jest jedna linia gięcia).
    #
    # Gdyby w pliku było kilka gięć 90°, musisz zdecydować,
    # czy sumujesz offsety i połowy łuków, czy tylko pojedyncze.
    #

    # Na potrzeby przykładu: bierzemy tylko DC, który ma kąt_norm w pobliżu 90° (+/- 5°, powiedzmy)
    # i używamy *jednego* DC do korekty (out/in). W praktyce: musisz tu wprowadzić lepsze mapowanie.
    dc_90 = None
    for bend in bends_info:
        if abs(bend["angle_norm"] - 90) < 5:
            dc_90 = bend
            break

    # a(out), a(in)
    if dc_90 is not None:
        arc_90 = dc_90["arc"]
        a_out = a_zewn + offset_val
        a_in = a_zewn + (arc_90 / 2.0)
    else:
        # brak DC z kątem 90 => weźmy domyślnie a_out=a_zewn, a_in=a_zewn
        a_out = a_zewn
        a_in = a_zewn

    # Dla SC (b, c, d...) zrobimy analogiczną rzecz:
    sc_out = {}
    sc_in = {}
    for sc_name in sorted_sc_names:
        val_zewn = sc_zewn[sc_name]
        if dc_90 is not None:
            sc_out[sc_name] = val_zewn + offset_val
            sc_in[sc_name] = val_zewn + (dc_90["arc"] / 2.0)
        else:
            sc_out[sc_name] = val_zewn
            sc_in[sc_name] = val_zewn

    # --- Budowa wyniku ---
    basename = os.path.basename(filename)
    wynik = []
    wynik.append(f"=== Wyniki dla pliku: {basename} ===")
    wynik.append("=== Odczyt z pliku DLD (metoda bounding box) ===")
    wynik.append(f"WorkpieceDimensions = {dimension_type}")
    wynik.append(f"Grubość             = {thickness_val} mm")
    wynik.append(f"Promień wewn.       = {radius_val} mm")
    wynik.append("-------------------------------------------")

    # MainPlane => a
    wynik.append(f"[MainPlane] => a={a_zewn:.6f}")

    # SCxx => b, c, d...
    for sc_name in sorted_sc_names:
        label = sc_labels[sc_name]
        wynik.append(f"[{sc_name}] => {label}={sc_zewn[sc_name]:.6f}")

    # DCxx => łuki
    for bend in bends_info:
        wynik.append(f"[{bend['name']}] => łuk={bend['arc']:.6f}")

    wynik.append("-------------------------------------------")
    wynik.append(f"Offset (r+g)        = {offset_val:.6f} mm")
    wynik.append("-------------------------------------------")

    # (zewn.)
    wynik.append(f"a (zewn.) = {a_zewn:.6f} mm")
    for sc_name in sorted_sc_names:
        label = sc_labels[sc_name]
        wynik.append(f"{label} (zewn.) = {sc_zewn[sc_name]:.6f} mm")

    wynik.append(f"Rozwinięcie (a + b + c + ... + łuki) = {total_extension:.6f} mm")

    wynik.append("")
    wynik.append("-------------------------------------------")

    # (out)
    wynik.append(f"a (out) = {a_out:.3f}")  # np. zaokrąglenie
    for sc_name in sorted_sc_names:
        label = sc_labels[sc_name]
        wynik.append(f"{label} (out) = {sc_out[sc_name]:.3f}")

    wynik.append("")
    wynik.append("-----")
    wynik.append("")

    # (in)
    wynik.append(f"a (in) = {a_in:.3f}")
    for sc_name in sorted_sc_names:
        label = sc_labels[sc_name]
        wynik.append(f"{label} (in) = {sc_in[sc_name]:.3f}")

    wynik.append("")
    wynik.append("-----")
    wynik.append("kąty")
    for bend in bends_info:
        wynik.append(f"{bend['angle_norm']:.0f}")

    wynik_text = "\n".join(wynik)

    # Wyświetlenie
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
    output_dir = os.path.join(folder, "wyniki2")
    os.makedirs(output_dir, exist_ok=True)

    # Znajdź wszystkie pliki .dld w folderze
    pattern = os.path.join(folder, "*.dld")
    files = glob.glob(pattern)

    if not files:
        print(f"Nie znaleziono żadnych plików .dld w folderze: {folder}")
        return

    print(f"Znaleziono {len(files)} plików .dld w folderze: {folder}\n")

    for file in files:
        process_file(file, output_dir)

    print("\nPrzetwarzanie zakończone.")

if __name__ == "__main__":
    main()
