import os
import glob
import math
import xml.etree.ElementTree as ET
import pandas as pd

def parse_outline(outline_str):
    """
    Parsuje ciąg znaków z atrybutu 'value' elementu Outline.
    Obsługuje dwa formaty:
      - format standardowy (pierwszy token – liczba segmentów)
      - format z tokenem "Outline" (dla VDeformableComponentHulls)
    Zwraca listę krotek:
       (X1, Y1, X2, Y2, is_arc, chord_length)
    """
    tokens = outline_str.split()
    if not tokens:
        return []
    if len(tokens) > 1 and tokens[1] == "Outline":
        try:
            n_segments = int(tokens[2])
        except ValueError:
            print("Błąd przy odczycie liczby segmentów (Outline format):", outline_str)
            return []
        start_index = 3
    else:
        try:
            n_segments = int(tokens[0])
        except ValueError:
            print("Błąd przy odczycie liczby segmentów:", outline_str)
            return []
        start_index = 1

    segments = []
    for i in range(n_segments):
        idx = start_index + i * 5
        try:
            x1 = float(tokens[idx].replace(',', '.'))
            y1 = float(tokens[idx+1].replace(',', '.'))
            x2 = float(tokens[idx+2].replace(',', '.'))
            y2 = float(tokens[idx+3].replace(',', '.'))
            is_arc = tokens[idx+4].lower() in ["true", "prawda"]
        except (ValueError, IndexError):
            print("Błąd przy parsowaniu segmentu:", tokens[idx:idx+5])
            continue
        chord_length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        segments.append((x1, y1, x2, y2, is_arc, chord_length))
    return segments

def process_file(filepath):
    """
    Przetwarza jeden plik XML (.dld) i zwraca listę wierszy z danymi szczegółowymi.
    Każdy wiersz zawiera:
      [Nazwa pliku, Komponent, Źródło outline, Odcinek nr, X1, Y1, X2, Y2, Łuk?, Długość cięciwy, Długość łuku, Skrajny]
    """
    results = []
    filename = os.path.basename(filepath)
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Błąd parsowania pliku {filepath}: {e}")
        return results

    # Przetwarzanie elementów StaticComponent
    for static_comp in root.findall(".//StaticComponent"):
        comp_elem = static_comp.find("WorkpieceComponentName")
        comp_name = comp_elem.attrib.get("value", "") if comp_elem is not None else ""
        
        # StaticComponentHull
        hull_elem = static_comp.find("StaticComponentPart/StaticComponentHull")
        if hull_elem is not None:
            outline_str = hull_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                arc_length = chord_length  # dla StaticComponentHull – przyjmujemy długość cięciwy
                skrajny = (i == 0 or i == len(segments) - 1)
                results.append([filename, comp_name, "StaticComponentHull", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length, skrajny])
        
        # ShorteningContour (z DeformableCompShortening)
        def_comp = static_comp.find("DeformableCompShortening")
        if def_comp is not None:
            dc_elem = def_comp.find("DeformableComponentName")
            comp_dc = dc_elem.attrib.get("value", "") if dc_elem is not None else ""
            contour_elem = def_comp.find("ShorteningContour")
            if contour_elem is not None:
                outline_str = contour_elem.attrib.get("value", "")
                segments = parse_outline(outline_str)
                for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                    arc_length = chord_length
                    skrajny = (i == 0 or i == len(segments) - 1)
                    results.append([filename, comp_dc, "ShorteningContour", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length, skrajny])
    
    # Przetwarzanie elementów VDeformableComponent
    for vdeform in root.findall(".//VDeformableComponent"):
        comp_elem = vdeform.find("WorkpieceComponentName")
        comp_name = comp_elem.attrib.get("value", "") if comp_elem is not None else ""
        
        # VDeformableComponentBendLine – przetwarzamy standardowo
        bend_line_elem = vdeform.find("VDeformableComponentBendLine")
        if bend_line_elem is not None:
            outline_str = bend_line_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                arc_length = chord_length
                skrajny = (i == 0 or i == len(segments) - 1)
                results.append([filename, comp_name, "VDeformableComponentBendLine", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length, skrajny])
        
        # VDeformableComponentHulls – dla komponentów DC pobieramy długość łuku wg danych z pliku
        hulls_elem = vdeform.find("VDeformableComponentHulls")
        if hulls_elem is not None:
            outline_str = hulls_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            if segments:
                if comp_name.startswith("DC"):
                    arc_val = segments[0][2]
                else:
                    arc_val = None
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                if comp_name.startswith("DC") and arc_val is not None:
                    arc_length = arc_val
                else:
                    arc_length = chord_length
                skrajny = (i == 0 or i == len(segments) - 1)
                results.append([filename, comp_name, "VDeformableComponentHulls", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length, skrajny])
    
    return results

