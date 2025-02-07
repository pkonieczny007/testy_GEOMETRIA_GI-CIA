# -*- coding: utf-8 -*-
"""
test_odcinki_v.2.00o1DOM.py

Przykładowy skrypt z poprawkami:
- Naprawione wyszukiwanie "MainPlane" (zastąpiono XPath iteracją).
- Dostosowana funkcja parse_outline do sytuacji, gdy mamy token "Line".
- Dodane zabezpieczenia przed błędami parsowania segmentów.
"""

import os
import glob
import math
import xml.etree.ElementTree as ET
import pandas as pd

def parse_outline(outline_str):
    """
    Parsuje ciąg znaków z atrybutu 'value' elementu Outline lub Line.

    Obsługuje kilka formatów:
      1. Format standardowy: 
         np. "4 50 295.44915 0 295.44915 false ..." 
         (gdzie pierwszy token to liczba segmentów)
      2. Format używany przez VDeformableComponentHulls:
         np. "1 Outline 4 0 0 5.927563 0 false ..."
         (gdzie tokeny[0] = liczba outline’ów, tokeny[1] = "Outline", tokeny[2] = liczba segmentów)
      3. Format w rodzaju "Line ..." (który może się pojawić)
         np. "1 Line 2.997455 0 2.997455 200 false"
         lub czasem samo "Line 2.997455 0 2.997455 200" (bez boolean).

    Zwraca listę krotek: (x1, y1, x2, y2, is_arc, chord_length).
    W wypadku problemów z parsowaniem segmentu – pomija go.
    """
    # Rozbijamy na tokeny, zamieniamy ewentualne przecinki na kropki
    outline_str = outline_str.replace(",", ".")
    tokens = outline_str.split()
    if not tokens:
        return []

    # Próba rozpoznania wariantów
    # ---------------------------------------------------
    # (A) Czy format "1 Outline 4 ..." lub "1 Line 4 ..."?
    #     tokens[0] => liczba outlines, tokens[1] => "Outline"/"Line", tokens[2] => liczba segmentów.
    # (B) Czy format "4 50 295.44915 0 ..." (pierwszy token to liczba segmentów)?
    # (C) Jeśli coś jeszcze (np. "Line 2.997455 0 2.997455 200"), spróbujemy heurystyk.
    # ---------------------------------------------------
    idx_start_segments = 0
    n_segments = 0

    # Próbujemy parse A:
    # tokens[0] - próba interpretacji jako int (liczba outlines)
    # tokens[1] - "Outline" lub "Line"
    # tokens[2] - liczba segmentów
    if len(tokens) >= 3 and tokens[1].lower() in ("outline", "line"):
        try:
            _dummy_n = int(tokens[0])   # liczba outlines, nie zawsze używana
            n_segments = int(tokens[2]) # rzeczywista liczba segmentów
            idx_start_segments = 3
        except ValueError:
            pass

    # Jeśli n_segments == 0, to sprawdź format B:
    if n_segments == 0:
        # spróbujmy z tokens[0] jako liczba segmentów
        try:
            n_segments = int(tokens[0])
            idx_start_segments = 1
        except ValueError:
            pass

    # Jeśli dalej n_segments == 0 i widzimy np. "Line ..." – heurystyka:
    # np. "Line 2.997455 0 2.997455 200"
    # Załóżmy wtedy, że n_segments=1 i reszta to parametry:
    if n_segments == 0 and tokens[0].lower() == "line":
        n_segments = 1
        idx_start_segments = 1

    segments = []
    if n_segments < 1:
        # Nie udało się zinterpretować liczby segmentów
        return segments

    # Parsujemy po 5 wartości na segment:
    # (x1, y1, x2, y2, is_arc)
    # ale uwaga – bywa, że "is_arc" w ogóle nie występuje (np. "Line x1 y1 x2 y2" bez boolean)
    # Więc staramy się poradzić z tym elastycznie
    # Normalnie: co segment = 5 tokenów
    # ale może być 4 tokeny (bez booleana)
    # lub może być więcej.

    tokens_for_segment = 5  # docelowo
    pointer = idx_start_segments

    for seg_index in range(n_segments):
        # Wycinamy fragment z tokens od pointer do pointer+5 (lub pointer+4)
        seg_slice = tokens[pointer : pointer + tokens_for_segment]
        if len(seg_slice) < 4:
            # zbyt mało danych nawet na x1,y1,x2,y2
            break

        try:
            x1 = float(seg_slice[0])
            y1 = float(seg_slice[1])
            x2 = float(seg_slice[2])
            y2 = float(seg_slice[3])
        except ValueError:
            # nie da się sparsować tych 4 liczb
            break

        # Czy mamy is_arc?
        if len(seg_slice) >= 5:
            is_arc_str = seg_slice[4].lower()
            is_arc = (is_arc_str == "true")
        else:
            is_arc = False  # domyślnie

        chord_length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        segments.append((x1, y1, x2, y2, is_arc, chord_length))

        pointer += tokens_for_segment  # przesuwamy się do następnego segmentu

    return segments


