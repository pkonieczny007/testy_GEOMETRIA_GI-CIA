import os
import xml.etree.ElementTree as ET

def parse_dld_file(file_path):
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Inicjalizacja zmiennych
        workpiece_name = None
        material_thickness = None
        preferred_inner_radius = None
        blank_length = None
        segments = []

        # Parsowanie danych z pliku
        for workpiece in root.iter('Workpiece'):
            workpiece_name = workpiece.find('WorkpieceName').get('value')
            material_thickness = workpiece.find('WorkpieceThickness').get('value')

        for v_deformable_component in root.iter('VDeformableComponent'):
            preferred_inner_radius = v_deformable_component.find('PreferredInnerRadius').get('value')

        for static_component in root.iter('StaticComponent'):
            hull = static_component.find('StaticComponentPart').find('StaticComponentHull')
            if hull is not None:
                outline_values = hull.get('value').split()
                points = []

                # Filtrowanie i przetwarzanie punktów
                for i in range(0, len(outline_values), 3):
                    try:
                        x = float(outline_values[i])
                        y = float(outline_values[i + 1])
                        points.append((x, y))
                    except ValueError:
                        continue

                # Obliczanie długości segmentów
                for j in range(len(points) - 1):
                    x1, y1 = points[j]
                    x2, y2 = points[j + 1]
                    segment_length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
                    segments.append(segment_length)

        for bend_sequence in root.iter('BendSequence'):
            blank_length = bend_sequence.find('BlankLength').get('value')

        # Wyświetlanie wyników
        print(f"Nazwa produktu: {workpiece_name}")
        print(f"Grubość materiału: {material_thickness} mm")
        print(f"Preferowany promień wewnętrzny: {preferred_inner_radius} mm")
        print(f"Rozwinięcie (długość blachy): {blank_length} mm")
        print("Długości segmentów i kąty:")
        for i in range(len(segments)):
            angle = 90 if i == 0 else None  # Zakładamy kąt 90 stopni dla pierwszego segmentu
            print(f"  Segment {i + 1}: Długość = {segments[i]:.2f} mm", end="")
            if angle:
                print(f", Kąt: {angle} stopni")
            else:
                print()

    except ET.ParseError as e:
        print(f"Błąd parsowania pliku XML: {e}")
    except FileNotFoundError:
        print(f"Plik {file_path} nie został znaleziony.")
    except Exception as e:
        print(f"Wystąpił nieoczekiwany błąd: {e}")

if __name__ == "__main__":
    # Pobranie ścieżki do katalogu, w którym znajduje się skrypt
    script_directory = os.path.dirname(os.path.abspath(__file__))

    # Iteracja po wszystkich plikach w katalogu
    for filename in os.listdir(script_directory):
        if filename.endswith(".dld"):
            file_path = os.path.join(script_directory, filename)
            print(f"\nPrzetwarzanie pliku: {filename}")
            parse_dld_file(file_path)
