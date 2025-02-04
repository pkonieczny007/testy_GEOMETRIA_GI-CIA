#!/usr/bin/env python3 
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import os
import re
import glob
import sys
import string
import math

def parse_outline_value(value_str):
    tokens = value_str.split()
    numeric_vals = []
    for t in tokens:
        if t.lower() in ['outline', 'true', 'false']:
            continue
        try:
            numeric_vals.append(float(t))
        except ValueError:
            pass
    if not numeric_vals:
        return []
    segment_count = int(numeric_vals[0])
    coords = numeric_vals[1:]
    points = []
    for i in range(0, len(coords), 2):
        if i + 1 < len(coords):
            x = coords[i]
            y = coords[i + 1]
            points.append((x, y))
    return points

def bounding_box(coords):
    if not coords:
        return 0, 0, 0, 0
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    return min(xs), max(xs), min(ys), max(ys)

def width_height_from_box(xmin, xmax, ymin, ymax):
    return abs(xmax - xmin), abs(ymax - ymin)

def normalize_angle(angle_deg):
    if angle_deg > 180:
        return angle_deg - 360
    return angle_deg

def process_file(filename, output_dir):
    if not os.path.isfile(filename):
        print(f"Brak pliku: {filename}")
        return

    try:
        tree = ET.parse(filename)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Błąd parsowania pliku {filename}: {e}")
        return

    dimension_type = None
    thickness_val = 0.0
    radius_val = 0.0
    mainplane_value = None
    mainplane_name = None
    sc_components = {}
    bends_info = []

    for elem in root.iter():
        tag_name = elem.tag.lower()

        if tag_name.endswith("workpiecedimensions"):
            dimension_type = elem.get("value", "")
        if tag_name.endswith("workpiecethickness"):
            try:
                thickness_val = float(elem.get("value", "0"))
            except ValueError:
                thickness_val = 0.0
        if tag_name.endswith("preferredinnerradius"):
            try:
                radius_val = float(elem.get("value", "0"))
            except ValueError:
                radius_val = 0.0

        if tag_name.endswith("workpiecemap"):
            mp_elem = elem.find("./MainPlaneName")
            if mp_elem is not None:
                mainplane_name = mp_elem.get("value", "")

        if tag_name.endswith("staticcomponent"):
            wp_name = elem.find("./WorkpieceComponentName")
            if wp_name is not None:
                comp_name = wp_name.get("value", "")
                hull_elem = elem.find("./StaticComponentPart/StaticComponentHull")
                if hull_elem is not None:
                    val_str = hull_elem.get("value", "")
                    coords = parse_outline_value(val_str)
                    box = bounding_box(coords)
                    width, height = width_height_from_box(*box)
                    value_min = min(width, height)

                    if comp_name == mainplane_name:
                        mainplane_value = value_min
                    elif re.match(r'^SC\d+', comp_name):
                        sc_components[comp_name] = value_min

        if tag_name.endswith("vdeformablecomponent"):
            wp_name = elem.find("./WorkpieceComponentName")
            if wp_name is not None:
                comp_name = wp_name.get("value", "")
                if re.match(r'^DC\d+', comp_name):
                    hulls_elem = elem.find("./VDeformableComponentHulls")
                    arc_value = 0.0
                    if hulls_elem is not None:
                        val_str = hulls_elem.get("value", "")
                        coords = parse_outline_value(val_str)
                        box = bounding_box(coords)
                        width, height = width_height_from_box(*box)
                        arc_value = min(width, height)

                    angle_elem = elem.find("./VDeformableComponentAngle")
                    angle_after = 0.0
                    if angle_elem is not None:
                        try:
                            angle_after = float(angle_elem.get("value", "0"))
                        except ValueError:
                            angle_after = 0.0

                    angle_normalized = normalize_angle(angle_after)
                    bends_info.append({
                        "name": comp_name,
                        "arc": arc_value,
                        "angle_raw": angle_after,
                        "angle_norm": angle_normalized
                    })

    output_filename = os.path.join(output_dir, f"wynik_{os.path.splitext(os.path.basename(filename))[0]}.txt")
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(f"=== Wyniki dla pliku: {os.path.basename(filename)} ===\n")
        f.write(f"=== Odczyt z pliku DLD (metoda bounding box) ===\n")
        f.write(f"WorkpieceDimensions = {dimension_type}\n")
        f.write(f"Grubość             = {thickness_val} mm\n")
        f.write(f"Promień wewn.       = {radius_val} mm\n")
        f.write("-------------------------------------------\n")
        f.write(f"[{mainplane_name}] => a={mainplane_value:.6f}\n")
        for sc_name, val in sc_components.items():
            f.write(f"[{sc_name}] => {val:.6f}\n")
        for binfo in bends_info:
            f.write(f"[{binfo['name']}] => łuk={binfo['arc']:.6f}\n")
        f.write("-------------------------------------------\n")
        f.write(f"kąty\n")
        for binfo in bends_info:
            f.write(f"{int(round(binfo['angle_norm']))}\n")
    print(f"Wyniki zapisano do pliku: {output_filename}")

def main():
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = os.getcwd()

    if not os.path.isdir(folder):
        print(f"Podany folder nie istnieje: {folder}")
        return

    output_dir = os.path.join(folder, "wyniki1")
    os.makedirs(output_dir, exist_ok=True)

    pattern = os.path.join(folder, "*.dld")
    files = glob.glob(pattern)

    if not files:
        print(f"Nie znaleziono żadnych plików .dld w folderze: {folder}")
        return

    print(f"Znaleziono {len(files)} plików .dld w folderze: {folder}\n")

    for file in files:
        process_file(file, output_dir)

    print("\nPrzetwarzanie zakończone.")

if __name__ == "__main__":
    main()
