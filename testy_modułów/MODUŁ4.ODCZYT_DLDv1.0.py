import os
import pandas as pd
import xml.etree.ElementTree as ET
import math

# -------------------
# Konfiguracja ścieżek
# -------------------
# Katalog, w którym znajdują się pliki .dld:
katalog_plik_dld = r"C:\PYTHON\PROJEKT_GEOMETRIA_GIĘCIA\plik_dld"

# Ścieżka do pliku wynik.xlsx (wygenerowanego przez MODUŁ1.ODCZYT_WYKAZUv1.2.py):
sciezka_wynik = os.path.join(os.getcwd(), "wynik.xlsx")

# -------------------
# Funkcje pomocnicze
# -------------------

def read_dld_data(filepath):
    """
    Odczytuje podstawowe dane z pliku .dld (XML).
    Zwraca słownik z interesującymi nas wartościami:
    - thickness
    - inner_radius
    - angles (lista kątów, w przykładzie tylko 1 kąt)
    - a_out, b_out, a_in, b_in
    - inne dane do ewentualnego rozbudowania
    """

    tree = ET.parse(filepath)
    root = tree.getroot()

    # Grubość arkusza
    thickness_element = root.find(".//WorkpieceThickness")
    if thickness_element is not None:
        thickness = float(thickness_element.get("value", "0"))
    else:
        thickness = 0.0

    # Preferowany promień wewnętrzny
    radius_element = root.find(".//PreferredInnerRadius")
    if radius_element is not None:
        inner_radius = float(radius_element.get("value", "0"))
    else:
        inner_radius = 0.0

    # Kąt (w przykładzie odczytujemy tylko 1. Jeśli jest wiele, można rozwinąć logikę)
    angle_element = root.find(".//VDeformableComponentAngle")
    if angle_element is not None:
        angle = float(angle_element.get("value", "0"))
    else:
        angle = 0.0

    # ---------------------------
    # Poniższy fragment jest mocno zależny od struktury .dld:
    # Odczytujemy np. dwa "StaticComponent" (a, b).
    # Jeśli plik ma więcej segmentów, trzeba rozszerzyć wyszukiwanie.
    # ---------------------------

    # Przykład: odczyt wymiaru a (zewn.)
    # main_plane_path to ścieżka Xpath, którą pokazywałeś w swoim skrypcie
    main_plane_elem = root.find(".//StaticComponent[WorkpieceComponentName[@value='MainPlane']]/StaticComponentPart/StaticComponentHull")
    if main_plane_elem is not None:
        main_plane_value = main_plane_elem.get("value", "")
        # Zwykle w "value" jest ciąg znaków np. "x y z a b c ..."
        # Zakładamy, że 3-cim indeksem (index=2) jest wymiar a (zewn.)
        parts = main_plane_value.split()
        try:
            external_a = float(parts[2])
        except (ValueError, IndexError):
            external_a = 0.0
    else:
        external_a = 0.0

    # Przykład: odczyt wymiaru b (zewn.)
    sc00_elem = root.find(".//StaticComponent[WorkpieceComponentName[@value='SC00']]/StaticComponentPart/StaticComponentHull")
    if sc00_elem is not None:
        sc00_value = sc00_elem.get("value", "")
        parts_b = sc00_value.split()
        # Zakładamy, że 7-mym indeksem (index=6) jest wymiar b (zewn.)
        try:
            external_b = float(parts_b[6])
        except (ValueError, IndexError):
            external_b = 0.0
    else:
        external_b = 0.0

    # Funkcje pomocnicze do obliczeń out/in
    def calculate_out_dimension(external_dim, offset, angle):
        """ x_out = x_zewn + offset * tan((180 - kąt)/2) """
        angle_rad = math.radians((180 - angle) / 2)
        return round(external_dim + offset * math.tan(angle_rad), 2)

    def calculate_in_dimension(external_dim, inner_radius, thickness, angle):
        """ x_in = x_zewn + (łuk po neutralnej)/2, gdzie:
            łuk = (R_wewn + grubość/2) * (pi * kąt/180)
        """
        neutral_arc_length = (inner_radius + thickness/2) * math.radians(angle)
        return round(external_dim + neutral_arc_length/2, 2)

    # offset = (r + g)
    offset = inner_radius + thickness

    # Obliczenia OUT
    a_out = calculate_out_dimension(external_a, offset, angle)
    b_out = calculate_out_dimension(external_b, offset, angle)

    # Obliczenia IN
    a_in = calculate_in_dimension(external_a, inner_radius, thickness, angle)
    b_in = calculate_in_dimension(external_b, inner_radius, thickness, angle)

    # Przykładowe wyliczenie "Rozwinięcia" (np. suma a_in + b_in, do modyfikacji wg potrzeb)
    rozwiniecie = round(a_in + b_in, 2)

    # Zwracamy w słowniku kluczowe dane
    return {
        "thickness": thickness,
        "inner_radius": inner_radius,
        "angles": [angle],  # wstawiamy listę, gdybyśmy chcieli rozbudować
        "external_a": external_a,
        "external_b": external_b,
        "a_out": a_out,
        "b_out": b_out,
        "a_in": a_in,
        "b_in": b_in,
        "rozwiniecie": rozwiniecie,
    }

