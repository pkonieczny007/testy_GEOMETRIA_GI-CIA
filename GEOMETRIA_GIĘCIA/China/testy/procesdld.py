import xml.etree.ElementTree as ET
import os
import math
import pandas as pd

def parse_outline(value):
    tokens = value.split()
    try:
        num_points = int(tokens[0])
        coords = []
        for token in tokens[1:]:
            try:
                coords.append(float(token))
            except ValueError:
                continue  # Ignore 'false' and non-numeric values
        points = [(coords[i], coords[i + 1]) for i in range(0, len(coords) - 1, 2)]
        return points
    except (IndexError, ValueError):
        return []

def compute_lengths(points):
    lengths = []
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        lengths.append(length)
    return lengths, sum(lengths)

def process_dld_file(filepath, output_dir):
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Błąd parsowania pliku {filepath}: {e}")
        return

    results = []
    for component in root.findall(".//StaticComponent"):
        name = component.find("WorkpieceComponentName").get("value")
        hull = component.find(".//StaticComponentHull")
        if hull is not None:
            points = parse_outline(hull.get("value"))
            lengths, perimeter = compute_lengths(points)
            for i, segment_length in enumerate(lengths, start=1):
                results.append({"Component": name, "Segment Index": i, "Length": segment_length, "Perimeter": perimeter})

    if results:
        df = pd.DataFrame(results)
        output_filename = os.path.join(output_dir, os.path.basename(filepath).replace(".dld", "_results.xlsx"))
        df.to_excel(output_filename, index=False)
        print(f"Wyniki zapisano do: {output_filename}")

def process_all_dld_files():
    folder = os.getcwd()
    output_dir = os.path.join(folder, "wyniki_dld")
    os.makedirs(output_dir, exist_ok=True)
    
    dld_files = [f for f in os.listdir(folder) if f.endswith(".dld")]
    if not dld_files:
        print("Brak plików .dld w folderze.")
        return
    
    for dld_file in dld_files:
        process_dld_file(os.path.join(folder, dld_file), output_dir)
    print("Przetwarzanie zakończone.")

if __name__ == "__main__":
    process_all_dld_files()