def process_file(filepath):
    """
    Przetwarza jeden plik XML (.dld) i zwraca listę wierszy z danymi
    do tabeli 'wyniki_odcinki'.

    Każdy wiersz zawiera:
      [Nazwa pliku, Komponent, Źródło outline, Odcinek nr, X1, Y1, X2, Y2,
       Łuk?, Długość cięciwy, Długość łuku, Czy odcinek skrajny]
    """
    results = []
    filename = os.path.basename(filepath)
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Błąd parsowania pliku {filepath}: {e}")
        return results

    # --- Przetwarzanie elementów StaticComponent ---
    for static_comp in root.findall(".//StaticComponent"):
        comp_elem = static_comp.find("WorkpieceComponentName")
        comp_name = comp_elem.attrib.get("value", "") if comp_elem is not None else ""

        # 1. StaticComponentHull
        hull_elem = static_comp.find("StaticComponentPart/StaticComponentHull")
        if hull_elem is not None:
            outline_str = hull_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            n_segments = len(segments)
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                arc_length = chord_length  # dla statycznych elementów przyjmujemy cięciwę
                # Sprawdzamy skrajność
                is_end = (i == 0) or (i == n_segments - 1)
                is_end_str = "PRAWDA" if is_end else "FAŁSZ"

                results.append([
                    filename, comp_name, "StaticComponentHull",
                    i+1, x1, y1, x2, y2,
                    is_arc, chord_length, arc_length,
                    is_end_str
                ])

        # 2. ShorteningContour (z DeformableCompShortening)
        def_comp = static_comp.find("DeformableCompShortening")
        if def_comp is not None:
            dc_elem = def_comp.find("DeformableComponentName")
            comp_dc = dc_elem.attrib.get("value", "") if dc_elem is not None else ""
            contour_elem = def_comp.find("ShorteningContour")
            if contour_elem is not None:
                outline_str = contour_elem.attrib.get("value", "")
                segments = parse_outline(outline_str)
                n_segments = len(segments)
                for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                    arc_length = chord_length
                    is_end = (i == 0) or (i == n_segments - 1)
                    is_end_str = "PRAWDA" if is_end else "FAŁSZ"

                    results.append([
                        filename, comp_dc, "ShorteningContour",
                        i+1, x1, y1, x2, y2,
                        is_arc, chord_length, arc_length,
                        is_end_str
                    ])

    # --- Przetwarzanie elementów VDeformableComponent ---
    for vdeform in root.findall(".//VDeformableComponent"):
        comp_elem = vdeform.find("WorkpieceComponentName")
        comp_name = comp_elem.attrib.get("value", "") if comp_elem is not None else ""

        # (A) VDeformableComponentBendLine
        bend_line_elem = vdeform.find("VDeformableComponentBendLine")
        if bend_line_elem is not None:
            outline_str = bend_line_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            n_segments = len(segments)
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                # Dla BendLine zostawiamy arc_length równy cięciwie
                arc_length = chord_length
                is_end = (i == 0) or (i == n_segments - 1)
                is_end_str = "PRAWDA" if is_end else "FAŁSZ"

                results.append([
                    filename, comp_name, "VDeformableComponentBendLine",
                    i+1, x1, y1, x2, y2,
                    is_arc, chord_length, arc_length,
                    is_end_str
                ])

        # (B) VDeformableComponentHulls
        hulls_elem = vdeform.find("VDeformableComponentHulls")
        if hulls_elem is not None:
            outline_str = hulls_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            # Dla komponentów DC (DC00, DC01, DC02) chcemy pobrać wartość łuku
            # z pierwszego segmentu (x2) i stosować do wszystkich segmentów
            arc_val = None
            if comp_name.startswith("DC") and len(segments) > 0:
                x2_first = segments[0][2]  # X2 z pierwszego segmentu
                arc_val = x2_first

            n_segments = len(segments)
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                if comp_name.startswith("DC") and arc_val is not None:
                    arc_length = arc_val
                else:
                    arc_length = chord_length

                is_end = (i == 0) or (i == n_segments - 1)
                is_end_str = "PRAWDA" if is_end else "FAŁSZ"

                results.append([
                    filename, comp_name, "VDeformableComponentHulls",
                    i+1, x1, y1, x2, y2,
                    is_arc, chord_length, arc_length,
                    is_end_str
                ])

    return results


