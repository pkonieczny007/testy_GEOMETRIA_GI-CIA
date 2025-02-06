import os
import glob
import math
import xml.etree.ElementTree as ET
import pandas as pd

def parse_outline(outline_str):
    """
    Parsuje wartość `value` z `StaticComponentHull` i zwraca listę odcinków.
    Każdy segment ma format:
       X1, Y1, X2, Y2, flag (czy jest łukiem)
    """
    tokens = outline_str.split()
    if not tokens:
        return []

    try:
        n_segments = int(tokens[0])  # Liczba odcinków
    except ValueError:
        print("Błąd przy odczycie liczby segmentów z outline:", outline_str)
        return []

    segments = []

    # Każdy segment składa się z 5 wartości
    for i in range(n_segments):
        idx = 1 + i * 5
        try:
            x1 = float(tokens[idx])
            y1 = float(tokens[idx+1])
            x2 = float(tokens[idx+2])
            y2 = float(tokens[idx+3])
            is_arc = tokens[idx+4].lower() == "true"  # Czy to łuk?
        except (ValueError, IndexError):
            print("Błąd przy parsowaniu segmentu:", tokens[idx:idx+5])
            continue

        # Obliczamy długość odcinka (dla łuków można rozszerzyć)
        length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        segments.append((x1, y1, x2, y2, is_arc, length))

    return segments

def process_file(filepath):
    """
    Przetwarza plik XML i zwraca listę odcinków dla każdego `StaticComponentHull`.
    """
    results = []
    filename = os.path.basename(filepath)

    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Błąd parsowania pliku {filepath}: {e}")
        return results

    # Szukamy wszystkich StaticComponentHull
    for hull_elem in root.findall(".//StaticComponentPart/StaticComponentHull"):
        outline_str = hull_elem.attrib.get("value", "")
        if outline_str:
            segments = parse_outline(outline_str)
            for i, (x1, y1, x2, y2, is_arc, length) in enumerate(segments):
                results.append([filename, i+1, x1, y1, x2, y2, is_arc, length])

    return results

def main():
    # Pobierz wszystkie pliki .dld w bieżącym folderze
    dld_files = glob.glob("*.dld")
    if not dld_files:
        print("Nie znaleziono plików .dld w bieżącym folderze.")
        return

    all_results = []

    # Przetwarzamy każdy plik
    for filepath in dld_files:
        results = process_file(filepath)
        all_results.extend(results)

    # Konwersja do DataFrame i zapis do pliku XLSX
    df = pd.DataFrame(all_results, columns=["Nazwa pliku", "Odcinek nr", "X1", "Y1", "X2", "Y2", "Łuk?", "Długość odcinka"])
    output_filename = "wyniki_odcinki.xlsx"
    df.to_excel(output_filename, index=False)

    print(f"Przetwarzanie zakończone. Wyniki zapisano w '{output_filename}'.")

if __name__ == "__main__":
    main()
