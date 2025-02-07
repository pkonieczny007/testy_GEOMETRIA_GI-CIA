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
    filename = os.path.basename(filepath)
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        return results

    static_components = []
    for static_comp in root.findall(".//StaticComponent"):
        comp_name = static_comp.find("WorkpieceComponentName").attrib.get("value", "")
        static_components.append(comp_name)
        hull_elem = static_comp.find("StaticComponentPart/StaticComponentHull")
        if hull_elem:
            outline_str = hull_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                arc_length = chord_length
                skrajny = (comp_name == "MainPlane" or comp_name in ["SC01", "SC02", "SC03"])  # Adjust based on naming
                results.append([filename, comp_name, "StaticComponentHull", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length, skrajny])
        
        def_comp = static_comp.find("DeformableCompShortening")
        if def_comp:
            dc_name = def_comp.find("DeformableComponentName").attrib.get("value", "")
            contour_elem = def_comp.find("ShorteningContour")
            if contour_elem:
                outline_str = contour_elem.attrib.get("value", "")
                segments = parse_outline(outline_str)
                for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                    arc_length = chord_length
                    skrajny = (i == 0 or i == len(segments) - 1)
                    results.append([filename, dc_name, "ShorteningContour", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length, skrajny])
    
    for vdeform in root.findall(".//VDeformableComponent"):
        comp_name = vdeform.find("WorkpieceComponentName").attrib.get("value", "")
        bend_line_elem = vdeform.find("VDeformableComponentBendLine")
        if bend_line_elem:
            outline_str = bend_line_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                arc_length = chord_length
                skrajny = (i == 0 or i == len(segments) - 1)
                results.append([filename, comp_name, "VDeformableComponentBendLine", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length, skrajny])
        
        hulls_elem = vdeform.find("VDeformableComponentHulls")
        if hulls_elem:
            outline_str = hulls_elem.attrib.get("value", "")
            segments = parse_outline(outline_str)
            for i, (x1, y1, x2, y2, is_arc, chord_length) in enumerate(segments):
                arc_length = segments[0][2] if comp_name.startswith("DC") else chord_length
                skrajny = (i == 0 or i == len(segments) - 1)
                results.append([filename, comp_name, "VDeformableComponentHulls", i+1, x1, y1, x2, y2, is_arc, chord_length, arc_length, skrajny])
    
    return results

def process_summary(filepath, detailed_rows):
    summary = {}
    filename = os.path.basename(filepath)
    summary["Nazwa pliku"] = filename

    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        return summary

    bend_sequence = root.find(".//BendSequence")
    summary["Liczba odcinkow"] = len(bend_sequence.findall("BendStep")) + 1 if bend_sequence else None

    workpiece = root.find(".//Workpiece")
    thickness = 0
    dims_mode = ""
    if workpiece:
        wp_thickness_elem = workpiece.find("WorkpieceThickness")
        if wp_thickness_elem:
            try:
                thickness = float(wp_thickness_elem.attrib.get("value", "0").replace(',', '.'))
            except ValueError:
                pass
        dims_mode = workpiece.find("WorkpieceDimensions").attrib.get("value", "") if workpiece.find("WorkpieceDimensions") else ""
    summary["Typ"] = dims_mode

    base_list = []
    skrajny_segments = []
    for row in detailed_rows:
        if row[0] == filename and row[2] == "StaticComponentHull" and row[3] == 2:
            if row[11]:  # Check 'Skrajny' flag
                skrajny_segments.append(float(row[10]))
            base_list.append(float(row[10]))

    if dims_mode.lower() == "outside":
        dc_list = []
        for row in detailed_rows:
            if row[0] == filename and row[2] == "ShorteningContour" and row[3] == 2 and row[1].startswith("DC"):
                dc_list.append(float(row[10]))
        
        ext_dims = []
        if len(base_list) > 0 and len(dc_list) == len(base_list) - 1:
            ext_dims.append(base_list[0] + dc_list[0])
            for i in range(1, len(base_list)-1):
                ext_dims.append(dc_list[i-1] + base_list[i] + dc_list[i])
            ext_dims.append(dc_list[-1] + base_list[-1])
            summary["Wymiary zewnetrzne"] = ",".join(f"{x:.6f}" for x in ext_dims)
        else:
            summary["Wymiary zewnetrzne"] = ""
        summary["Wymiary wewnętrzne"] = ""
    elif dims_mode.lower() == "inside":
        summary["Wymiary wewnętrzne"] = ",".join(f"{x:.6f}" for x in skrajny_segments) if skrajny_segments else ""
        summary["Wymiary zewnetrzne"] = ""
    else:
        summary["Wymiary zewnetrzne"] = ""
        summary["Wymiary wewnętrzne"] = ""

    inner_radii = []
    for v in root.findall(".//VDeformableComponent"):
        radius_elem = v.find("ActualInnerRadius")
        if radius_elem is not None:
            inner_radii.append(radius_elem.attrib.get("value", "").replace(',', '.'))
    summary["Promień wewnętrzny"] = ", ".join(inner_radii)

    bend_length = None
    if bend_sequence:
        first_bendstep = bend_sequence.find("BendStep")
        if first_bendstep:
            bend_length_elem = first_bendstep.find(".//BendLength")
            if bend_length_elem:
                bend_length = bend_length_elem.attrib.get("value", "").replace(',', '.')
    summary["Długość złamu"] = bend_length

    blank_length = bend_sequence.find("BlankLength").attrib.get("value", "").replace(',', '.') if bend_sequence else None
    summary["Rozwinięcie z pliku"] = blank_length

    computed_unfolding = sum(float(row[10]) for row in detailed_rows if row[0] == filename and row[2] in ["StaticComponentHull", "VDeformableComponentHulls"] and row[3] == 2)
    summary["Rozwinięcie wyliczeniowe"] = round(computed_unfolding, 6) if computed_unfolding else None

    summary["Wymiary"] = ",".join(f"{x:.6f}" for x in base_list) if base_list else ""
    
    luke_list = {}
    for row in detailed_rows:
        if row[0] == filename and row[2] == "VDeformableComponentHulls" and row[3] == 1:
            comp = row[1]
            luke_list[comp] = float(row[10])
    summary["Łuki"] = ",".join(f"{luke_list[k]:.1f}" for k in sorted(luke_list)) if luke_list else ""

    return summary

def main():
    dld_files = glob.glob("*.dld")
    if not dld_files:
        print("Nie znaleziono plików .dld.")
        return

    all_detailed = []
    summaries = []
    for filepath in dld_files:
        detailed_rows = process_file(filepath)
        all_detailed.extend(detailed_rows)
        summary = process_summary(filepath, detailed_rows)
        summaries.append(summary)

    detailed_columns = ["Nazwa pliku", "Komponent", "Źródło outline", "Odcinek nr", "X1", "Y1", "X2", "Y2", "Łuk?", "Długość cięciwy", "Długość łuku", "Skrajny"]
    df_detailed = pd.DataFrame(all_detailed, columns=detailed_columns)
    df_detailed.to_excel("wyniki_odcinki_v3.xlsx", index=False)

    summary_columns = ["Nazwa pliku", "Liczba odcinkow", "Wymiary zewnetrzne", "Wymiary wewnętrzne", "Promień wewnętrzny", "Długość złamu", "Rozwinięcie wyliczeniowe", "Rozwinięcie z pliku", "Wymiary", "Łuki", "Typ"]
    df_summary = pd.DataFrame(summaries, columns=summary_columns)
    df_summary.to_excel("wyniki_zw_v3.xlsx", index=False)

if __name__ == "__main__":
    main()