def process_summary(filepath, detailed_rows):
    """
    Przetwarza plik XML i zwraca słownik z danymi podsumowania:
      - Nazwa pliku
      - Liczba odcinków (liczba BendStep + 1)
      - Wymiary zewnetrzne lub wewnętrzne (wyliczone według wytycznych)
      - Promień wewnętrzny
      - Długość złamu (pierwszy BendLength)
      - Rozwinięcie wyliczeniowe – suma długości odcinka nr 2 z wybranych źródeł
      - Rozwinięcie z pliku – BlankLength z BendSequence
      - Wymiary – dla StaticComponentHull (odcinek nr 2) (kolumna pomocnicza)
      - Łuki – dla VDeformableComponentHulls (odcinek nr 1) (kolumna pomocnicza)
      - Typ – rodzaj wymiarowania (Inside lub Outside)
    """
    summary = {}
    filename = os.path.basename(filepath)
    summary["Nazwa pliku"] = filename

    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Błąd parsowania pliku {filepath}: {e}")
        return summary

    # Liczba odcinków = liczba BendStep + 1
    bend_sequence = root.find(".//BendSequence")
    if bend_sequence is not None:
        bend_steps = bend_sequence.findall("BendStep")
        summary["Liczba odcinkow"] = len(bend_steps) + 1
    else:
        summary["Liczba odcinkow"] = None

    # Odczyt trybu wymiarowania i WorkpieceName oraz grubości
    workpiece = root.find(".//Workpiece")
    thickness = 0
    dims_mode = ""
    if workpiece is not None:
        wp_name_elem = workpiece.find("WorkpieceName")
        wp_thickness_elem = workpiece.find("WorkpieceThickness")
        wp_dims_elem = workpiece.find("WorkpieceDimensions")
        if wp_thickness_elem is not None:
            try:
                thickness = float(wp_thickness_elem.attrib.get("value", "0").replace(',', '.'))
            except ValueError:
                thickness = 0
        dims_mode = wp_dims_elem.attrib.get("value", "") if wp_dims_elem is not None else ""
        wp_name = wp_name_elem.attrib.get("value", "") if wp_name_elem is not None else ""
    else:
        wp_name = ""
    summary["Typ"] = dims_mode  # dodajemy typ wymiarowania

    # Obliczanie wymiarów na podstawie odcinka nr 2 z StaticComponentHull
    base_dims = {}
    for row in detailed_rows:
        if row[0] == filename and row[2] == "StaticComponentHull" and row[3] == 2:
            comp = row[1]
            try:
                base_dims[comp] = float(row[10])
            except:
                continue

    if dims_mode.lower() == "outside":
        # Dla Outside wymiar zewnetrzny = base (StaticComponentHull) + ShorteningContour (odcinek nr 2) z komponentu DC (np. DC00)
        dc_val = None
        for row in detailed_rows:
            if (row[0] == filename and row[2] == "ShorteningContour" and row[3] == 2 
                and row[1].startswith("DC")):
                try:
                    dc_val = float(row[10])
                except:
                    continue
                break
        ext_dims = {}
        if dc_val is not None:
            for comp, val in base_dims.items():
                ext_dims[comp] = val + dc_val
        if ext_dims:
            summary["Wymiary zewnetrzne"] = ",".join(str(round(ext_dims[k], 2)) for k in sorted(ext_dims.keys()))
        else:
            summary["Wymiary zewnetrzne"] = ""
        summary["Wymiary wewnętrzne"] = ""
    elif dims_mode.lower() == "inside":
        # Dla Inside przyjmujemy wartości z StaticComponentHull (odcinek nr 2) jako wymiary wewnętrzne
        if base_dims:
            summary["Wymiary wewnętrzne"] = ",".join(str(round(base_dims[k], 2)) for k in sorted(base_dims.keys()))
        else:
            summary["Wymiary wewnętrzne"] = ""
        summary["Wymiary zewnetrzne"] = ""
    else:
        summary["Wymiary zewnetrzne"] = ""
        summary["Wymiary wewnętrzne"] = ""

    # Promień wewnętrzny – zbieramy wszystkie ActualInnerRadius z VDeformableComponent
    inner_radii = []
    for v in root.findall(".//VDeformableComponent"):
        for radius_tag in v.findall("ActualInnerRadius"):
            val = radius_tag.attrib.get("value", "").replace(',', '.')
            if val:
                inner_radii.append(val)
    summary["Promień wewnętrzny"] = ", ".join(inner_radii)

    # Długość złamu – pobieramy z pierwszego BendStep
    bend_length = None
    if bend_sequence is not None:
        first_bendstep = bend_sequence.find("BendStep")
        if first_bendstep is not None:
            ds_state = first_bendstep.find("DeformableSystemState")
            if ds_state is not None:
                bend_length_elem = ds_state.find("BendLength")
                if bend_length_elem is not None:
                    bend_length = bend_length_elem.attrib.get("value", "").replace(',', '.')
    summary["Długość złamu"] = bend_length

    # Rozwinięcie z pliku – z BlankLength
    blank_length = None
    if bend_sequence is not None:
        blank_elem = bend_sequence.find("BlankLength")
        if blank_elem is not None:
            blank_length = blank_elem.attrib.get("value", "").replace(',', '.')
    summary["Rozwinięcie z pliku"] = blank_length

    # Rozwinięcie wyliczeniowe – suma odcinka nr 2 z wybranych źródeł
    computed_unfolding = 0
    for row in detailed_rows:
        # Wiersz: [filename, Komponent, źródło, odcinek_nr, ..., Długość łuku (index 10), Skrajny (index 11)]
        if row[0] == filename and row[2] in ["StaticComponentHull", "VDeformableComponentHulls"] and row[3] == 2:
            try:
                computed_unfolding += float(row[10])
            except:
                pass
    summary["Rozwinięcie wyliczeniowe"] = round(computed_unfolding, 6) if computed_unfolding else None

    # Nowa kolumna "Wymiary" – pomocnicza, pobieramy wartości z StaticComponentHull (odcinek nr 2)
    if base_dims:
        summary["Wymiary"] = ",".join(str(round(base_dims[k], 2)) for k in sorted(base_dims.keys()))
    else:
        summary["Wymiary"] = ""

    # Nowa kolumna "Łuki" – pomocnicza, pobieramy dla każdego unikalnego VDeformableComponentHulls, odcinek nr 1
    luke_list = {}
    for row in detailed_rows:
        if row[0] == filename and row[2] == "VDeformableComponentHulls" and row[3] == 1:
            comp = row[1]
            try:
                val = float(row[10])
            except:
                continue
            luke_list[comp] = val
    if luke_list:
        summary["Łuki"] = ",".join(str(round(luke_list[k], 1)) for k in sorted(luke_list.keys()))
    else:
        summary["Łuki"] = ""

    return summary

