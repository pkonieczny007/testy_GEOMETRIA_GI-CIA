# -*- coding: utf-8 -*-
"""
test_odcinki_v2.00o1DOM.py

Główne zmiany względem poprzedniej wersji:
- Nowa logika obliczania wymiarów zewn. (Outside) i wewn. (Inside) dla 'odcinek nr 2'.
- Dodana kolumna "Typ wymiarow" w pliku podsumowującym.
- Zmiana nazw plików wynikowych na *_o1.xlsx zamiast v3.xlsx.
"""

import os
import glob
import math
import xml.etree.ElementTree as ET
import pandas as pd

def parse_outline(outline_str):
    """
    Parsuje ciąg znaków z atrybutu 'value' elementu Outline (lub ShorteningContour).
    Obsługuje dwa formaty główne:
      - standardowy: "4 x1 y1 x2 y2 bool x1 y1 x2 y2 bool ..."
      - z dopiskiem "Outline": "1 Outline 4 x1 y1 x2 y2 bool ..."
    Zamieniamy przecinki na kropki, by unikać problemów w float().

    Zwraca listę krotek: (x1, y1, x2, y2, is_arc, chord_length).
    """
    outline_str = outline_str.replace(",", ".")  # na wypadek przecinków
    tokens = outline_str.split()
    if not tokens:
        return []

    # Sprawdź, czy mamy "Outline" w drugim tokenie
    if len(tokens) > 2 and tokens[1].lower() == "outline":
        # tokens[0] = ile Outline'ów, tokens[2] = liczba segmentów
        try:
            n_segments = int(tokens[2])
        except ValueError:
            return []
        start_index = 3
    else:
        # Pierwszy token to liczba segmentów
        try:
            n_segments = int(tokens[0])
        except ValueError:
            return []
        start_index = 1

    segments = []
    for i in range(n_segments):
        idx = start_index + i*5
        chunk = tokens[idx:idx+5]
        if len(chunk) < 5:
            continue
        try:
            x1 = float(chunk[0])
            y1 = float(chunk[1])
            x2 = float(chunk[2])
            y2 = float(chunk[3])
            is_arc = (chunk[4].lower() == "true")
        except ValueError:
            continue
        chord_length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        segments.append((x1, y1, x2, y2, is_arc, chord_length))

    return segments

def process_file(filepath):
    """
    Zwraca wiersze szczegółowe (wyniki_odcinki_o1.xlsx).
    Format każdego wiersza: 
      [filename, componentName, sourceOutline, odcinekNr,
       x1, y1, x2, y2, isArc, chordLength, arcLength, skrajny?]
    """
    results = []
    filename = os.path.basename(filepath)

    # Wczytanie XML
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Błąd parsowania pliku {filepath}: {e}")
        return results

    # --- StaticComponent ---
    for static_comp in root.findall(".//StaticComponent"):
        comp_elem = static_comp.find("WorkpieceComponentName")
        comp_name = comp_elem.attrib.get("value", "") if comp_elem is not None else ""

        # 1) StaticComponentHull
        hull_elem = static_comp.find("StaticComponentPart/StaticComponentHull")
        if hull_elem is not None:
            outline_str = hull_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            nseg = len(segments)
            for i, seg in enumerate(segments):
                (x1, y1, x2, y2, is_arc, chord_len) = seg
                arc_len = chord_len  # w uproszczeniu
                skrajny = (i==0 or i==nseg-1)
                results.append([
                    filename, comp_name, "StaticComponentHull", i+1,
                    x1, y1, x2, y2, is_arc, chord_len, arc_len, skrajny
                ])

        # 2) ShorteningContour
        def_comp = static_comp.find("DeformableCompShortening")
        if def_comp is not None:
            dc_elem = def_comp.find("DeformableComponentName")
            dc_name = dc_elem.attrib.get("value", "") if dc_elem is not None else ""
            contour_elem = def_comp.find("ShorteningContour")
            if contour_elem is not None:
                outline_str = contour_elem.attrib.get("value", "")
                segments = parse_outline(outline_str)
                nseg = len(segments)
                for i, seg in enumerate(segments):
                    (x1, y1, x2, y2, is_arc, chord_len) = seg
                    arc_len = chord_len
                    skrajny = (i==0 or i==nseg-1)
                    results.append([
                        filename, dc_name, "ShorteningContour", i+1,
                        x1, y1, x2, y2, is_arc, chord_len, arc_len, skrajny
                    ])

    # --- VDeformableComponent ---
    for vdef in root.findall(".//VDeformableComponent"):
        comp_elem = vdef.find("WorkpieceComponentName")
        comp_name = comp_elem.attrib.get("value", "") if comp_elem is not None else ""

        # (A) BendLine
        bend_line_elem = vdef.find("VDeformableComponentBendLine")
        if bend_line_elem is not None:
            outline_str = bend_line_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            nseg = len(segments)
            for i, seg in enumerate(segments):
                (x1, y1, x2, y2, is_arc, chord_len) = seg
                arc_len = chord_len
                skrajny = (i==0 or i==nseg-1)
                results.append([
                    filename, comp_name, "VDeformableComponentBendLine", i+1,
                    x1, y1, x2, y2, is_arc, chord_len, arc_len, skrajny
                ])

        # (B) VDeformableComponentHulls
        hulls_elem = vdef.find("VDeformableComponentHulls")
        if hulls_elem is not None:
            outline_str = hulls_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            nseg = len(segments)
            # Jeżeli comp_name zaczyna się na "DC", to z definicji do arcLength wpisujemy x2 z pierwszego segmentu
            arc_val = None
            if comp_name.startswith("DC") and nseg>0:
                arc_val = segments[0][2]  # x2
            for i, seg in enumerate(segments):
                (x1, y1, x2, y2, is_arc, chord_len) = seg
                if arc_val is not None:
                    arc_len = arc_val
                else:
                    arc_len = chord_len
                skrajny = (i==0 or i==nseg-1)
                results.append([
                    filename, comp_name, "VDeformableComponentHulls", i+1,
                    x1, y1, x2, y2, is_arc, chord_len, arc_len, skrajny
                ])

    return results


