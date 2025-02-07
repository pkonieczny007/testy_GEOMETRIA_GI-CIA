# -*- coding: utf-8 -*-
"""
Przykładowy kompletny skrypt z poprawnym liczeniem "skrajnych" i "środkowych" wymiarów
wg reguły:
   - Pierwszy statyczny segment + DC0 = wymiar skrajny lewy
   - DC0 + kolejny statyczny + DC1 = wymiar środkowy
   - DC(n-2) + ostatni statyczny = skrajny prawy
itp.

Generuje dwa pliki:
  1) wyniki_odcinki_o1.xlsx – dane szczegółowe
  2) wyniki_zw_o1.xlsx       – podsumowanie z wyliczonymi wymiarami.
"""

import os
import glob
import math
import xml.etree.ElementTree as ET
import pandas as pd

def parse_outline(outline_str):
    """
    Funkcja do parsowania atrybutu 'value' np.:
      "4 x1 y1 x2 y2 bool x1 y1 x2 y2 bool ..."
      lub "1 Outline 4 x1 y1 x2 y2 bool ..."
    Zwraca listę krotek: (x1, y1, x2, y2, is_arc, chord_length).
    """
    outline_str = outline_str.replace(",", ".")
    tokens = outline_str.split()
    if not tokens:
        return []

    # Sprawdzamy, czy mamy "Outline" w 2. tokenie
    if len(tokens) > 2 and tokens[1].lower() == "outline":
        try:
            n_segments = int(tokens[2])
        except ValueError:
            return []
        start_index = 3
    else:
        # Pierwszy token to liczba segmentów
        try:
            n_segments = int(tokens[0])
        except ValueError:
            return []
        start_index = 1

    segments = []
    for i in range(n_segments):
        idx = start_index + i * 5
        chunk = tokens[idx:idx+5]
        if len(chunk) < 5:
            continue
        try:
            x1 = float(chunk[0])
            y1 = float(chunk[1])
            x2 = float(chunk[2])
            y2 = float(chunk[3])
            is_arc = (chunk[4].lower() == "true")
        except ValueError:
            continue

        chord_length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        segments.append((x1, y1, x2, y2, is_arc, chord_length))

    return segments


def process_file(filepath):
    """
    Przetwarza jeden plik .dld i zwraca listę WIERZY:
      [filename, component, source, odcinek_nr,
       x1, y1, x2, y2, is_arc, chord_len, arc_len, skrajny_bool]
    """
    results = []
    filename = os.path.basename(filepath)

    # Parsowanie XML
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Błąd parsowania pliku {filepath}: {e}")
        return results

    # --- StaticComponent ---
    for static_comp in root.findall(".//StaticComponent"):
        wcn_elem = static_comp.find("WorkpieceComponentName")
        comp_name = wcn_elem.attrib.get("value","") if wcn_elem is not None else ""

        # (A) StaticComponentHull
        hull_elem = static_comp.find("StaticComponentPart/StaticComponentHull")
        if hull_elem is not None:
            segs = parse_outline(hull_elem.attrib.get("value",""))
            nseg = len(segs)
            for i,(x1,y1,x2,y2,is_arc,ch_len) in enumerate(segs):
                arc_len = ch_len  # w uproszczeniu
                skrajny = (i==0 or i==nseg-1)
                results.append([
                    filename, comp_name, "StaticComponentHull", i+1,
                    x1, y1, x2, y2, is_arc, ch_len, arc_len, skrajny
                ])

        # (B) DeformableCompShortening -> ShorteningContour
        defc = static_comp.find("DeformableCompShortening")
        if defc is not None:
            dcn_elem = defc.find("DeformableComponentName")
            dc_name = dcn_elem.attrib.get("value","") if dcn_elem is not None else ""
            sc_elem = defc.find("ShorteningContour")
            if sc_elem is not None:
                segs = parse_outline(sc_elem.attrib.get("value",""))
                nseg = len(segs)
                for i,(x1,y1,x2,y2,is_arc,ch_len) in enumerate(segs):
                    arc_len = ch_len
                    skrajny = (i==0 or i==nseg-1)
                    results.append([
                        filename, dc_name, "ShorteningContour", i+1,
                        x1, y1, x2, y2, is_arc, ch_len, arc_len, skrajny
                    ])

    # --- VDeformableComponent ---
    for vdef in root.findall(".//VDeformableComponent"):
        wcn_elem = vdef.find("WorkpieceComponentName")
        comp_name = wcn_elem.attrib.get("value","") if wcn_elem is not None else ""

        # (A) BendLine
        bl_elem = vdef.find("VDeformableComponentBendLine")
        if bl_elem is not None:
            segs = parse_outline(bl_elem.attrib.get("value",""))
            nseg = len(segs)
            for i,(x1,y1,x2,y2,is_arc,ch_len) in enumerate(segs):
                arc_len = ch_len
                skrajny = (i==0 or i==nseg-1)
                results.append([
                    filename, comp_name, "VDeformableComponentBendLine", i+1,
                    x1, y1, x2, y2, is_arc, ch_len, arc_len, skrajny
                ])

        # (B) VDeformableComponentHulls
        hulls_elem = vdef.find("VDeformableComponentHulls")
        if hulls_elem is not None:
            segs = parse_outline(hulls_elem.attrib.get("value",""))
            nseg = len(segs)
            arc_val = None
            if comp_name.startswith("DC") and nseg>0:
                # definicja: arcLength = x2 z pierwszego segmentu
                arc_val = segs[0][2]
            for i,(x1,y1,x2,y2,is_arc,ch_len) in enumerate(segs):
                if arc_val is not None:
                    arc_len = arc_val
                else:
                    arc_len = ch_len
                skrajny = (i==0 or i==nseg-1)
                results.append([
                    filename, comp_name, "VDeformableComponentHulls", i+1,
                    x1, y1, x2, y2, is_arc, ch_len, arc_len, skrajny
                ])

    return results


