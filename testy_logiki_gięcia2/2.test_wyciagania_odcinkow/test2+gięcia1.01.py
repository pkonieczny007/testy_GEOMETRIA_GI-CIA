import os
import glob
import math
import xml.etree.ElementTree as ET
import pandas as pd

def parse_outline(outline_str):
    """
    Parsuje wartość atrybutu 'value' z elementu Outline.
    
    Format outline:
      Pierwszy token – liczba segmentów (N).
      Następnie dla każdego segmentu mamy 5 tokenów:
         X1, Y1, X2, Y2, flag (np. "false" lub "true")
    
    Zwraca listę krotek:
      (X1, Y1, X2, Y2, is_arc, chord_length)
    """
    tokens = outline_str.split()
    if not tokens:
        return []

    try:
        n_segments = int(tokens[0])
    except ValueError:
        print("Błąd przy odczycie liczby segmentów z outline:", outline_str)
        return []

    segments = []
    # Każdy segment zajmuje 5 tokenów
    for i in range(n_segments):
        idx = 1 + i * 5
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

    # --- Przetwarzanie elementów z StaticComponent ---
    for static_comp in root.findall(".//StaticComponent"):
        # Pobieramy nazwę komponentu z <WorkpieceComponentName>
        comp_elem = static_comp.find("WorkpieceComponentName")
        comp_name = comp_elem.attrib.get("value", "") if comp_elem is not None else ""
        
        # 1. Przetwarzanie StaticComponentHull
        hull_elem = static_comp.find("StaticComponentPart/StaticComponentHull")
        if hull_elem is not None:
            outline_str = hull_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                # Domyślnie przyjmujemy, że długość łuku = długość cięciwy
                arc_length = chord_length
                # Jeśli segment jest łukiem i komponent DC, przyjmujemy przelicznik (np. dla 90°)
                if is_arc and comp_name.startswith("DC"):
                    arc_length = chord_length * 1.11072
                results.append([filename, comp_name, "StaticComponentHull", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length])
        
        # 2. Przetwarzanie ShorteningContour (z DeformableCompShortening)
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
                    if is_arc and comp_dc.startswith("DC"):
                        arc_length = chord_length * 1.11072
                    results.append([filename, comp_dc, "ShorteningContour", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length])
    
    # --- Przetwarzanie elementów z VDeformableComponent ---
    for vdeform in root.findall(".//VDeformableComponent"):
        comp_elem = vdeform.find("WorkpieceComponentName")
        comp_name = comp_elem.attrib.get("value", "") if comp_elem is not None else ""
        
        # Przykład: przetwarzanie linii gięcia z VDeformableComponentBendLine
        bend_line_elem = vdeform.find("VDeformableComponentBendLine")
        # Próba pobrania dodatkowych danych, jeśli dostępne (kąt gięcia, promień)
        angle_elem = vdeform.find("VDeformableComponentAngle")
        radius_elem = vdeform.find("PreferredInnerRadius")
        if angle_elem is not None and radius_elem is not None:
            try:
                angle_deg = float(angle_elem.attrib.get("value", "0"))
                angle_rad = math.radians(angle_deg)
                preferred_radius = float(radius_elem.attrib.get("value", "0"))
            except ValueError:
                angle_rad = None
                preferred_radius = None
        else:
            angle_rad = None
            preferred_radius = None
        
        if bend_line_elem is not None:
            outline_str = bend_line_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                # Jeśli segment jest łukiem i komponent DC, spróbuj obliczyć długość łuku
                if is_arc and comp_name.startswith("DC") and angle_rad is not None and preferred_radius is not None:
                    # Jeśli mamy kąt i promień – obliczamy długość łuku klasycznym wzorem
                    arc_length = angle_rad * preferred_radius
                elif is_arc and comp_name.startswith("DC"):
                    arc_length = chord_length * 1.11072
                else:
                    arc_length = chord_length
                results.append([filename, comp_name, "VDeformableComponentBendLine", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length])
        
        # Przetwarzanie elementu VDeformableComponentHulls (jeśli występuje)
        hulls_elem = vdeform.find("VDeformableComponentHulls")
        if hulls_elem is not None:
            outline_str = hulls_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                if is_arc and comp_name.startswith("DC"):
                    arc_length = chord_length * 1.11072
                else:
                    arc_length = chord_length
                results.append([filename, comp_name, "VDeformableComponentHulls", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length])
    
    return results

def main():
    # Szukanie wszystkich plików .dld w bieżącym folderze
    dld_files = glob.glob("*.dld")
    if not dld_files:
        print("Nie znaleziono plików .dld w bieżącym folderze.")
        return

    all_results = []
    for filepath in dld_files:
        file_results = process_file(filepath)
        all_results.extend(file_results)

    # Definicja kolumn:
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
