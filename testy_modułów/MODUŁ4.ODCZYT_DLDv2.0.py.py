import os
import math
import pandas as pd
import xml.etree.ElementTree as ET

# --------------- Fragmenty zapożyczone z kod_testowy.py ---------------

def normalize_angle(angle_deg):
    """Normalizuje kąt do zakresu [-180, 180]."""
    if angle_deg > 180:
        return angle_deg - 360
    return angle_deg

def parse_outline_segments(outline_str):
    """
    Parsuje ciąg znaków outline (z atrybutu 'value'), zwraca listę segmentów:
    (x1, y1, x2, y2, is_arc, chord_length).
    
    Obsługuje dwa formaty:
      1) [liczba_segmentów x1 y1 x2 y2 isArc ...]
      2) Outline liczba_segmentów x1 y1 x2 y2 isArc ...
    """
    tokens = outline_str.split()
    if not tokens:
        return []
    
    # Sprawdzamy, czy mamy format z "Outline"
    if len(tokens) > 1 and tokens[1].lower() == "outline":
        try:
            n_segments = int(tokens[2])
        except ValueError:
            return []
        start_index = 3
    else:
        # Format standardowy
        try:
            n_segments = int(tokens[0])
        except ValueError:
            return []
        start_index = 1

    segments = []
    for i in range(n_segments):
        idx = start_index + i*5
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

def compute_bending_angles_from_xml(file_path):
    """
    Pobiera kąty gięcia (AngleAfter) dla deformowalnych komponentów DC z pliku .dld.
    Zwraca ciąg znaków z kątami (np. "90, 90, -45").
    """
    try:
        tree = ET.parse(file_path)
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
                # Szukamy VDeformableComponentAngle
                angle_elem = v.find("VDeformableComponentAngle")
                if angle_elem is not None:
                    try:
                        angle_after = float(angle_elem.attrib.get("value", "0"))
                    except ValueError:
                        angle_after = 0.0
                # Opcjonalnie sprawdzamy VBendDeformation -> AngleAfter
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
    return ", ".join(str(a) for a in angles)

