import os
import glob
import math
import xml.etree.ElementTree as ET
import pandas as pd

def parse_outline(outline_str):
    """
    Parsuje ciąg znaków z atrybutu 'value' elementu Outline.
    
    Obsługuje dwa formaty:
      1. Format standardowy: 
         np. "4 50 295.44915 0 295.44915 false ..." 
         – gdzie pierwszy token to liczba segmentów.
      2. Format używany przez VDeformableComponentHulls:
         np. "1 Outline 4 0 0 5.927563 0 false ..." 
         – gdzie tokeny[0] = liczba outline’ów (np. "1"),
           tokeny[1] = "Outline",
           tokeny[2] = liczba segmentów,
           a segmenty zaczynają się od tokenu o indeksie 3.
           
    Zwraca listę krotek:
       (X1, Y1, X2, Y2, is_arc, chord_length)
    """
    tokens = outline_str.split()
    if not tokens:
        return []

    # Sprawdź, czy mamy format "Outline"
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
            x1 = float(tokens[idx])
            y1 = float(tokens[idx+1])
            x2 = float(tokens[idx+2])
            y2 = float(tokens[idx+3])
            is_arc = tokens[idx+4].lower() == "true"
        except (ValueError, IndexError):
            print("Błąd przy parsowaniu segmentu:", tokens[idx:idx+5])
            continue
        chord_length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        segments.append((x1, y1, x2, y2, is_arc, chord_length))
    return segments

def process_file(filepath):
    """
    Przetwarza jeden plik XML (.dld) i zwraca listę wierszy z danymi.
    
    Każdy wiersz zawiera:
      [Nazwa pliku, Komponent, Źródło outline, Odcinek nr, X1, Y1, X2, Y2, Łuk?, Długość cięciwy, Długość łuku]
    """
    results = []
    filename = os.path.basename(filepath)
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Błąd parsowania pliku {filepath}: {e}")
        return results

    # --- Przetwarzanie elementów z StaticComponent (np. MainPlane, SCxx) ---
    for static_comp in root.findall(".//StaticComponent"):
        comp_elem = static_comp.find("WorkpieceComponentName")
        comp_name = comp_elem.attrib.get("value", "") if comp_elem is not None else ""
        
        # 1. StaticComponentHull
        hull_elem = static_comp.find("StaticComponentPart/StaticComponentHull")
        if hull_elem is not None:
            outline_str = hull_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                arc_length = chord_length  # dla statycznych elementów przyjmujemy cięciwę
                results.append([filename, comp_name, "StaticComponentHull", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length])
        
        # 2. ShorteningContour (z DeformableCompShortening)
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
                    results.append([filename, comp_dc, "ShorteningContour", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length])
    
    # --- Przetwarzanie elementów z VDeformableComponent ---
    for vdeform in root.findall(".//VDeformableComponent"):
        comp_elem = vdeform.find("WorkpieceComponentName")
        comp_name = comp_elem.attrib.get("value", "") if comp_elem is not None else ""
        
        # (A) VDeformableComponentBendLine – przetwarzamy standardowo
        bend_line_elem = vdeform.find("VDeformableComponentBendLine")
        if bend_line_elem is not None:
            outline_str = bend_line_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                # Dla BendLine zostawiamy arc_length równy cięciwie
                arc_length = chord_length
                results.append([filename, comp_name, "VDeformableComponentBendLine", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length])
        
        # (B) VDeformableComponentHulls – tutaj dla komponentów DC pobieramy długość łuku wg danych z pliku
        hulls_elem = vdeform.find("VDeformableComponentHulls")
        if hulls_elem is not None:
            outline_str = hulls_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            # Dla komponentów DC (DC00, DC01, DC02) chcemy pobrać wartość łuku z pierwszego segmentu
            if comp_name.startswith("DC") and segments:
                # Pobieramy wartość z pierwszego segmentu – X2
                arc_val = segments[0][2]
            else:
                arc_val = None
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                if comp_name.startswith("DC") and arc_val is not None:
                    arc_length = arc_val
                else:
                    arc_length = chord_length
                results.append([filename, comp_name, "VDeformableComponentHulls", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length])
    
    return results

def main():
    # Szukamy wszystkich plików .dld w bieżącym folderze
    dld_files = glob.glob("*.dld")
    if not dld_files:
        print("Nie znaleziono plików .dld w bieżącym folderze.")
        return

    all_results = []
    for filepath in dld_files:
        file_results = process_file(filepath)
        all_results.extend(file_results)

    # Definicja kolumn
    columns = [
        "Nazwa pliku", "Komponent", "Źródło outline", "Odcinek nr", 
        "X1", "Y1", "X2", "Y2", "Łuk?", "Długość cięciwy", "Długość łuku"
    ]
    df = pd.DataFrame(all_results, columns=columns)
    
    output_filename = "wyniki_odcinki.xlsx"
    df.to_excel(output_filename, index=False)
    print(f"Przetwarzanie zakończone. Wyniki zapisano w pliku '{output_filename}'.")

if __name__ == "__main__":
    main()