def compute_dimensions_skrajne_srodkowe(
    static_list, dc_list,
    dimension_mode="Outside"
):
    """
    Funkcja przyjmująca dwie listy:
      static_list = [(komponent, arc_len), (komponent, arc_len), ...]  – odcinek nr 2
      dc_list     = [(komponent, arc_len), (komponent, arc_len), ...]  – odcinek nr 2
    ułożone w KOLEJNOŚCI logicznej:
      np. static_list = [ (MainPlane, 95.44915),
                          (SC00, 17.627265),
                          (SC01, 32.178115) ]
          dc_list     = [ (DC00, X), (DC01, Y) ]

    Wynik: listę floatów reprezentujących:
      - skrajny lewy = static0 + DC0
      - środkowy = DC0 + static1 + DC1
      - skrajny prawy = DC1 + static2
    (dla 3 statycznych i 2 DC).
    Jeśli jest inna liczba segmentów, można to uogólnić pętlą.

    dimension_mode: "Outside" lub "Inside" – ewentualnie możemy wstawić
                    korekty (np. -grubość) przy Inside.
    """
    # Upewniamy się, że mamy min. 3 statics i 2 DC (w tym przykładzie)
    # Jeśli w pliku jest inna liczba – dopasuj poniższą logikę.
    dims = []

    n_static = len(static_list)
    n_dc = len(dc_list)

    # Przykład: 3 statics, 2 DC
    # i=0: skrajny lewy -> static[0] + dc[0]
    # i=1: środkowy -> dc[0] + static[1] + dc[1]
    # i=2: skrajny prawy -> dc[1] + static[2]

    if n_static == 3 and n_dc == 2:
        s0 = static_list[0][1]
        s1 = static_list[1][1]
        s2 = static_list[2][1]
        dc0 = dc_list[0][1]
        dc1 = dc_list[1][1]

        left  = s0 + dc0
        mid   = dc0 + s1 + dc1
        right = dc1 + s2

        dims = [left, mid, right]

    else:
        # Jeżeli chcesz bardziej ogólne podejście do n segmentów:
        #   0: static[0] + dc[0]
        #   i in [1..n-2]: dc[i-1] + static[i] + dc[i]
        #   n-1: dc[n-2] + static[n-1]
        # implementacja pętli:
        dims_tmp = []
        for i in range(n_static):
            if i == 0:
                # skrajny lewy
                if n_dc > 0:
                    dims_tmp.append(static_list[i][1] + dc_list[0][1])
                else:
                    dims_tmp.append(static_list[i][1])
            elif i == n_static - 1:
                # skrajny prawy
                dc_idx = i - 1
                if dc_idx >= 0 and dc_idx < n_dc:
                    dims_tmp.append(dc_list[dc_idx][1] + static_list[i][1])
                else:
                    dims_tmp.append(static_list[i][1])
            else:
                # środkowy
                dc_left_idx  = i - 1
                dc_right_idx = i
                val = static_list[i][1]
                if 0 <= dc_left_idx < n_dc:
                    val += dc_list[dc_left_idx][1]
                if 0 <= dc_right_idx < n_dc:
                    val += dc_list[dc_right_idx][1]
                dims_tmp.append(val)
        dims = dims_tmp

    # Ewentualnie korekta, jeśli dimension_mode == "Inside"
    if dimension_mode.lower() == "inside":
        # Przykład: odejmij grubość 2mm (jeśli tak to zdefiniowano).
        # Można wczytać realną grubość z pliku .dld i tutaj odjąć. 
        # Tymczasowo pokazujemy np. -2:
        dims = [d - 2 for d in dims if d>2]

    return dims