def parse_dimensions_from_name(workpiece_name):
    """
    Przykładowa funkcja, która z napisu w stylu '70x60x20x2' zwraca:
      - lista wymiarów (np. [70, 60, 20])
      - grubość (np. 2)
    Zakłada, że ostatnia liczba to zawsze grubość.
    """
    parts = workpiece_name.split('x')
    if len(parts) < 2:
        return [], 0
    try:
        dims = list(map(float, parts[:-1]))  # wszystko poza ostatnim to wymiary
        thickness = float(parts[-1])         # ostatni to grubość
    except ValueError:
        return [], 0
    return dims, thickness


def compute_inner_dims(outer_dims, thickness):
    """
    Uproszczona logika:
      - Wymiar na skraju: -1 × grubość
      - Wymiary w środku: -2 × grubość
    """
    n = len(outer_dims)
    if n == 0:
        return []
    inner = []
    for i in range(n):
        if i == 0 or i == n-1:
            val = outer_dims[i] - thickness
        else:
            val = outer_dims[i] - 2*thickness
        if val < 0:
            val = 0
        inner.append(val)
    return inner


def compute_outer_dims(inner_dims, thickness):
    """
    Odwrotność compute_inner_dims.
    """
    n = len(inner_dims)
    if n == 0:
        return []
    outer = []
    for i in range(n):
        if i == 0 or i == n-1:
            val = inner_dims[i] + thickness
        else:
            val = inner_dims[i] + 2*thickness
        outer.append(val)
    return outer


def find_static_component_by_name(root, name_value):
    """
    Zastępuje XPath typu: .//StaticComponent[WorkpieceComponentName[@value="MainPlane"]]
    bo w niektórych wersjach ElementTree powoduje błąd SyntaxError: invalid predicate.

    Zwraca pierwszy znaleziony element <StaticComponent> o podanej nazwie
    (WorkpieceComponentName.value == name_value).
    """
    for sc in root.findall(".//StaticComponent"):
        wcn = sc.find("WorkpieceComponentName")
        if wcn is not None and wcn.attrib.get("value") == name_value:
            return sc
    return None


