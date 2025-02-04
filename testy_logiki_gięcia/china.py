import xml.etree.ElementTree as ET
import math

# Stałe
GRUBOSC = 2  # Grubość materiału w mm
KAT = 90  # Kąt gięcia w stopniach

# Funkcja do obliczania rozwinięcia
def oblicz_rozwinięcie(dlugosc_a, dlugosc_b, dlugosc_luku, kat, grubosc):
    # Przeliczenie kąta na radiany
    kat_rad = math.radians(kat)
    
    # Obliczenie współczynnika K (dla kąta 90 stopni i grubości 2mm, K ≈ 0.33)
    K = 0.33  # Wartość domyślna dla 90 stopni i grubości 2mm
    
    # Obliczenie rozwinięcia
    rozwinięcie = dlugosc_a + dlugosc_b + (dlugosc_luku * (math.pi / 2) * (grubosc + K))
    
    return rozwinięcie

# Funkcja do obliczania wymiarów zewnętrznych i wewnętrznych
def oblicz_wymiary(dlugosc_a, dlugosc_b, dlugosc_luku, kat, grubosc):
    # Wymiar zewnętrzny
    wymiar_zewnetrzny = dlugosc_a + dlugosc_b + dlugosc_luku
    
    # Wymiar wewnętrzny
    wymiar_wewnetrzny = wymiar_zewnetrzny - (2 * grubosc)
    
    return wymiar_zewnetrzny, wymiar_wewnetrzny

# Funkcja do odczytu danych z pliku .dld
def odczytaj_dane_z_pliku(sciezka_pliku):
    tree = ET.parse(sciezka_pliku)
    root = tree.getroot()
    
    # Wyszukanie odpowiednich elementów w pliku XML
    dlugosc_a = None
    dlugosc_b = None
    dlugosc_luku = None
    
    for elem in root.iter():
        if 'StaticComponentHull' in elem.tag:
            value = elem.get('value')
            if value:
                parts = value.split()
                # Filtruj tylko wartości numeryczne
                parts = [part for part in parts if part.replace('.', '').isdigit()]
                if len(parts) >= 8:
                    dlugosc_a = float(parts[2]) - float(parts[0])  # Obliczenie długości A
                    dlugosc_b = float(parts[6]) - float(parts[4])  # Obliczenie długości B
        elif 'VDeformableComponentHulls' in elem.tag:
            value = elem.get('value')
            if value:
                parts = value.split()
                # Filtruj tylko wartości numeryczne
                parts = [part for part in parts if part.replace('.', '').isdigit()]
                if len(parts) >= 6:
                    dlugosc_luku = float(parts[4]) - float(parts[2])  # Obliczenie długości łuku
    
    return dlugosc_a, dlugosc_b, dlugosc_luku

# Ścieżka do pliku .dld
sciezka_pliku = 'china.dld'

# Odczytanie danych z pliku
dlugosc_a, dlugosc_b, dlugosc_luku = odczytaj_dane_z_pliku(sciezka_pliku)

if dlugosc_a is not None and dlugosc_b is not None and dlugosc_luku is not None:
    print(f"Długość A: {dlugosc_a} mm")
    print(f"Długość B: {dlugosc_b} mm")
    print(f"Długość łuku: {dlugosc_luku} mm")
    
    # Obliczenie rozwinięcia
    rozwinięcie = oblicz_rozwinięcie(dlugosc_a, dlugosc_b, dlugosc_luku, KAT, GRUBOSC)
    print(f"Rozwinięcie: {rozwinięcie:.2f} mm")
    
    # Obliczenie wymiarów zewnętrznych i wewnętrznych
    wymiar_zewnetrzny, wymiar_wewnetrzny = oblicz_wymiary(dlugosc_a, dlugosc_b, dlugosc_luku, KAT, GRUBOSC)
    print(f"Wymiar zewnętrzny: {wymiar_zewnetrzny:.2f} mm")
    print(f"Wymiar wewnętrzny: {wymiar_wewnetrzny:.2f} mm")
else:
    print("Nie udało się odczytać wszystkich wymaganych danych z pliku.")