def compute_grouped2_dimensions(file_path):
    """
    Zwraca zgrupowane dane 'Grouped2' w postaci wieloliniowego tekstu:
      <StaticName>: static=..., DC count=N, DC values: ..., Computed dims: ...
    zgodnie z logiką z kod_testowy.py.
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        return f"Błąd parsowania pliku {file_path}: {e}"

    def get_static_value(static_elem):
        """
        Zczytujemy z <StaticComponentPart>/<StaticComponentHull> drugi segment outline
        (lub pierwszy, jeśli jest tylko jeden). Tam chord_length jest interpretowane jako 'static'.
        """
        hull_elem = static_elem.find("./StaticComponentPart/StaticComponentHull")
        if hull_elem is not None:
            val_str = hull_elem.attrib.get("value", "")
            segments = parse_outline_segments(val_str)
            if len(segments) >= 2:
                return segments[1][5]  # chord_length z 2. odcinka (indeks 1)
            elif segments:
                return segments[0][5]
        return 0.0

    def get_dc_value(shortening_elem):
        """
        Z <ShorteningContour> pobieramy wartość chord_length z 2. segmentu (lub 1. jeśli 2 brak).
        """
        val_str = shortening_elem.attrib.get("value", "")
        segments = parse_outline_segments(val_str)
        if len(segments) >= 2:
            return segments[1][5]
        elif segments:
            return segments[0][5]
        return 0.0

    report_lines = []
    # Iterujemy po StaticComponent
    for static in root.findall(".//StaticComponent"):
        comp_elem = static.find("WorkpieceComponentName")
        if comp_elem is None:
            continue
        static_name = comp_elem.attrib.get("value", "").strip()
        static_val = get_static_value(static)

        # Szukamy zagnieżdżonych DeformableCompShortening
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

        line = (
            f"{static_name}: static={round(static_val,6)}, "
            f"DC count={dc_count}, DC values: {dc_values_str}; "
            f"Computed dims: {round(computed_dim,6)}"
        )
        report_lines.append(line)

    return "\n".join(report_lines)

# --------------- Funkcja wyciągająca dane zbiorcze z pliku (podobna do process_summary) ---------------

def parse_dld_summary(file_path):
    """
    Zwraca słownik z danymi:
      - grubosc
      - liczba_odcinkow
      - promien_wewn (zebrany z ActualInnerRadius – pierwszy napotkany)
      - dlugosc_zlamu (z pierwszego BendStep->BendLength)
      - rozwiniecie (BlankLength z BendSequence)
      - wymiary (np. z StaticComponentHull, odcinek nr 2)
      - luki (np. z VDeformableComponentHulls, odcinek nr 1)
      - typ (Inside/Outside z WorkpieceDimensions -> value)
    """
    data = {
        "grubosc": 0.0,
        "liczba_odcinkow": None,
        "promien_wewn": "",
        "dlugosc_zlamu": "",
        "rozwiniecie": "",
        "wymiary": "",
        "luki": "",
        "typ": ""
    }

    # Odczyt XML
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError:
        return data

    # --- Grubość (WorkpieceThickness) ---
    thickness_el = root.find(".//WorkpieceThickness")
    if thickness_el is not None:
        try:
            data["grubosc"] = float(thickness_el.attrib.get("value", "0").replace(',', '.'))
        except ValueError:
            pass

    # --- Liczba odcinków (BendStep + 1) ---
    bend_sequence = root.find(".//BendSequence")
    if bend_sequence is not None:
        bend_steps = bend_sequence.findall("BendStep")
        data["liczba_odcinkow"] = len(bend_steps) + 1 if bend_steps else 1

        # Rozwinięcie z pliku: BlankLength
        blank_length_el = bend_sequence.find("BlankLength")
        if blank_length_el is not None:
            data["rozwiniecie"] = blank_length_el.attrib.get("value", "").replace(',', '.')

        # Długość złamu: z pierwszego BendStep
        if bend_steps:
            first_step = bend_steps[0]
            ds_state = first_step.find("DeformableSystemState")
            if ds_state is not None:
                bend_length_el = ds_state.find("BendLength")
                if bend_length_el is not None:
                    data["dlugosc_zlamu"] = bend_length_el.attrib.get("value", "").replace(',', '.')

    # --- Promień wewnętrzny (ActualInnerRadius) – pierwszy napotkany ---
    air_el = root.find(".//VDeformableComponent/ActualInnerRadius")
    if air_el is not None:
        data["promien_wewn"] = air_el.attrib.get("value", "").replace(',', '.')

    # --- Typ (Inside/Outside) -> z atrybutu WorkpieceDimensions ---
    workpiece_dim = root.find(".//Workpiece/WorkpieceDimensions")
    if workpiece_dim is not None:
        data["typ"] = workpiece_dim.attrib.get("value", "").strip()

    # --- Wymiary (StaticComponentHull, odcinek nr 2) ---
    # Zbieramy sumę długości łuku z odcinka nr 2 po wszystkich StaticComponent z "Hull"
    # (Podobne do w kod_testowy, ale uproszczone)
    base_dims = []
    for sc in root.findall(".//StaticComponent"):
        hull = sc.find("StaticComponentPart/StaticComponentHull")
        if hull is not None:
            outline_val = hull.attrib.get("value", "")
            segments = parse_outline_segments(outline_val)
            # Bierzemy drugi segment (indeks 1), jeśli istnieje
            if len(segments) >= 2:
                arc_len = segments[1][5]  # chord_length
            elif len(segments) == 1:
                arc_len = segments[0][5]
            else:
                arc_len = 0.0
            base_dims.append(arc_len)
    if base_dims:
        data["wymiary"] = ", ".join(str(round(x, 2)) for x in base_dims)

    # --- Łuki (VDeformableComponentHulls, odcinek nr 1) ---
    # Zbieramy chord_length z pierwszego segmentu (indeks 0), dla wszystkich VDeformableComponent
    v_comp_hulls = []
    for vcomp in root.findall(".//VDeformableComponent"):
        hulls_el = vcomp.find("VDeformableComponentHulls")
        if hulls_el is not None:
            outline_val = hulls_el.attrib.get("value", "")
            segments = parse_outline_segments(outline_val)
            if segments:
                # Bierzemy pierwszy segment
                arc_len = segments[0][5]
                v_comp_hulls.append(arc_len)
    if v_comp_hulls:
        data["luki"] = ", ".join(str(round(x, 1)) for x in v_comp_hulls)

    return data

# --------------- Główna część skryptu ---------------

def main():
    # Wczytanie pliku 'wynik.xlsx'
    sciezka_we = os.path.join(os.getcwd(), "wynik.xlsx")
    if not os.path.isfile(sciezka_we):
        print(f"Nie znaleziono pliku wejściowego: {sciezka_we}")
        return

    df = pd.read_excel(sciezka_we)

    # Upewniamy się, że w DataFrame istnieją kolumny docelowe (lub tworzymy je)
    # Kolumny, które chcemy wypełnić / nadpisać:
    kolumny_docelowe = [
        "dane_plik_dld",
        "Długości a/b/c/d.../n",   # Tu wstawiamy "Computed dims" z Grouped2
        "WorkpieceDimensions - Outside, Inside",  # Tu wstawiamy cały tekst Grouped2
        "Grubość",
        "Liczba odcinków",
        "Promień wewn.",
        "Długość złamu",
        "Rozwinięcie",
        "Wymiary",
        "Łuki",
        "Typ",
        "Kąty gięcia (test)"
    ]
    for kol in kolumny_docelowe:
        if kol not in df.columns:
            df[kol] = ""
        df[kol] = df[kol].astype("object")

    folder_dld = os.path.join(os.getcwd(), "plik_dld")
    if not os.path.isdir(folder_dld):
        print(f"Brak folderu plik_dld: {folder_dld}")
        return

    # Opcjonalnie tworzymy podfolder 'tmp'
    folder_tmp = os.path.join(folder_dld, "tmp")
    if not os.path.isdir(folder_tmp):
        os.makedirs(folder_tmp)

    for idx, row in df.iterrows():
        plik_dld_nazwa = row.get("plik_dld", "")
        if pd.isna(plik_dld_nazwa):
            continue

        plik_dld_nazwa = str(plik_dld_nazwa).strip()
        if not plik_dld_nazwa:
            continue

        # Dodaj rozszerzenie .dld, jeśli brak
        if not plik_dld_nazwa.lower().endswith(".dld"):
            plik_dld_nazwa += ".dld"

        sciezka_dld = os.path.join(folder_dld, plik_dld_nazwa)
        if not os.path.isfile(sciezka_dld):
            df.at[idx, "dane_plik_dld"] = f"Brak pliku: {plik_dld_nazwa}"
            continue

        # Wyciągamy dane zbiorcze
        dane_summary = parse_dld_summary(sciezka_dld)
        # Wyciągamy kąty gięcia (test)
        katy_test = compute_bending_angles_from_xml(sciezka_dld)
        # Wyciągamy Grouped2 (wieloliniowy tekst)
        grouped2 = compute_grouped2_dimensions(sciezka_dld)

        # Na potrzeby kolumny "Długości a/b/c/d.../n" musimy wyłuskać same "Computed dims" z grouped2
        computed_dims_list = []
        for line in grouped2.splitlines():
            idx_cd = line.find("Computed dims:")
            if idx_cd != -1:
                dims_part = line[idx_cd + len("Computed dims:"):].strip()
                # Dla jednego wiersza to np. "50.0" lub "20.0"
                # Zbieramy je do listy
                computed_dims_list.append(dims_part)

        # Sklejamy np. w formie "50.0; 20.0; 20.0;"
        computed_dims_str = "; ".join(computed_dims_list) + ";" if computed_dims_list else ""

        # Wypełniamy DataFrame
        try:
            df.at[idx, "dane_plik_dld"] = f"Plik: {plik_dld_nazwa}"
            df.at[idx, "Długości a/b/c/d.../n"] = computed_dims_str  # skrótowe "Computed dims"
            df.at[idx, "WorkpieceDimensions - Outside, Inside"] = grouped2  # pełny tekst Grouped2
            df.at[idx, "Grubość"] = str(dane_summary["grubosc"])
            df.at[idx, "Liczba odcinków"] = str(dane_summary["liczba_odcinkow"])
            df.at[idx, "Promień wewn."] = dane_summary["promien_wewn"]
            df.at[idx, "Długość złamu"] = dane_summary["dlugosc_zlamu"]
            df.at[idx, "Rozwinięcie"] = dane_summary["rozwiniecie"]
            df.at[idx, "Wymiary"] = dane_summary["wymiary"]
            df.at[idx, "Łuki"] = dane_summary["luki"]
            df.at[idx, "Typ"] = dane_summary["typ"]
            df.at[idx, "Kąty gięcia (test)"] = katy_test

            # Zapisujemy też w pliku tekstowym w folderze tmp (opcja)
            nazwa_txt = os.path.splitext(plik_dld_nazwa)[0] + ".txt"
            sciezka_txt = os.path.join(folder_tmp, nazwa_txt)
            with open(sciezka_txt, "w", encoding="utf-8") as f:
                f.write("=== DANE ODCZYTANE Z PLIKU DLD (v2.0) ===\n")
                f.write(f"Nazwa pliku DLD: {plik_dld_nazwa}\n\n")
                f.write(f"- Grubość: {dane_summary['grubosc']}\n")
                f.write(f"- Liczba odcinków: {dane_summary['liczba_odcinkow']}\n")
                f.write(f"- Promień wewn.: {dane_summary['promien_wewn']}\n")
                f.write(f"- Długość złamu: {dane_summary['dlugosc_zlamu']}\n")
                f.write(f"- Rozwinięcie: {dane_summary['rozwiniecie']}\n")
                f.write(f"- Wymiary (StaticCompHull, odc.2): {dane_summary['wymiary']}\n")
                f.write(f"- Łuki (VDeformableCompHulls, odc.1): {dane_summary['luki']}\n")
                f.write(f"- Typ (Inside/Outside): {dane_summary['typ']}\n")
                f.write(f"- Kąty gięcia (test): {katy_test}\n\n")
                f.write("----- GROUPED2 (pełny) -----\n")
                f.write(grouped2 + "\n\n")
                f.write("----- Computed dims (lista) -----\n")
                f.write(computed_dims_str + "\n")

        except Exception as e:
            df.at[idx, "dane_plik_dld"] = f"Wystąpił błąd zapisu danych: {e}"

    # Zapis do pliku końcowego
    sciezka_wy = os.path.join(os.getcwd(), "wynik_dane.xlsx")
    df.to_excel(sciezka_wy, index=False)
    print(f"Zakończono. Wyniki w pliku: {sciezka_wy}")

if __name__ == "__main__":
    main()
