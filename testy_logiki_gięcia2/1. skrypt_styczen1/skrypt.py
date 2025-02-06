import xml.etree.ElementTree as ET
import math

def extract_bend_data(filename):
    """
    Wczytuje plik XML i wyciąga dane potrzebne do obliczenia długości rozwinięcia (prostki):
      - grubość blachy,
      - kąt gięcia (w stopniach),
      - promień wewnętrzny (PreferredInnerRadius),
      - długość odcinka prostego (wyznaczaną na podstawie współrzędnych BendLine).
    """
    tree = ET.parse(filename)
    root = tree.getroot()
    
    # Wyciągamy grubość blachy
    thickness_elem = root.find(".//WorkpieceThickness")
    thickness = float(thickness_elem.attrib["value"])
    
    # Wyciągamy kąt gięcia (Degrees) z elementu VDeformableComponentAngle
    angle_elem = root.find(".//VDeformableComponentAngle")
    bend_angle = float(angle_elem.attrib["value"])
    
    # Wyciągamy preferowany promień wewnętrzny gięcia
    radius_elem = root.find(".//PreferredInnerRadius")
    inner_radius = float(radius_elem.attrib["value"])
    
    # Wyciągamy współrzędne linii gięcia (BendLine)
    # Przykładowa wartość: "1 Line 2.997455 0 2.997455 200 false"
    bend_line_elem = root.find(".//VDeformableComponentBendLine")
    bend_line_value = bend_line_elem.attrib["value"]
    tokens = bend_line_value.split()
    # Zakładamy format: [liczba, "Line", x1, y1, x2, y2, ...]
    x1 = float(tokens[2])
    y1 = float(tokens[3])
    x2 = float(tokens[4])
    y2 = float(tokens[5])
    # Obliczamy długość odcinka prostego (np. linia gięcia)
    straight_length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    return thickness, bend_angle, inner_radius, straight_length

def compute_developed_length(thickness, bend_angle, inner_radius, straight_length):
    """
    Oblicza:
      - promień neutralny (przyjmując, że włókno obojętne znajduje się w połowie grubości),
      - długość łuku gięcia,
      - oraz całkowitą długość rozwinięcia (prostkę) jako sumę:
          [długość odcinka prostego] + [długość łuku gięcia].
    """
    # Obliczamy promień neutralny: wewnętrzny + (grubość/2)
    neutral_radius = inner_radius + thickness / 2
    
    # Przeliczamy kąt z stopni na radiany
    bend_angle_rad = math.radians(bend_angle)
    
    # Długość łuku gięcia
    arc_length = bend_angle_rad * neutral_radius
    
    # Całkowita długość rozwinięcia (prostka)
    developed_length = straight_length + arc_length
    
    return neutral_radius, arc_length, developed_length

if __name__ == "__main__":
    # Nazwa pliku XML – zmień na odpowiednią, jeśli plik ma inną nazwę
    filename = "prd.60x30.dld"
    
    try:
        # Wyciągamy dane z pliku
        thickness, bend_angle, inner_radius, straight_length = extract_bend_data(filename)
        
        # Obliczamy rozwinięcie (prostkę)
        neutral_radius, arc_length, developed_length = compute_developed_length(thickness, bend_angle, inner_radius, straight_length)
        
        # Wyświetlamy wyniki
        print("Dane wczytane z pliku:")
        print(f"  Grubość blachy: {thickness} mm")
        print(f"  Kąt gięcia: {bend_angle}°")
        print(f"  Promień wewnętrzny: {inner_radius} mm")
        print(f"  Długość odcinka prostego (BendLine): {straight_length:.3f} mm")
        print()
        print("Obliczenia:")
        print(f"  Promień neutralny: {neutral_radius:.3f} mm")
        print(f"  Długość łuku gięcia: {arc_length:.3f} mm")
        print(f"  Całkowita długość rozwinięcia (prostka): {developed_length:.3f} mm")
    
    except Exception as e:
        print("Wystąpił błąd podczas przetwarzania pliku XML:", e)
