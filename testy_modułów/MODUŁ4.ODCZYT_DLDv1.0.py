import os
import math
import pandas as pd
import xml.etree.ElementTree as ET

def calculate_out_dimension(external_dim, offset, angle):
    """
    Oblicza wymiar OUT:
    x_out = x_zewn + offset * tan((180 - kąt) / 2).
    """
    angle_rad = math.radians((180 - angle) / 2.0)
    return round(external_dim + offset * math.tan(angle_rad), 2)

def calculate_in_dimension(external_dim, inner_radius, thickness, angle):
    """
    Oblicza wymiar IN:
    x_in = x_zewn + (łuk po neutralnej) / 2
    gdzie łuk po neutralnej = (R_wewn + grubość/2) * (π * kąt / 180).
    """
    neutral_arc_length = (inner_radius + thickness / 2.0) * math.radians(angle)
    return round(external_dim + neutral_arc_length / 2.0, 2)

def parse_dld_file(dld_path):
    """
    Odczytuje i analizuje plik .dld (XML), zwracając słownik z wybranymi danymi
    lub None, jeśli wystąpią błędy.
    """

    if not os.path.isfile(dld_path):
        return None

    try:
        tree = ET.parse(dld_path)
        root = tree.getroot()
    except ET.ParseError:
        return None

    # Odczyt grubosci
    thickness_el = root.find(".//WorkpieceThickness")
    thickness = float(thickness_el.get("value", "0")) if thickness_el is not None else 0.0

    # Odczyt promienia wewnetrznego
    inner_radius_el = root.find(".//PreferredInnerRadius")
    inner_radius = float(inner_radius_el.get("value", "0")) if inner_radius_el is not None else 0.0

    # Odczyt kąta
    angle_el = root.find(".//VDeformableComponentAngle")
    angle = float(angle_el.get("value", "0")) if angle_el is not None else 0.0

    # Szukamy "StaticComponent" -> "WorkpieceComponentName"
    a_zewn = None
    b_zewn = None

    static_components = root.findall(".//StaticComponent")
    for sc in static_components:
        wcn = sc.find("WorkpieceComponentName")
        if wcn is not None:
            value = wcn.get("value", "").strip()
            # MainPlane -> a_zewn
            if value == "MainPlane":
                mp_el = sc.find("./StaticComponentPart/StaticComponentHull")
                if mp_el is not None:
                    hull_value = mp_el.get("value", "")
                    hull_parts = hull_value.split()
                    if len(hull_parts) > 2:
                        a_zewn = float(hull_parts[2])
            # SC00 -> b_zewn
            elif value == "SC00":
                sc00_el = sc.find("./StaticComponentPart/StaticComponentHull")
                if sc00_el is not None:
                    hull_value = sc00_el.get("value", "")
                    hull_parts = hull_value.split()
                    if len(hull_parts) > 6:
                        b_zewn = float(hull_parts[6])

    if a_zewn is None or b_zewn is None:
        # Brak kluczowych danych
        return None

    offset = inner_radius + thickness
    a_out = calculate_out_dimension(a_zewn, offset, angle)
    b_out = calculate_out_dimension(b_zewn, offset, angle)
    a_in = calculate_in_dimension(a_zewn, inner_radius, thickness, angle)
    b_in = calculate_in_dimension(b_zewn, inner_radius, thickness, angle)

    neutral_arc_length = (inner_radius + thickness / 2.0) * math.radians(angle)
    rozwiniecie = round(neutral_arc_length, 2)

    return {
        "grubosc": thickness,
        "promien_wewn": inner_radius,
        "kat": angle,
        "a_zewn": a_zewn,
        "b_zewn": b_zewn,
        "a_out": a_out,
        "b_out": b_out,
        "a_in": a_in,
        "b_in": b_in,
        "rozwiniecie": rozwiniecie,
    }