def create_summary_for_file(filepath, detail_rows):
    """
    Tworzy słownik z kolumnami do pliku "wyniki_zw_o1.xlsx", w tym
    Wymiary zewnetrzne i Wymiary wewnetrzne wyliczone wg reguły
    skrajne/środkowe (Static + DC).
    """
    fname = os.path.basename(filepath)
    summary = {
        "Nazwa pliku": fname,
        "Liczba odcinkow": None,
        "Wymiary zewnetrzne": "",
        "Wymiary wewnętrzne": "",
        "Promień wewnętrzny": "",
        "Długość złamu": "",
        "Rozwinięcie wyliczeniowe": "",
        "Rozwinięcie z pliku": "",
        "Wymiary": "",  # w razie potrzeby
        "Łuki": "",     # w razie potrzeby
        "Typ": ""       # Inside/Outside
    }

    # Wczytujemy XML
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Błąd parsowania {filepath}: {e}")
        return summary

    # 1) Liczba odcinków – np. z BendStep w BendSequence
    bend_seq = root.find(".//BendSequence")
    if bend_seq is not None:
        bsteps = bend_seq.findall("BendStep")
        summary["Liczba odcinkow"] = len(bsteps)
    else:
        summary["Liczba odcinkow"] = 0

    # 2) Typ = Inside/Outside
    dim_elem = root.find(".//Workpiece/WorkpieceDimensions")
    dimension_mode = dim_elem.attrib.get("value","") if dim_elem is not None else ""
    summary["Typ"] = dimension_mode

    # 3) Promień wewnętrzny
    radii_vals = []
    for vdef in root.findall(".//VDeformableComponent"):
        for ar in vdef.findall("ActualInnerRadius"):
            val_str = ar.attrib.get("value","").replace(",",".")
            if val_str:
                try:
                    radii_vals.append(float(val_str))
                except:
                    pass
    if radii_vals:
        summary["Promień wewnętrzny"] = ", ".join(str(r) for r in radii_vals)

    # 4) Długość złamu – z pierwszego BendStep->DeformableSystemState->BendLength
    bend_len_str = ""
    if bend_seq is not None:
        first_bs = bend_seq.find("BendStep")
        if first_bs is not None:
            ds = first_bs.find("DeformableSystemState")
            if ds is not None:
                bl = ds.find("BendLength")
                if bl is not None:
                    bend_len_str = bl.attrib.get("value","")
    summary["Długość złamu"] = bend_len_str

    # 5) Rozwinięcie z pliku – <BlankLength>
    blank_len_str = ""
    if bend_seq is not None:
        bl_elem = bend_seq.find("BlankLength")
        if bl_elem is not None:
            blank_len_str = bl_elem.attrib.get("value","")
    summary["Rozwinięcie z pliku"] = blank_len_str

    # 6) Rozwinięcie wyliczeniowe – np. sum (odc=2, source in [StaticComponentHull, VDeformableComponentHulls])
    sum_rozwin = 0.0
    for row in detail_rows:
        if row[0] == fname and row[3] == 2 and (row[2] in ["StaticComponentHull", "VDeformableComponentHulls"]):
            try:
                sum_rozwin += float(row[10])  # arc_len
            except:
                pass
    summary["Rozwinięcie wyliczeniowe"] = str(sum_rozwin) if sum_rozwin else ""

    # 7) Wymiary zewn. i wewn. wg reguły skrajne/środkowe
    #    Zbieramy segmenty statyczne i DC (ShorteningContour), odc=2
    #    Sortujemy w kolejności: MainPlane -> SC00 -> SC01 -> ...
    #    DC w kolejności DC00 -> DC01 -> ...
    #    Potem compute_dimensions_skrajne_srodkowe.
    static_list = []
    dc_list = []

    # Prosta mapka priorytetów, by posortować w logicznej kolejności
    # (możesz rozbudować zależnie od swoich nazw)
    priority_static = {
        "MainPlane": 0,
        "SC00": 1,
        "SC01": 2,
        "SC02": 3
    }
    priority_dc = {
        "DC00": 0,
        "DC01": 1,
        "DC02": 2
    }

    for row in detail_rows:
        # row = [filename, comp, source, odc_nr, ..., arc_len(index=10), skrajny(11)]
        if row[0] == fname and row[3] == 2:
            comp  = row[1]
            src   = row[2]
            a_len = row[10]
            if src == "StaticComponentHull":
                prio = priority_static.get(comp, 99)
                static_list.append((prio, comp, a_len))
            elif src == "ShorteningContour" and comp.startswith("DC"):
                prio = priority_dc.get(comp, 99)
                dc_list.append((prio, comp, a_len))

    # Sortujemy wg prio
    static_list.sort(key=lambda x: x[0])
    dc_list.sort(key=lambda x: x[0])

    # Budujemy listy (comp, arc_len) -> arc_len
    st_list = [(it[1], it[2]) for it in static_list]  # (comp, val)
    dc_l    = [(it[1], it[2]) for it in dc_list]

    dims_outside = compute_dimensions_skrajne_srodkowe(st_list, dc_l, dimension_mode="Outside")
    dims_inside  = compute_dimensions_skrajne_srodkowe(st_list, dc_l, dimension_mode="Inside")

    # Jeżeli plik ma typ Outside, to "Wymiary zewnetrzne" = dims_outside, "Wymiary wewnętrzne" = pusto
    # Jeżeli plik ma typ Inside, to "Wymiary wewnętrzne" = dims_inside, "Wymiary zewnetrzne" = pusto
    if dimension_mode.lower() == "outside":
        summary["Wymiary zewnetrzne"] = ", ".join(str(round(x,5)) for x in dims_outside)
        summary["Wymiary wewnętrzne"] = ""
    else:
        summary["Wymiary zewnetrzne"] = ""
        summary["Wymiary wewnętrzne"] = ", ".join(str(round(x,5)) for x in dims_inside)

    return summary


