import os
import glob
import math
import xml.etree.ElementTree as ET
import pandas as pd

def parse_outline(outline_str):
    tokens = outline_str.split()
    if not tokens:
        return []
    if len(tokens) > 1 and tokens[1] == "Outline":
        try:
            n_segments = int(tokens[2])
        except ValueError:
            return []
        start_index = 3
    else:
        try:
            n_segments = int(tokens[0])
        except ValueError:
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
            continue
        chord_length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        segments.append((x1, y1, x2, y2, is_arc, chord_length))
    return segments

def process_file(filepath):
    results = []
    summary = {}
    filename = os.path.basename(filepath)
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError:
        return results, summary

    dims_mode = ""
    workpiece = root.find(".//Workpiece")
    if workpiece is not None:
        wp_dims_elem = workpiece.find("WorkpieceDimensions")
        dims_mode = wp_dims_elem.attrib.get("value", "") if wp_dims_elem is not None else ""
    summary["Nazwa pliku"] = filename
    summary["Typ"] = dims_mode
    
    base_list = []
    for static_comp in root.findall(".//StaticComponent"):
        hull_elem = static_comp.find("StaticComponentPart/StaticComponentHull")
        if hull_elem is not None:
            outline_str = hull_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            for i, (_, _, _, _, _, chord_length) in enumerate(segments):
                if i == 1:
                    base_list.append(chord_length)

    if dims_mode.lower() == "outside":
        summary["Wymiary zewnetrzne"] = ",".join(str(round(x, 6)) for x in base_list)
        summary["Wymiary wewnętrzne"] = ""
    else:
        summary["Wymiary wewnętrzne"] = ",".join(str(round(x, 6)) for x in base_list)
        summary["Wymiary zewnetrzne"] = ""
    
    return results, summary

def main():
    dld_files = glob.glob("*.dld")
    if not dld_files:
        print("Nie znaleziono plików .dld w bieżącym folderze.")
        return

    all_results = []
    summaries = []
    for filepath in dld_files:
        results, summary = process_file(filepath)
        all_results.extend(results)
        summaries.append(summary)

    df_results = pd.DataFrame(all_results, columns=[
        "Nazwa pliku", "Komponent", "Źródło", "Odcinek nr", 
        "X1", "Y1", "X2", "Y2", "Łuk?", "Długość cięciwy", "Skrajny"
    ])
    df_results.to_excel("wyniki_odcinki.xlsx", index=False)
    print("Wyniki szczegółowe zapisano w 'wyniki_odcinki.xlsx'")
    
    df_summaries = pd.DataFrame(summaries, columns=[
        "Nazwa pliku", "Typ", "Wymiary zewnetrzne", "Wymiary wewnętrzne"
    ])
    df_summaries.to_excel("wyniki_zw.xlsx", index=False)
    print("Wyniki podsumowania zapisano w 'wyniki_zw.xlsx'")

if __name__ == "__main__":
    main()
