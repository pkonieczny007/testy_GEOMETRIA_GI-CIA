import pandas as pd
import xml.etree.ElementTree as ET
import math
import os

# Funkcja normalizująca kąt do zakresu [-180, 180]
def normalize_angle(angle_deg):
    if angle_deg > 180:
        return angle_deg - 360
    return angle_deg

# Funkcja pomocnicza – zwraca listę segmentów z outline (każdy segment to krotka:
# (x1, y1, x2, y2, is_arc, chord_length))
def parse_outline_segments(outline_str):
    tokens = outline_str.split()
    if not tokens:
        return []
    # Sprawdzenie formatu – jeżeli drugi token to "Outline", to liczba segmentów jest pod tokenem 2
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

# Funkcje bounding box i wyznaczania width/height (używane przy parsowaniu, gdyby były potrzebne)
def parse_outline_value(value_str):
    tokens = value_str.split()
    numeric_vals = []
    for t in tokens:
        t_low = t.lower()
        if t_low in ['outline', 'true', 'false']:
            continue
        try:
            numeric_vals.append(float(t.replace(',', '.')))
        except ValueError:
            pass
    if not numeric_vals:
        return []
    coords = numeric_vals[1:]
    points = []
    for i in range(0, len(coords), 2):
        if i+1 < len(coords):
            points.append((coords[i], coords[i+1]))
    return points

def bounding_box(coords):
    if not coords:
        return (0, 0, 0, 0)
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    return (min(xs), max(xs), min(ys), max(ys))

def width_height_from_box(box):
    xmin, xmax, ymin, ymax = box
    return abs(xmax - xmin), abs(ymax - ymin)

# Funkcje działające na danych z Excela (wyniki_odcinki_v3.xlsx)
def compute_inside_dimensions(file_name, df_odcinki):
    df_file = df_odcinki[df_odcinki["Nazwa pliku"] == file_name]
    df_seg2 = df_file[df_file["Odcinek nr"] == 2]
    df_base = df_seg2[df_seg2["Źródło outline"] == "StaticComponentHull"]
    base_values = []
    for _, row in df_base.iterrows():
        try:
            val = float(str(row["Długość łuku"]).replace(',', '.'))
            base_values.append(val)
        except:
            pass
    df_dc = df_seg2[(df_seg2["Źródło outline"] == "ShorteningContour") &
                    (df_seg2["Komponent"].str.startswith("DC"))]
    dc_values = []
    for _, row in df_dc.iterrows():
        try:
            val = float(str(row["Długość łuku"]).replace(',', '.'))
            dc_values.append(val)
        except:
            pass
    computed_dims = []
    if len(base_values) == 2 and len(dc_values) == 1:
        computed_dims.append(base_values[0] + dc_values[0])
        computed_dims.append(base_values[1] + dc_values[0])
    elif len(base_values) > 2 and len(dc_values) == len(base_values) - 1:
        computed_dims.append(base_values[0] + dc_values[0])
        for i in range(1, len(base_values)-1):
            computed_dims.append(dc_values[i-1] + base_values[i] + dc_values[i])
        computed_dims.append(base_values[-1] + dc_values[-1])
    else:
        computed_dims = base_values
    return ",".join(str(round(x, 6)) for x in computed_dims)

def compute_dc_shortening(file_name, df_odcinki):
    df_file = df_odcinki[df_odcinki["Nazwa pliku"] == file_name]
    df_dc = df_file[(df_file["Odcinek nr"] == 2) &
                    (df_file["Źródło outline"] == "ShorteningContour") &
                    (df_file["Komponent"].str.startswith("DC"))]
    # W tej funkcji nie usuwamy duplikatów – każdy wiersz jest brany pod uwagę
    dc_values = []
    for _, row in df_dc.iterrows():
        try:
            val = float(str(row["Długość łuku"]).replace(',', '.'))
            dc_values.append(val)
        except:
            pass
    return ",".join(str(round(x, 2)) for x in dc_values)

def compute_bending_angles_from_xml(file_name):
    try:
        tree = ET.parse(file_name)
        root = tree.getroot()
    except ET.ParseError:
        return ""
    angles = []
    for v in root.findall(".//VDeformableComponent"):
        comp_elem = v.find("WorkpieceComponentName")
        if comp_elem is not None:
            comp_name = comp_elem.attrib.get("value", "")
            if comp_name.startswith("DC"):
                angle_after = 0.0
                angle_elem = v.find("VDeformableComponentAngle")
                if angle_elem is not None:
                    try:
                        angle_after = float(angle_elem.attrib.get("value", "0"))
                    except ValueError:
                        angle_after = 0.0
                deformation_elem = v.find("VBendDeformation")
                if deformation_elem is not None:
                    angle_after_elem = deformation_elem.find("AngleAfter")
                    if angle_after_elem is not None:
                        try:
                            angle_after = float(angle_after_elem.attrib.get("value", "0"))
                        except ValueError:
                            pass
                angle_norm = normalize_angle(angle_after)
                angles.append(int(round(angle_norm)))
    return ",".join(str(x) for x in angles)