def main():
    # Szukamy wszystkich plików .dld w bieżącym folderze
    dld_files = glob.glob("*.dld")
    if not dld_files:
        print("Nie znaleziono plików .dld w bieżącym folderze.")
        return

    all_detailed = []
    summaries = []
    for filepath in dld_files:
        detailed_rows = process_file(filepath)
        all_detailed.extend(detailed_rows)
        summary = process_summary(filepath, detailed_rows)
        summaries.append(summary)

    # Zapis wyników szczegółowych do pliku wyniki_odcinki_v3.xlsx
    detailed_columns = [
        "Nazwa pliku", "Komponent", "Źródło outline", "Odcinek nr", 
        "X1", "Y1", "X2", "Y2", "Łuk?", "Długość cięciwy", "Długość łuku", "Skrajny"
    ]
    df_detailed = pd.DataFrame(all_detailed, columns=detailed_columns)
    output_detailed = "wyniki_odcinki_v3.xlsx"
    df_detailed.to_excel(output_detailed, index=False)
    print(f"Wyniki szczegółowe zapisano w pliku '{output_detailed}'.")

    # Zapis wyników podsumowania do pliku wyniki_zw_v3.xlsx
    summary_columns = [
        "Nazwa pliku", "Liczba odcinkow", "Wymiary zewnetrzne", "Wymiary wewnętrzne",
        "Promień wewnętrzny", "Długość złamu", "Rozwinięcie wyliczeniowe", "Rozwinięcie z pliku",
        "Wymiary", "Łuki", "Typ"
    ]
    df_summary = pd.DataFrame(summaries, columns=summary_columns)
    output_summary = "wyniki_zw_v3.xlsx"
    df_summary.to_excel(output_summary, index=False)
    print(f"Wyniki podsumowania zapisano w pliku '{output_summary}'.")

if __name__ == "__main__":
    main()