# -------------------
# Główny skrypt
# -------------------

def main():
    # Wczytujemy plik wynik.xlsx
    if not os.path.isfile(sciezka_wynik):
        print(f"Nie znaleziono pliku Excel: {sciezka_wynik}")
        return

    df = pd.read_excel(sciezka_wynik)

    # Upewniamy się, że mamy w DataFrame kolumny docelowe
    # (jeśli nie ma – tworzymy puste)
    kolumny_docelowe = [
        "dane_plik_dld",
        "Długości a/b/c/d.../n",
        "Kąty",
        "WorkpieceDimensions - Outside, Inside",
        "Grubość",
        "Promień wewn.",
        "Rozwinięcie"
    ]
    for kol in kolumny_docelowe:
        if kol not in df.columns:
            df[kol] = ""

    # Iterujemy po wierszach, sprawdzając kolumnę plik_dld
    for idx, row in df.iterrows():
        plik_dld_bez_ext = str(row["plik_dld"]).strip()

        # Jeśli brak nazwy pliku, pomijamy
        if not plik_dld_bez_ext or plik_dld_bez_ext.lower() in ["nan", "none"]:
            continue

        # Składamy pełną ścieżkę do pliku .dld
        dld_filepath = os.path.join(katalog_plik_dld, plik_dld_bez_ext + ".dld")

        if os.path.isfile(dld_filepath):
            try:
                # Parsujemy plik .dld
                data = read_dld_data(dld_filepath)

                # Uzupełniamy kolumny w DataFrame
                # 1) dane_plik_dld – np. krótkie podsumowanie
                df.at[idx, "dane_plik_dld"] = (
                    f"OK: {plik_dld_bez_ext}.dld "
                    f"(g={data['thickness']}, r={data['inner_radius']}, kąt={data['angles']})"
                )

                # 2) Długości a/b/c/d.../n (tutaj przykład a_out, b_out, a_in, b_in)
                dlugosci_txt = (
                    f"a_out={data['a_out']} mm; b_out={data['b_out']} mm; "
                    f"a_in={data['a_in']} mm; b_in={data['b_in']} mm"
                )
                df.at[idx, "Długości a/b/c/d.../n"] = dlugosci_txt

                # 3) Kąty
                katy_txt = ", ".join([str(k) for k in data["angles"]])
                df.at[idx, "Kąty"] = katy_txt

                # 4) WorkpieceDimensions - Outside, Inside
                wi_txt = (
                    f"Outside: a={data['external_a']:.2f}, b={data['external_b']:.2f}; "
                    f"Inside: a_in={data['a_in']}, b_in={data['b_in']}"
                )
                df.at[idx, "WorkpieceDimensions - Outside, Inside"] = wi_txt

                # 5) Grubość
                df.at[idx, "Grubość"] = data["thickness"]

                # 6) Promień wewn.
                df.at[idx, "Promień wewn."] = data["inner_radius"]

                # 7) Rozwinięcie
                df.at[idx, "Rozwinięcie"] = data["rozwiniecie"]

            except ET.ParseError as e:
                df.at[idx, "dane_plik_dld"] = f"Błąd parsowania XML: {e}"
            except Exception as ex:
                df.at[idx, "dane_plik_dld"] = f"Błąd: {ex}"
        else:
            # Jeśli nie ma pliku .dld, wpisujemy informację
            df.at[idx, "dane_plik_dld"] = f"Brak pliku: {plik_dld_bez_ext}.dld"

    # Zapisujemy zaktualizowany plik ponownie do wynik.xlsx
    df.to_excel(sciezka_wynik, index=False)
    print(f"Zaktualizowano dane w pliku: {sciezka_wynik}")


if __name__ == "__main__":
    main()