def compute_dimensions_for_file(filename, rows, dimension_mode):
    """
    Na podstawie wierszy 'rows' (czyli rekordów z wyniki_odcinki_o1),
    oblicza wymiar(y) na odcinku nr 2 wg Twojej reguły:
    
    - Gdy dimension_mode = 'Outside':
        wymiar zewnętrzny = (StaticComponentHull (odc2)) + (ShorteningContour (odc2))
        dla każdej pary (SC, DC).
      Jeżeli masz kilka SC i kilka DC, możesz uzyskać kilka wyników (np. 70, 60, 20).
    
    - Gdy dimension_mode = 'Inside':
        analogicznie, ale interpretujemy to jako wymiar wewnętrzny.
        Możesz tu dostosować, czy sumujesz SC + DC tak samo, czy inaczej.

    Zwraca listę floatów z obliczonymi wymiarami.
    """

    # 1) Zbierz wszystkie SC: (komponent statyczny, nr=2, source=StaticComponentHull)
    #    klucz = nazwa komponentu, wartość = długość łuku (arcLength) z wiersza
    #    (lub chordLength, zależnie czego chcesz używać)
    sc_dict = {}
    for row in rows:
        # row = [filename, comp, sourceOutline, odcNr, ..., dlugosc_luku (idx=10), skrajny(11)]
        fname = row[0]
        comp = row[1]
        source = row[2]
        odc = row[3]
        arc_len = row[10]
        if fname == filename and source == "StaticComponentHull" and odc == 2:
            sc_dict[comp] = arc_len

    # 2) Zbierz wszystkie DC: (komponent DCxx, nr=2, source=ShorteningContour)
    dc_dict = {}
    for row in rows:
        fname = row[0]
        comp = row[1]
        source = row[2]
        odc = row[3]
        arc_len = row[10]
        # Rozpoznajmy, czy to DC - np. "DC00", "DC01"
        if fname == filename and source == "ShorteningContour" and odc == 2 and comp.startswith("DC"):
            dc_dict[comp] = arc_len

    # 3) Teraz parujemy wartości: do każdego SC dodajemy DC (lub odwrotnie)
    #    Jeżeli jest wiele DC i wiele SC, można zrobić pełną kombinację (albo
    #    łączyć je parami wg Twoich zasad). W przykładzie 60x30 miałeś "MainPlane" i "SC00" jako SC
    #    oraz "DC00" jako DC – to daje 2 pary.
    dimensions = []
    for sc_name, sc_val in sc_dict.items():
        # Weźmy wszystkie DC i sumujmy:
        for dc_name, dc_val in dc_dict.items():
            dim = sc_val + dc_val
            dimensions.append(dim)

    # 4) Jeżeli dimension_mode = 'Inside', logika niby taka sama
    #    (w razie potrzeby modyfikuj sumowanie).
    #    Tutaj założymy, że w inside postępujemy identycznie,
    #    bo tak zapowiada Twoja uwaga: "dla inside mamy ten sam mechanizm".
    #    W razie odmiennych reguł - wstaw warunek if dimension_mode=="Inside": ...
    #    i zmień to co potrzeba.

    # Sortujemy, zaokrąglamy do 3 miejsc
    dimensions_rounded = [round(d, 4) for d in sorted(dimensions)]
    return dimensions_rounded


