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
      - Wymiary zewnetrzne, Wymiary wewnętrzne
      - Promień wewnętrzny
      - Długość złamu (pierwszy BendLength)
      - Rozwinięcie wyliczeniowe – suma długości odcinka nr 2 z wybranych źródeł
      - Rozwinięcie z pliku – BlankLength z BendSequence
      - Wymiary – dla każdego StaticComponentHull (odcinek nr 2) – zaokrąglone do dwóch miejsc po przecinku
      - Łuki – dla każdego VDeformableComponentHulls (odcinek nr 1) – zaokrąglone do jednej cyfry po przecinku
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

    # Wymiary – próba odczytu z WorkpieceName
    workpiece = root.find(".//Workpiece")
    thickness = None
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
        if wp_name_elem is not None:
            wp_name = wp_name_elem.attrib.get("value", "")
        else:
            wp_name = ""
    else:
        wp_name = ""
        dims_mode = ""
        thickness = 0

    parts = wp_name.split("x")
    if len(parts) >= 3:
        try:
            ext_dims = [float(parts[0].replace(',', '.')),
                        float(parts[1].replace(',', '.')),
                        float(parts[2].replace(',', '.'))]
        except ValueError:
            ext_dims = []
    else:
        # Jeśli nazwa nie zawiera oczekiwanego formatu, wyliczamy wymiary na podstawie MainPlane
        main_planes = root.findall(".//StaticComponent[WorkpieceComponentName[@value='MainPlane']]")
        pts = []
        for mp in main_planes:
            hull = mp.find("StaticComponentPart/StaticComponentHull")
            if hull is not None:
                segs = parse_outline(hull.attrib.get("value", ""))
                for (x1, y1, x2, y2, _, _) in segs:
                    pts.append((x1, y1))
                    pts.append((x2, y2))
        if pts:
            xs = [pt[0] for pt in pts]
            ys = [pt[1] for pt in pts]
            width = round(max(xs) - min(xs), 2)
            height = round(max(ys) - min(ys), 2)
            # Przyjmujemy trzeci wymiar równy grubości
            ext_dims = [width, height, thickness if thickness is not None else 0]
        else:
            ext_dims = []

    if ext_dims and len(ext_dims) == 3:
        summary["Wymiary zewnetrzne"] = ",".join(str(x) for x in ext_dims)
        if dims_mode.lower() == "outside":
            int_dims = [round(ext_dims[0] - thickness, 3), round(ext_dims[1] - 2*thickness, 3), round(ext_dims[2] - thickness, 3)]
        else:
            int_dims = [round(x, 3) for x in ext_dims]
        summary["Wymiary wewnętrzne"] = ",".join(str(x) for x in int_dims)
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

    # Nowa kolumna "Wymiary" – zbieramy, dla każdego unikalnego StaticComponentHull, odcinek nr 2
    wymiary_list = {}
    for row in detailed_rows:
        if row[0] == filename and row[2] == "StaticComponentHull" and row[3] == 2:
            comp = row[1]
            try:
                val = float(row[10])
            except:
                continue
            wymiary_list[comp] = val
    # Sortujemy wg klucza (np. alfabetycznie) i łączymy wartości zaokrąglone do dwóch miejsc
    if wymiary_list:
        wymiary_str = ",".join(str(round(wymiary_list[k],2)) for k in sorted(wymiary_list.keys()))
    else:
        wymiary_str = ""
    summary["Wymiary"] = wymiary_str

    # Nowa kolumna "Łuki" – dla każdego unikalnego VDeformableComponentHulls, odcinek nr 1
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
        luke_str = ",".join(str(round(luke_list[k],1)) for k in sorted(luke_list.keys()))
    else:
        luke_str = ""
    summary["Łuki"] = luke_str

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
        "Wymiary", "Łuki"
    ]
    df_summary = pd.DataFrame(summaries, columns=summary_columns)
    output_summary = "wyniki_zw_v3.xlsx"
    df_summary.to_excel(output_summary, index=False)
    print(f"Wyniki podsumowania zapisano w pliku '{output_summary}'.")

if __name__ == "__main__":
    main()
