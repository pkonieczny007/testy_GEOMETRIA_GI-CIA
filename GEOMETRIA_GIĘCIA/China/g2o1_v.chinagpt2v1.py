import xml.etree.ElementTree as ET
import os
import re
import glob
import sys
import string
import math

def calculate_out_dimension(external_dim, offset, angle):
    """
    Oblicza długość zewnętrzną (out) wg wzoru:
    x_out = x_zewn + offset * tan((180 - kąt) / 2)
    """
    angle_rad = math.radians((180 - angle) / 2)
    return round(external_dim + offset * math.tan(angle_rad))

def calculate_in_dimension(external_dim, inner_radius, thickness, angle):
    """
    Oblicza długość wewnętrzną (in) wg wzoru:
    x_in = x_zewn + (łuk po neutralnej) / 2
    gdzie łuk po neutralnej = (R_wewn + 1/2 * grubość) * (pi * kąt / 180)
    """
    neutral_arc_length = (inner_radius + thickness / 2) * math.radians(angle)
    return round(external_dim + neutral_arc_length / 2)

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

    # Pobranie wartości grubości i promienia wewnętrznego
    thickness = float(root.find(".//WorkpieceThickness").get("value", "0"))
    inner_radius = float(root.find(".//PreferredInnerRadius").get("value", "0"))

    # Pobranie wartości kąta
    angle = float(root.find(".//VDeformableComponentAngle").get("value", "0"))

    # Pobranie offsetu (r+g)
    offset = inner_radius + thickness

    # Pobranie wymiarów z pliku
    external_a = float(root.find(".//StaticComponent[WorkpieceComponentName[@value='MainPlane']]/StaticComponentPart/StaticComponentHull").get("value", "").split()[2])
    external_b = float(root.find(".//StaticComponent[WorkpieceComponentName[@value='SC00']]/StaticComponentPart/StaticComponentHull").get("value", "").split()[6])

    # Obliczenia wymiarów OUT
    a_out = calculate_out_dimension(external_a, offset, angle)
    b_out = calculate_out_dimension(external_b, offset, angle)

    # Obliczenia wymiarów IN
    a_in = calculate_in_dimension(external_a, inner_radius, thickness, angle)
    b_in = calculate_in_dimension(external_b, inner_radius, thickness, angle)

    # Wyniki
    print(f"=== Wyniki dla pliku: {os.path.basename(filename)} ===")
    print(f"Grubość             = {thickness} mm")
    print(f"Promień wewn.       = {inner_radius} mm")
    print("-------------------------------------------")
    print(f"a (zewn.) = {external_a:.6f} mm")
    print(f"b (zewn.) = {external_b:.6f} mm")
    print("-------------------------------------------")
    print(f"a (out) = {a_out}")
    print(f"b (out) = {b_out}")
    print("-----")
    print(f"a (in) = {a_in}")
    print(f"b (in) = {b_in}")
    print("-----")
    print(f"kąty")
    print(f"{int(angle)}")


def main():
    # Folder wejściowy
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = os.getcwd()

    if not os.path.isdir(folder):
        print(f"Podany folder nie istnieje: {folder}")
        return

    # Przetwarzanie plików
    pattern = os.path.join(folder, "*.dld")
    files = glob.glob(pattern)

    if not files:
        print(f"Nie znaleziono plików .dld w folderze: {folder}")
        return

    for file in files:
        process_file(file, folder)

if __name__ == "__main__":
    main()