def create_summary_row(filename, root, all_rows):
    """
    Tworzy słownik z informacjami do pliku podsumowującego wyniki_zw_o1.xlsx
    """
    summary = {
        "Nazwa pliku": filename,
        "Typ wymiarow": "",              # <WorkpieceDimensions value="Outside" / "Inside">
        "Wymiary_obliczone": "",        # nasz finalny string z listą wymiarów
        "PozostaleDane1": "",           # ewentualne promienie, długość złamu itd. - wedle potrzeb
        "PozostaleDane2": "",
    }

    # Wczytujemy <WorkpieceDimensions>
    dim_elem = root.find(".//Workpiece/WorkpieceDimensions")
    dimension_mode = ""
    if dim_elem is not None:
        dimension_mode = dim_elem.attrib.get("value", "")
    summary["Typ wymiarow"] = dimension_mode

    # Obliczamy wymiary:
    dims = compute_dimensions_for_file(filename, all_rows, dimension_mode)
    if dims:
        # np. "60, 30"
        summary["Wymiary_obliczone"] = ", ".join(str(d) for d in dims)
    else:
        summary["Wymiary_obliczone"] = ""

    # Tu ewentualnie możesz dodać promienie wewnętrzne, blankLength, itp.
    # ...
    # Np. ActualInnerRadius:
    radii_vals = []
    for vdef in root.findall(".//VDeformableComponent"):
        for rad in vdef.findall("ActualInnerRadius"):
            val = rad.attrib.get("value", "").replace(",", ".")
            if val:
                try:
                    radii_vals.append(float(val))
                except:
                    pass
    if radii_vals:
        summary["PozostaleDane1"] = "Promienie: " + ", ".join(str(round(r,2)) for r in radii_vals)

    # Np. BlankLength:
    blank_elem = root.find(".//BendSequence/BlankLength")
    if blank_elem is not None:
        val = blank_elem.attrib.get("value", "").replace(",", ".")
        summary["PozostaleDane2"] = f"BlankLength={val}"

    return summary


def main():
    dld_files = glob.glob("*.dld")
    if not dld_files:
        print("Brak plików .dld w folderze.")
        return

    all_details = []
    all_summaries = []

    for filepath in dld_files:
        # 1) Szczegółowe wiersze (wyniki_odcinki_o1.xlsx)
        detail_rows = process_file(filepath)
        all_details.extend(detail_rows)

    # Mamy już "all_details" z wszystkich plików.
    # Ale do utworzenia podsumowania potrzebujemy ponownie wczytać każdy plik,
    # bo chcemy w nim sprawdzić <WorkpieceDimensions> i tym podobne.
    # Ewentualnie moglibyśmy parse w main() raz, ale tu jest to proste.
    for filepath in dld_files:
        filename = os.path.basename(filepath)
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
        except ET.ParseError:
            continue

        # Tworzymy wiersz podsumowania
        summary_row = create_summary_row(filename, root, all_details)
        all_summaries.append(summary_row)

    # Zapis szczegółów do wyniki_odcinki_o1.xlsx
    cols_details = [
        "Nazwa pliku", "Komponent", "Źródło outline", "Odcinek nr",
        "X1", "Y1", "X2", "Y2", "Łuk?", "Długość cięciwy", "Długość łuku", "Skrajny"
    ]
    df_details = pd.DataFrame(all_details, columns=cols_details)
    df_details.to_excel("wyniki_odcinki_o1.xlsx", index=False)
    print("Zapisano plik 'wyniki_odcinki_o1.xlsx' z danymi szczegółowymi.")

    # Zapis podsumowania do wyniki_zw_o1.xlsx
    # Kolumny mogą być dowolne – tu pokazujemy przykładowe
    cols_summary = [
        "Nazwa pliku",
        "Typ wymiarow",       # Outside / Inside
        "Wymiary_obliczone",  # np. "60,30"
        "PozostaleDane1",     # np. promienie
        "PozostaleDane2",     # np. BlankLength
    ]
    df_summ = pd.DataFrame(all_summaries, columns=cols_summary)
    df_summ.to_excel("wyniki_zw_o1.xlsx", index=False)
    print("Zapisano plik 'wyniki_zw_o1.xlsx' z podsumowaniem.")


if __name__ == "__main__":
    main()