def main():
    dld_files = glob.glob("*.dld")
    if not dld_files:
        print("Brak plików .dld w folderze.")
        return

    # 1) Zbieramy dane szczegółowe ze wszystkich plików
    all_details = []
    for fp in dld_files:
        rows = process_file(fp)
        all_details.extend(rows)

    # Zapis do wyniki_odcinki_o1.xlsx (szczegóły)
    cols = [
      "Nazwa pliku", "Komponent", "Źródło outline", "Odcinek nr",
      "X1", "Y1", "X2", "Y2", "Łuk?", "Długość cięciwy", "Długość łuku", "Skrajny?"
    ]
    df_detail = pd.DataFrame(all_details, columns=cols)
    df_detail.to_excel("wyniki_odcinki_o1.xlsx", index=False)
    print("Utworzono plik 'wyniki_odcinki_o1.xlsx'.")

    # 2) Tworzymy podsumowanie
    all_summaries = []
    for fp in dld_files:
        summary_row = create_summary_for_file(fp, all_details)
        all_summaries.append(summary_row)

    # Ustalamy kolejność kolumn w wynikach końcowych
    final_cols = [
        "Nazwa pliku",
        "Liczba odcinkow",
        "Wymiary zewnetrzne",
        "Wymiary wewnętrzne",
        "Promień wewnętrzny",
        "Długość złamu",
        "Rozwinięcie wyliczeniowe",
        "Rozwinięcie z pliku",
        "Wymiary",  # ewentualnie jeśli chcesz wypełniać
        "Łuki",     # ewentualnie
        "Typ"
    ]
    df_summ = pd.DataFrame(all_summaries, columns=final_cols)
    df_summ.to_excel("wyniki_zw_o1.xlsx", index=False)
    print("Utworzono plik 'wyniki_zw_o1.xlsx' z podsumowaniem.")


if __name__ == "__main__":
    main()
