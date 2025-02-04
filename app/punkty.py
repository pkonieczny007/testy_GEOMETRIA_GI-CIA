import os
import xml.etree.ElementTree as ET

def find_dld_file():
    """
    Znajdź pierwszy plik .dld w katalogu skryptu.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Katalog skryptu
    for file in os.listdir(script_dir):
        if file.endswith(".dld"):
            return os.path.join(script_dir, file)
    return None

def extract_points_from_dld(file_path):
    """
    Wyciągnij punkty z pliku .dld (zakładamy format XML).
    """
    points = []

    try:
        # Wczytaj plik XML
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Namespace XML
        namespaces = {'delem': 'http://www.delem.com/delem'}

        # StaticComponentHull
        for element in root.findall(".//delem:StaticComponentHull", namespaces):
            hull_value = element.attrib.get("value")
            if hull_value:
                points.append(("StaticComponentHull", hull_value))

        # ShorteningContour
        for element in root.findall(".//delem:ShorteningContour", namespaces):
            contour_value = element.attrib.get("value")
            if contour_value:
                points.append(("ShorteningContour", contour_value))

        # VDeformableComponentBendLine
        for element in root.findall(".//delem:VDeformableComponentBendLine", namespaces):
            bend_line_value = element.attrib.get("value")
            if bend_line_value:
                points.append(("VDeformableComponentBendLine", bend_line_value))

    except ET.ParseError as e:
        print(f"Błąd parsowania XML: {e}")
    except Exception as e:
        print(f"Inny błąd: {e}")

    return points

# Znajdź plik .dld w katalogu skryptu
dld_file = find_dld_file()

if dld_file:
    print(f"Znaleziono plik: {dld_file}")
    # Wyciągnij punkty
    points = extract_points_from_dld(dld_file)
    if points:
        for point_type, point_value in points:
            print(f"{point_type}: {point_value}")
    else:
        print("Nie znaleziono punktów w pliku.")
else:
    print("Nie znaleziono pliku .dld w katalogu skryptu.")