def create_simplified_summary(root, filename):
    """
    Zwraca słownik z polami potrzebnymi do pliku wyniki_zw:
      {
        'nazwa_pliku': ...,
        'liczba_odcinkow': ...,
        'wymiary_zewnetrzne': ...,
        'wymiary_wewnetrzne': ...,
        'promien_wewnetrzny': ...,
        'dlugosc_zlamu': ...,
        'rozwiniecie_obliczeniowe': ...,
        'rozwiniecie_z_pliku': ...
      }
    """
    result = {
        'nazwa_pliku': filename,
        'liczba_odcinkow': 0,
        'wymiary_zewnetrzne': '',
        'wymiary_wewnetrzne': '',
        'promien_wewnetrzny': '',
        'dlugosc_zlamu': 0,
        'rozwiniecie_obliczeniowe': 0,
        'rozwiniecie_z_pliku': 0
    }

    # Parsujemy <Workpiece>
    workpiece = root.find(".//Workpiece")
    if workpiece is None:
        return result

    # Odczyt nazwy i grubości
    wpn_elem = workpiece.find("WorkpieceName")
    thickness_elem = workpiece.find("WorkpieceThickness")
    dims_elem = workpiece.find("WorkpieceDimensions")
    if not wpn_elem or not thickness_elem or not dims_elem:
        return result

    workpiece_name = wpn_elem.attrib.get("value", "")
    thickness_str = thickness_elem.attrib.get("value", "0")
    dimension_mode = dims_elem.attrib.get("value", "Outside")  # "Outside" / "Inside"

    try:
        thickness = float(thickness_str)
    except ValueError:
        thickness = 0.0

    dims, t = parse_dimensions_from_name(workpiece_name)

    # 3) Obliczenie wymiarów wewn. i zewn.
    if dimension_mode == "Outside":
        outer_dims = dims
        inner_dims = compute_inner_dims(outer_dims, thickness)
    else:
        inner_dims = dims
        outer_dims = compute_outer_dims(inner_dims, thickness)

    result['wymiary_zewnetrzne'] = ",".join([str(round(d, 2)) for d in outer_dims])
    result['wymiary_wewnetrzne'] = ",".join([str(round(d, 2)) for d in inner_dims])

    # 4) Zbieramy promienie wewnętrzne z <ActualInnerRadius>
    actual_radii = root.findall(".//VDeformableComponent/ActualInnerRadius")
    promienie = []
    for ar in actual_radii:
        val_str = ar.attrib.get("value", "0")
        try:
            val = float(val_str)
            promienie.append(val)
        except ValueError:
            pass
    result['promien_wewnetrzny'] = ",".join([str(round(p, 3)) for p in promienie])

    # 5) Liczba odcinków = liczba <VDeformableComponent>
    vdef_components = root.findall(".//VDeformableComponent")
    result['liczba_odcinkow'] = len(vdef_components)

    # 6) Długość złamu – np. max cięciwy w MainPlane
    mainplane = find_static_component_by_name(root, "MainPlane")
    if mainplane is not None:
        hull_elem = mainplane.find("StaticComponentPart/StaticComponentHull")
        if hull_elem is not None:
            segments = parse_outline(hull_elem.attrib.get("value", ""))
            max_chord = 0
            for seg in segments:
                chord_len = seg[5]
                if chord_len > max_chord:
                    max_chord = chord_len
            result['dlugosc_zlamu'] = round(max_chord, 2)

    # 7) Rozwinięcie z pliku – <BlankLength>
    bend_sequence = root.find(".//BendSequence")
    if bend_sequence is not None:
        blank_length_elem = bend_sequence.find("BlankLength")
        if blank_length_elem is not None:
            val_str = blank_length_elem.attrib.get("value", "0")
            try:
                result['rozwiniecie_z_pliku'] = round(float(val_str), 5)
            except ValueError:
                pass

    # 8) Rozwinięcie obliczeniowe (UPROSZCZONE).
    #    Załóżmy: sumujemy "SC01" (StaticComponentHull) + "DC01" (VDeformableComponentHulls)
    #    Przykładowo.
    sc01_static_sum = 0
    sc01_elem = find_static_component_by_name(root, "SC01")
    if sc01_elem is not None:
        hull_sc = sc01_elem.find("StaticComponentPart/StaticComponentHull")
        if hull_sc is not None:
            segs = parse_outline(hull_sc.attrib.get("value", ""))
            for (_, _, _, _, _, chord_length) in segs:
                sc01_static_sum += chord_length

    dc01_vdef_sum = 0
    for dc01 in root.findall(".//VDeformableComponent[WorkpieceComponentName[@value='DC01']]"):
        hulls = dc01.find("VDeformableComponentHulls")
        if hulls is not None:
            segs = parse_outline(hulls.attrib.get("value", ""))
            arc_val = None
            if segs:
                arc_val = segs[0][2]  # x2 z pierwszego segmentu
            for (x1, y1, x2, y2, is_arc, chord_length) in segs:
                if arc_val is not None:
                    dc01_vdef_sum += arc_val
                else:
                    dc01_vdef_sum += chord_length

    computed_length = sc01_static_sum + dc01_vdef_sum
    result['rozwiniecie_obliczeniowe'] = round(computed_length, 5)

    return result


def main():
    # Szukamy wszystkich plików .dld w bieżącym folderze
    dld_files = glob.glob("*.dld")
    if not dld_files:
        print("Nie znaleziono plików .dld w bieżącym folderze.")
        return

    all_odcinki_results = []
    all_zw_results = []
    
    for filepath in dld_files:
        # 1) Przetwarzanie do wyniki_odcinki
        file_results = process_file(filepath)
        all_odcinki_results.extend(file_results)

        # 2) Tworzenie podsumowania do wyniki_zw
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
        except ET.ParseError:
            continue

        summary_row = create_simplified_summary(root, os.path.basename(filepath))
        all_zw_results.append(summary_row)

    # --- Zapisujemy wyniki_odcinki.xlsx ---
    columns_odcinki = [
        "Nazwa pliku", "Komponent", "Źródło outline", "Odcinek nr",
        "X1", "Y1", "X2", "Y2", "Łuk?", "Długość cięciwy", "Długość łuku",
        "Czy odcinek skrajny"
    ]
    df_odcinki = pd.DataFrame(all_odcinki_results, columns=columns_odcinki)
    df_odcinki.to_excel("wyniki_odcinki.xlsx", index=False)
    print(f"Plik 'wyniki_odcinki.xlsx' został wygenerowany.")

    # --- Zapisujemy wyniki_zw.xlsx ---
    columns_zw = [
        'nazwa_pliku',
        'liczba_odcinkow',
        'wymiary_zewnetrzne',
        'wymiary_wewnetrzne',
        'promien_wewnetrzny',
        'dlugosc_zlamu',
        'rozwiniecie_obliczeniowe',
        'rozwiniecie_z_pliku'
    ]
    df_zw = pd.DataFrame(all_zw_results, columns=columns_zw)
    df_zw.to_excel("wyniki_zw.xlsx", index=False)
    print(f"Plik 'wyniki_zw.xlsx' został wygenerowany.")


if __name__ == "__main__":
    main()