# Funkcja compute_grouped_dimensions oparta na danych z Excela
def compute_grouped_dimensions(file_name, df_odcinki):
    df_file = df_odcinki[df_odcinki["Nazwa pliku"] == file_name]
    df_seg2 = df_file[df_file["Odcinek nr"] == 2]
    
    groups = []
    current_group = None
    for idx, row in df_seg2.iterrows():
        source = str(row["Źródło outline"]).strip().upper()
        comp = str(row["Komponent"]).strip().upper()
        try:
            value = float(str(row["Długość łuku"]).replace(',', '.'))
        except:
            continue
        if source == "STATICCOMPONENTHULL":
            if current_group is not None:
                groups.append(current_group)
            current_group = {"static": comp, "static_value": value, "dc": [], "dc_order": []}
        elif source == "SHORTENINGCONTOUR" and comp.startswith("DC"):
            if current_group is not None:
                current_group["dc"].append(value)
                current_group["dc_order"].append(comp)
    if current_group is not None:
        groups.append(current_group)
    
    output_lines = []
    for group in groups:
        static_comp = group["static"]
        static_val = group["static_value"]
        dc_order = group["dc_order"]
        dc_values = group["dc"]
        count_dc = len(dc_order)
        computed_values = []
        dc_values_str = []
        for i in range(count_dc):
            computed = static_val + dc_values[i]
            computed_values.append(computed)
            dc_values_str.append(f"{dc_order[i]}={round(dc_values[i],2)}")
        line = (f"{static_comp}: static={round(static_val,6)}, DC count={count_dc}, "
                f"DC values: {', '.join(dc_values_str)}; Computed dims: {', '.join(str(round(x,6)) for x in computed_values)}")
        output_lines.append(line)
    return "\n".join(output_lines)

# Funkcja compute_grouped2_dimensions – oparta na oryginalnym pliku XML
def compute_grouped2_dimensions(file_name):
    try:
        tree = ET.parse(file_name)
        root = tree.getroot()
    except ET.ParseError as e:
        return f"Błąd parsowania pliku {file_name}: {e}"
    
    # Zamiast używać bounding box dla całego outline, pobieramy wartość z segmentu nr 2.
    def get_static_value(elem):
        hull_elem = elem.find("./StaticComponentPart/StaticComponentHull")
        if hull_elem is not None:
            val_str = hull_elem.attrib.get("value", "")
            segments = parse_outline_segments(val_str)
            if len(segments) >= 2:
                # Drugi segment (indeks 1)
                return segments[1][5]  # chord_length
            elif segments:
                return segments[0][5]
        return 0.0
    
    def get_dc_value(elem):
        val_str = elem.attrib.get("value", "")
        segments = parse_outline_segments(val_str)
        if len(segments) >= 2:
            return segments[1][5]
        elif segments:
            return segments[0][5]
        return 0.0
    
    report_lines = []
    for static in root.findall(".//StaticComponent"):
        comp_elem = static.find("WorkpieceComponentName")
        if comp_elem is None:
            continue
        static_name = comp_elem.attrib.get("value", "").strip()
        static_val = get_static_value(static)
        
        dc_elems = static.findall("DeformableCompShortening")
        dc_info = []
        for dcs in dc_elems:
            dc_name_elem = dcs.find("DeformableComponentName")
            short_elem = dcs.find("ShorteningContour")
            if dc_name_elem is None or short_elem is None:
                continue
            dc_name = dc_name_elem.attrib.get("value", "").strip()
            dc_val = get_dc_value(short_elem)
            dc_info.append((dc_name, dc_val))
        dc_count = len(dc_info)
        dc_values_str = ", ".join(f"{name}={round(val,2)}" for name, val in dc_info)
        computed_dim = static_val + sum(val for _, val in dc_info)
        line = (f"{static_name}: static={round(static_val,6)}, DC count={dc_count}, "
                f"DC values: {dc_values_str}; Computed dims: {round(computed_dim,6)}")
        report_lines.append(line)
    return "\n".join(report_lines)

def main():
    try:
        df_zw = pd.read_excel("wyniki_zw_v3.xlsx")
        df_odcinki = pd.read_excel("wyniki_odcinki_v3.xlsx")
    except Exception as e:
        print("Błąd wczytywania plików Excel:", e)
        return
    
    df_test = df_zw.copy()
    computed_dimensions_list = []
    dc_shortening_list = []
    bending_angles_list = []
    grouped_dimensions_list = []
    grouped2_list = []
    
    for idx, row in df_test.iterrows():
        file_name = row["Nazwa pliku"]
        typ = str(row["Typ"]).strip().lower()
        if typ == "inside":
            computed_dim = compute_inside_dimensions(file_name, df_odcinki)
            computed_dimensions_list.append(computed_dim)
        else:
            computed_dimensions_list.append("")
        
        dc_val = compute_dc_shortening(file_name, df_odcinki)
        dc_shortening_list.append(dc_val)
        
        angles_val = compute_bending_angles_from_xml(file_name)
        bending_angles_list.append(angles_val)
        
        grouped_dims = compute_grouped_dimensions(file_name, df_odcinki)
        grouped_dimensions_list.append(grouped_dims)
        
        grouped2 = compute_grouped2_dimensions(file_name)
        grouped2_list.append(grouped2)
    
    df_test["Wymiary wewnętrzne (test)"] = computed_dimensions_list
    df_test["DC Shortening (test)"] = dc_shortening_list
    df_test["Kąty gięcia (test)"] = bending_angles_list
    df_test["Grouped Dimensions (test)"] = grouped_dimensions_list
    df_test["Grouped2"] = grouped2_list
    
    try:
        df_test.to_excel("TESTY.xlsx", index=False)
        print("Plik TESTY.xlsx został zapisany.")
    except Exception as e:
        print("Błąd zapisu pliku TESTY.xlsx:", e)

if __name__ == "__main__":
    main()
