import os
import glob
import math
import xml.etree.ElementTree as ET
import pandas as pd

def parse_outline(outline_str):
    """
    Parsuje ciąg znaków z atrybutu 'value' elementu Outline.
    Obsługuje dwa formaty:
      – standardowy, gdzie pierwszy token to liczba segmentów,
      – oraz format z dodatkowym tokenem "Outline" (dla VDeformableComponentHulls).
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
            # Zamieniamy ewentualne przecinki na kropki
            x1 = float(tokens[idx].replace(',', '.'))
            y1 = float(tokens[idx+1].replace(',', '.'))
            x2 = float(tokens[idx+2].replace(',', '.'))
            y2 = float(tokens[idx+3].replace(',', '.'))
            # Przyjmujemy, że "true"/"prawda" oznacza True – pozostałe traktujemy jako False
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
    Przetwarza jeden plik XML i zwraca słownik z danymi podsumowania:
      - Nazwa pliku
      - Liczba odcinkow (liczba BendStep + 1)
      - Wymiary zewnetrzne (pobrane z WorkpieceName – zakładamy format "A x B x C x T")
      - Wymiary wewnętrzne (dla zewnetrznego wymiarowania: [A-T, B-2*T, C-T])
      - Promień wewnętrzny (wszystkie ActualInnerRadius)
      - Długość złamu (pobrana z pierwszego BendStep, element BendLength)
      - Rozwinięcie wyliczeniowe – suma długości odcinków o numerze 2 z:
           StaticComponentHull (dla MainPlane, SC00, SC01)
         oraz VDeformableComponentHulls (dla komponentów zaczynających się od "DC")
      - Rozwinięcie z pliku – wartość BlankLength z BendSequence
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

    # Liczba odcinkow = liczba BendStep + 1
    bend_sequence = root.find(".//BendSequence")
    if bend_sequence is not None:
        bend_steps = bend_sequence.findall("BendStep")
        summary["Liczba odcinkow"] = len(bend_steps) + 1
    else:
        summary["Liczba odcinkow"] = None

    # Wymiary – pobieramy nazwę detalu, grubość i tryb wymiarowania
    workpiece = root.find(".//Workpiece")
    if workpiece is not None:
        wp_name_elem = workpiece.find("WorkpieceName")
        wp_thickness_elem = workpiece.find("WorkpieceThickness")
        wp_dims_elem = workpiece.find("WorkpieceDimensions")
        if wp_name_elem is not None and wp_thickness_elem is not None and wp_dims_elem is not None:
            wp_name = wp_name_elem.attrib.get("value", "")
            thickness = float(wp_thickness_elem.attrib.get("value", "0").replace(',', '.'))
            dims_mode = wp_dims_elem.attrib.get("value", "")
            # Przykładowo: "70x60x20x2"
            parts = wp_name.split("x")
            if len(parts) >= 3:
                try:
                    ext_dims = [float(parts[0].replace(',', '.')), 
                                float(parts[1].replace(',', '.')), 
                                float(parts[2].replace(',', '.'))]
                except ValueError:
                    ext_dims = [None, None, None]
                summary["Wymiary zewnetrzne"] = ",".join(str(x) for x in ext_dims)
                if dims_mode.lower() == "outside":
                    # Zakładamy: wymiary wewnętrzne = [A - thickness, B - 2*thickness, C - thickness]
                    int_dims = [ext_dims[0] - thickness, ext_dims[1] - 2 * thickness, ext_dims[2] - thickness]
                else:
                    int_dims = ext_dims  # lub inna logika, gdyby wymiarowano wewnętrznie
                summary["Wymiary wewnętrzne"] = ",".join(str(round(x, 3)) for x in int_dims)
            else:
                summary["Wymiary zewnetrzne"] = ""
                summary["Wymiary wewnętrzne"] = ""
        else:
            summary["Wymiary zewnetrzne"] = ""
            summary["Wymiary wewnętrzne"] = ""
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

    # Rozwinięcie wyliczeniowe – suma odcinków o numerze 2 z wybranych elementów
    computed_unfolding = 0
    for row in detailed_rows:
        # Format wiersza: [filename, comp_name, źródło, odcinek_nr, ..., Długość łuku (index 10), Skrajny (index 11)]
        if row[0] == filename and row[3] == 2:
            if row[2] in ["StaticComponentHull", "VDeformableComponentHulls"]:
                try:
                    computed_unfolding += float(row[10])
                except:
                    pass
    summary["Rozwinięcie wyliczeniowe"] = round(computed_unfolding, 6) if computed_unfolding else None

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

    # Zapis wyników szczegółowych do pliku wyniki_odcinki.xlsx
    detailed_columns = [
        "Nazwa pliku", "Komponent", "Źródło outline", "Odcinek nr", 
        "X1", "Y1", "X2", "Y2", "Łuk?", "Długość cięciwy", "Długość łuku", "Skrajny"
    ]
    df_detailed = pd.DataFrame(all_detailed, columns=detailed_columns)
    output_detailed = "wyniki_odcinki.xlsx"
    df_detailed.to_excel(output_detailed, index=False)
    print(f"Wyniki szczegółowe zapisano w pliku '{output_detailed}'.")

    # Zapis wyników podsumowania do pliku wyniki_zw.xlsx
    summary_columns = ["Nazwa pliku", "Liczba odcinkow", "Wymiary zewnetrzne", "Wymiary wewnętrzne",
                       "Promień wewnętrzny", "Długość złamu", "Rozwinięcie wyliczeniowe", "Rozwinięcie z pliku"]
    df_summary = pd.DataFrame(summaries, columns=summary_columns)
    output_summary = "wyniki_zw.xlsx"
    df_summary.to_excel(output_summary, index=False)
    print(f"Wyniki podsumowania zapisano w pliku '{output_summary}'.")

if __name__ == "__main__":
    main()
