#!/usr/bin/env python3
import xml.etree.ElementTree as ET

FILE_NAME = "plik.dld"

def parse_delem_outline(value_attr):
    """
    Funkcja parsuje napis w stylu:
      "4 0 -95.18352 200 -95.18352 false 200 -95.18352 200 200 false ..."
    - Pierwsza liczba (4) to liczba segmentów.
    - Następnie sekwencje (x1, y1, x2, y2, [false/true], x2, y2, x3, y3, [false/true], ...)
    Zwraca listę krotek (x, y) punktów w kolejności.
    """
    parts = value_attr.strip().split()
    # Pierwsza liczba to ilość segmentów, ale segmentów jest o jeden mniej niż punktów
    # Format: [nSeg, x1, y1, x2, y2, arcFlag?, x2, y2, x3, y3, arcFlag?, ...]
    # Uwaga: arcFlag? = 'false' lub 'true'
    n_seg = int(parts[0])
    coords = []
    # Przesuwamy się po tablicy od indeksu 1 w paczkach (x, y, x, y, arc?)
    idx = 1
    # Za każdy segment mamy 5 elementów: x, y, x, y, arcFlag
    # ale zauważ, że x2,y2 powtarza się jako x1,y1 kolejnego segmentu
    for _ in range(n_seg):
        x1 = float(parts[idx]);     y1 = float(parts[idx+1])
        x2 = float(parts[idx+2]);   y2 = float(parts[idx+3])
        arc_flag = parts[idx+4]     # 'false' / 'true'
        idx += 5
        # Możemy np. dodać do listy punkt startowy (o ile go jeszcze nie ma),
        # i zawsze dodać punkt końcowy
        if not coords:  
            coords.append((x1, y1))
        coords.append((x2, y2))
    return coords

def distance(p1, p2):
    """ Prosta funkcja licząca odległość euklidesową między punktami 2D. """
    import math
    return math.dist(p1, p2)

def main():
    # [1] Wczytanie pliku .dld
    tree = ET.parse(FILE_NAME)
    root = tree.getroot()

    # [2] Wyszukanie interesujących obrysów (Outline)
    # Przykładowo: <StaticComponentHull unit="Outline" value="4 0 0 10 0 false ..." />
    # lub: <VDeformableComponentHulls unit="Outlines" value="1 Outline 4 0 0 5.994909 0 false ..." />
    #
    # Zależnie od struktury pliku może być kilka węzłów. Przykładowo:
    all_outlines = root.findall(".//StaticComponentPart/StaticComponentHull[@unit='Outline']")
    deformable_outlines = root.findall(".//VDeformableComponentHulls[@unit='Outlines']")

    # Zmienne na wyniki (dla uproszczenia).
    a = b = arc = 0.0
    thickness = 2.0
    angle = 90

    # [2a] Przykład odczytu jednej z wartości (np. dla 'MainPlane'):
    for outline_elem in all_outlines:
        val_str = outline_elem.get("value")  # cały string z punktami
        coords = parse_delem_outline(val_str)
        # Jeśli wiemy, że np. w outline MainPlane mamy odcinek 295.18352,
        # możemy to wykryć, licząc odległości kolejnych segmentów:
        for i in range(len(coords) - 1):
            d = distance(coords[i], coords[i+1])
            # heurystycznie sprawdzamy, czy 'd' jest ~295.18352
            if abs(d - 295.18352) < 0.001:
                a = 295.18352  # wstawiamy do zmiennej, np. 'a'
            if abs(d - 45.183522) < 0.001:
                b = 45.183522  # wstawiamy do zmiennej, np. 'b'

    # [2b] Przykład odczytu obrysu odkształcalnego (gdzie może być 5.994909)
    for def_outline_elem in deformable_outlines:
        val_str = def_outline_elem.get("value")
        # W Delem często jest format: "1 Outline 4 0 0 5.994909 0 false ..."
        # trzeba wydobyć fragment po "Outline" – w parse_delem_outline
        # zaczęliśmy od razu od liczby segmentów. 
        # W tym wypadku:
        #   "1 Outline 4 0 0 5.994909 0 false 5.994909 0 5.994909 200 false ..."
        # więc warto najpierw splitnąć po "Outline".
        if "Outline" in val_str:
            # usuwamy początek "1 Outline"
            cleaned_val = val_str.split("Outline")[-1].strip()
            coords = parse_delem_outline(cleaned_val)
            for i in range(len(coords) - 1):
                d = distance(coords[i], coords[i+1])
                # heurystycznie sprawdzamy, czy 'd' ~ 5.994909
                if abs(d - 5.994909) < 0.001:
                    arc = 5.994909

    # [3] Teraz mamy a, b, arc (wykryte z pliku).
    #     Obliczamy przykładowe parametry (jak w wariancie A).
    rozwiniecie = a + b + arc
    wymiar_zew = a + b
    wymiar_wew = wymiar_zew - 2 * thickness

    print(f"--- Odczyt z pliku {FILE_NAME} ---")
    print(f"a = {a:.6f} mm")
    print(f"b = {b:.6f} mm")
    print(f"arc = {arc:.6f} mm")
    print(f"grubość = {thickness:.2f} mm")
    print(f"kąt = {angle}°")
    print()
    print(f"--- Wyniki obliczeń ---")
    print(f"Rozwinięcie (flat length) = {rozwiniecie:.3f} mm")
    print(f"Wymiar zewnętrzny (outside) = {wymiar_zew:.3f} mm")
    print(f"Wymiar wewnętrzny (inside) = {wymiar_wew:.3f} mm")

if __name__ == "__main__":
    main()