def main():
    # Wczytanie pliku wynik.xlsx
    sciezka_we = os.path.join(os.getcwd(), "wynik.xlsx")
    if not os.path.isfile(sciezka_we):
        print(f"Nie znaleziono pliku wejściowego: {sciezka_we}")
        return

    df = pd.read_excel(sciezka_we)

    # Upewniamy się, że kolumny istnieją i mają typ 'object' (tekstowy)
    nowe_kolumny = [
        "dane_plik_dld",
        "Długości a/b/c/d.../n",
        "Kąty",
        "WorkpieceDimensions - Outside, Inside",
        "Grubość",
        "Promień wewn.",
        "Rozwinięcie",
    ]
    for kol in nowe_kolumny:
        if kol not in df.columns:
            df[kol] = ""
        # Wymuszamy typ 'object' (co w Pandas zwykle pozwala na przechowywanie dowolnych stringów)
        df[kol] = df[kol].astype("object")

    folder_dld = os.path.join(os.getcwd(), "plik_dld")
    if not os.path.isdir(folder_dld):
        print(f"Brak folderu plik_dld: {folder_dld}")
        return

    # (opcjonalnie) folder tmp na pliki tekstowe
    folder_tmp = os.path.join(folder_dld, "tmp")
    if not os.path.isdir(folder_tmp):
        os.makedirs(folder_tmp)

    for idx, row in df.iterrows():
        plik_dld_nazwa = row.get("plik_dld", "")

        # Pomijamy, jeśli puste lub NaN
        if pd.isna(plik_dld_nazwa):
            continue
        plik_dld_nazwa = str(plik_dld_nazwa).strip()
        if not plik_dld_nazwa:
            continue

        # Dodaj rozszerzenie .dld, jeśli trzeba
        if not plik_dld_nazwa.lower().endswith(".dld"):
            plik_dld_nazwa += ".dld"

        sciezka_dld = os.path.join(folder_dld, plik_dld_nazwa)
        if not os.path.isfile(sciezka_dld):
            # Jeśli nie ma takiego pliku, zapisz info i przejdź dalej
            try:
                df.at[idx, "dane_plik_dld"] = f"Brak pliku: {plik_dld_nazwa}"
            except Exception as e:
                # Jeśli z jakiegoś powodu wystąpi błąd zapisu, pomiń
                print(f"Błąd przy zapisie 'Brak pliku': {e}")
            continue

        dane_dld = parse_dld_file(sciezka_dld)
        if dane_dld is None:
            try:
                df.at[idx, "dane_plik_dld"] = f"Błąd parsowania / brak danych: {plik_dld_nazwa}"
            except Exception as e:
                print(f"Błąd przy zapisie 'Błąd parsowania': {e}")
            continue

        # Spróbujmy wypełnić kolumny
        try:
            opis_txt = (
                f"Plik: {plik_dld_nazwa}, "
                f"grubość={dane_dld['grubosc']} mm, "
                f"promień_wewn={dane_dld['promien_wewn']} mm, "
                f"kąt={dane_dld['kat']} st."
            )
            df.at[idx, "dane_plik_dld"] = opis_txt

            dlugosci_txt = (
                f"a_zewn={dane_dld['a_zewn']}, a_in={dane_dld['a_in']}, a_out={dane_dld['a_out']}; "
                f"b_zewn={dane_dld['b_zewn']}, b_in={dane_dld['b_in']}, b_out={dane_dld['b_out']}"
            )
            df.at[idx, "Długości a/b/c/d.../n"] = dlugosci_txt
            df.at[idx, "Kąty"] = str(dane_dld["kat"])
            df.at[idx, "WorkpieceDimensions - Outside, Inside"] = (
                f"Outside(a,b)=({dane_dld['a_out']},{dane_dld['b_out']}), "
                f"Inside(a,b)=({dane_dld['a_in']},{dane_dld['b_in']})"
            )
            df.at[idx, "Grubość"] = str(dane_dld["grubosc"])  # zapis jako tekst
            df.at[idx, "Promień wewn."] = str(dane_dld["promien_wewn"])
            df.at[idx, "Rozwinięcie"] = str(dane_dld["rozwiniecie"])

            # (opcjonalnie) plik tekstowy z danymi
            nazwa_txt = os.path.splitext(plik_dld_nazwa)[0] + ".txt"
            sciezka_txt = os.path.join(folder_tmp, nazwa_txt)
            with open(sciezka_txt, "w", encoding="utf-8") as f:
                f.write("=== DANE ODCZYTANE Z PLIKU DLD ===\n")
                f.write(f"Nazwa pliku DLD: {plik_dld_nazwa}\n")
                f.write(f"Grubość: {dane_dld['grubosc']} mm\n")
                f.write(f"Promień wewn.: {dane_dld['promien_wewn']} mm\n")
                f.write(f"Kąt: {dane_dld['kat']} st.\n")
                f.write("------------------------------------\n")
                f.write(f"a (zewn.) = {dane_dld['a_zewn']} mm\n")
                f.write(f"b (zewn.) = {dane_dld['b_zewn']} mm\n")
                f.write("------------------------------------\n")
                f.write(f"a (out) = {dane_dld['a_out']} mm\n")
                f.write(f"b (out) = {dane_dld['b_out']} mm\n")
                f.write("-----\n")
                f.write(f"a (in)  = {dane_dld['a_in']} mm\n")
                f.write(f"b (in)  = {dane_dld['b_in']} mm\n")
                f.write("-----\n")
                f.write(f"Rozwinięcie (łuk po neutralnej) = {dane_dld['rozwiniecie']} mm\n")

        except Exception as e:
            # Jeśli wystąpił błąd przy przypisywaniu kolumn, zapiszmy go w 'dane_plik_dld' i idźmy dalej
            df.at[idx, "dane_plik_dld"] = f"Wystąpił błąd zapisu danych: {e}"
            continue

    # Zapis do pliku końcowego
    sciezka_wy = os.path.join(os.getcwd(), "wynik_dane.xlsx")
    df.to_excel(sciezka_wy, index=False)
    print(f"Zakończono. Wyniki w pliku: {sciezka_wy}")

if __name__ == "__main__":
    main()
