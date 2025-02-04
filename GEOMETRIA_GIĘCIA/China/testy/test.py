#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
import xml.etree.ElementTree as ET

def parse_outline_value(value_str):
    """
    Prosta funkcja pomocnicza do parsowania atrybutu 'value' z Outline
    (np. '4 0 6.613518 200 6.613518 false ...').
    Zwraca listę par współrzędnych [(x1,y1), (x2,y2), ...].
    Ignoruje słowa: 'outline', 'true', 'false'.
    """
    tokens = value_str.split()
    numeric_vals = []
    for t in tokens:
        t_low = t.lower()
        if t_low in ['outline', 'true', 'false']:
            continue
        try:
            numeric_vals.append(float(t))
        except ValueError:
            pass

    if not numeric_vals:
        return []

    # Pierwsza liczba zwykle oznacza ilość węzłów w polilinii (np. 4)
    count_points = int(numeric_vals[0])
    coords = numeric_vals[1:]

    points = []
    for i in range(0, len(coords), 2):
        if i+1 < len(coords):
            x = coords[i]
            y = coords[i+1]
            points.append((x, y))
    return points

def process_dld_file(dld_filename, output_folder):
    """Parsuje jeden plik .dld, wyciąga <WorkpieceMap> i zapisuje wyniki w pliku txt."""
    import sys

    base_name = os.path.splitext(os.path.basename(dld_filename))[0]
    output_filename = os.path.join(output_folder, f"test_{base_name}.txt")

    try:
        tree = ET.parse(dld_filename)
        root = tree.getroot()
    except ET.ParseError as e:
        result_text = f"Błąd parsowania XML w pliku {dld_filename}: {e}\n"
        # Zapisz do pliku i wypisz w konsoli
        print(result_text)
        with open(output_filename, "w", encoding="utf-8") as fout:
            fout.write(result_text)
        return

    # Szukamy WorkpieceMap
    workpiece_map = root.find(".//WorkpieceMap")
    if workpiece_map is None:
        result_text = (
            f"Plik: {os.path.basename(dld_filename)}\n"
            "Nie znaleziono węzła <WorkpieceMap>.\n"
        )
        print(result_text)
        with open(output_filename, "w", encoding="utf-8") as fout:
            fout.write(result_text)
        return

    lines = []
    lines.append(f"=== Dane z <WorkpieceMap> dla pliku: {os.path.basename(dld_filename)} ===\n")

    # Przejrzyjmy wszystkie pod-węzły w <WorkpieceMap>
    for child in workpiece_map:
        tag_name = child.tag
        # Usuwamy namespace, np. '{...}StaticComponent' => 'StaticComponent'
        if '}' in tag_name:
            tag_name = tag_name.split('}',1)[1]

        if tag_name == "StaticComponent":
            # Nazwa SC
            sc_name_elem = child.find("./WorkpieceComponentName")
            sc_name = sc_name_elem.get("value","") if sc_name_elem is not None else "(brak nazwy)"

            lines.append(f"--- StaticComponent: {sc_name} ---")

            # Hull:
            hull_elem = child.find("./StaticComponentPart/StaticComponentHull")
            if hull_elem is not None:
                hull_val = hull_elem.get("value","")
                hull_pts = parse_outline_value(hull_val)
                lines.append(f"  Hull Outline (punktów={len(hull_pts)}): {hull_pts}")

            # DeformableCompShortening (może być wiele)
            short_list = child.findall("./DeformableCompShortening")
            for s in short_list:
                dc_name_elem = s.find("./DeformableComponentName")
                dc_name = dc_name_elem.get("value","") if dc_name_elem is not None else "(brak DC)"
                short_contour_elem = s.find("./ShorteningContour")
                short_contour_val = short_contour_elem.get("value","") if short_contour_elem is not None else ""
                sc_pts = parse_outline_value(short_contour_val)

                lines.append(f"  DeformableCompShortening => DC: {dc_name}")
                lines.append(f"    ShorteningContour (pkt={len(sc_pts)}): {sc_pts}")

        elif tag_name == "VDeformableComponent":
            # Nazwa DC
            dc_name_elem = child.find("./WorkpieceComponentName")
            dc_name = dc_name_elem.get("value","") if dc_name_elem is not None else "(brak nazwy DC)"

            lines.append(f"--- VDeformableComponent: {dc_name} ---")

            # Kąt gięcia
            angle_elem = child.find("./VDeformableComponentAngle")
            angle_val = angle_elem.get("value","") if angle_elem is not None else "(brak)"

            lines.append(f"  Kąt (Angle) = {angle_val} stopni")

            # PreferredInnerRadius
            r_elem = child.find("./PreferredInnerRadius")
            r_val = r_elem.get("value","") if r_elem is not None else "(brak)"

            lines.append(f"  Promień wewn. (PreferredInnerRadius) = {r_val} mm")

            # VDeformableComponentHulls (outline łuku)
            hulls_elem = child.find("./VDeformableComponentHulls")
            if hulls_elem is not None:
                hulls_val = hulls_elem.get("value","")
                hulls_pts = parse_outline_value(hulls_val)
                lines.append(f"  VDeformableComponentHulls (pkt={len(hulls_pts)}): {hulls_pts}")

            # LeftStaticComponent
            left_comp = child.find("./LeftStaticComponent/StaticComponentName")
            if left_comp is not None:
                lines.append(f"  LeftStaticComponent => {left_comp.get('value','')}")
            # RightStaticComponent
            right_comp = child.find("./RightStaticComponent/StaticComponentName")
            if right_comp is not None:
                lines.append(f"  RightStaticComponent => {right_comp.get('value','')}")

            # VBendDeformation => kąt po gięciu, allowance, itp.
            deformation_elem = child.find("./VBendDeformation")
            if deformation_elem is not None:
                angle_after_elem = deformation_elem.find("./AngleAfter")
                angle_after = angle_after_elem.get("value","") if angle_after_elem is not None else ""
                angle_before_elem = deformation_elem.find("./AngleBefore")
                angle_before = angle_before_elem.get("value","") if angle_before_elem is not None else ""
                bend_allowance_elem = deformation_elem.find("./BendAllowance")
                bend_allowance = bend_allowance_elem.get("value","") if bend_allowance_elem is not None else ""

                lines.append(f"  VBendDeformation -> AngleAfter={angle_after}, AngleBefore={angle_before}, BendAllowance={bend_allowance}")

        else:
            # Inne ewentualne węzły w <WorkpieceMap>
            lines.append(f"[Info] Inny węzeł w <WorkpieceMap>: {tag_name}")

    lines.append("\n=== Koniec wyciągania danych z <WorkpieceMap> ===\n")

    # Tworzymy finalny tekst
    result_text = "\n".join(lines)

    # 1) Wypis w konsoli
    print(result_text)

    # 2) Zapis do pliku
    try:
        with open(output_filename, "w", encoding="utf-8") as fout:
            fout.write(result_text)
        print(f"(Wyniki zapisane w pliku: {output_filename})\n")
    except IOError as e:
        print(f"Błąd zapisu do {output_filename}: {e}")

def main():
    # 1. Bieżący katalog:
    folder = os.getcwd()
    print(f"Przeglądam pliki *.dld w folderze: {folder}\n")

    # 2. Znajdź wszystkie pliki z rozszerzeniem .dld
    pattern = os.path.join(folder, "*.dld")
    dld_files = glob.glob(pattern)

    if not dld_files:
        print("Nie znaleziono żadnych plików .dld w bieżącym folderze.")
        return

    # 3. Tworzymy folder "test" (jeśli nie istnieje)
    output_folder = os.path.join(folder, "test")
    os.makedirs(output_folder, exist_ok=True)

    # 4. Przetwarzamy każdy znaleziony plik .dld
    for f in dld_files:
        process_dld_file(f, output_folder)

    print("Zakończono przetwarzanie wszystkich plików .dld.\n")

if __name__ == "__main__":
    main()
