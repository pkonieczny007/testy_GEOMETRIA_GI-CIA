# -*- coding: utf-8 -*-
"""
Przykładowy skrypt generujący dwa pliki Excela:
1) wyniki_odcinki_o1.xlsx – dane szczegółowe każdego odcinka
2) wyniki_zw_o1.xlsx – zestawienie w formie wskazanej w pytaniu
   z kolumnami:
   Nazwa pliku, Liczba odcinkow, Wymiary zewnetrzne, Wymiary wewnętrzne,
   Promień wewnętrzny, Długość złamu, Rozwinięcie wyliczeniowe, Rozwinięcie z pliku,
   Wymiary, Łuki, Typ
"""

import os
import glob
import math
import xml.etree.ElementTree as ET
import pandas as pd

def parse_outline(outline_str):
    """
    Funkcja do parsowania atrybutu 'value' np. "4 x1 y1 x2 y2 bool x1 y1 x2 y2 bool ..."
    lub "1 Outline 4 x1 y1 x2 y2 bool ...".
    Zwraca listę (x1, y1, x2, y2, is_arc, chord_length).
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
        idx = start_index + i*5
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
    Zwraca listę wierszy szczegółowych:
      [filename, component, source, odcinek_nr,
       x1, y1, x2, y2, is_arc, chord_len, arc_len, skrajny_bool]
    """
    results = []
    filename = os.path.basename(filepath)

    # Odczyt XML
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Błąd parsowania pliku {filepath}: {e}")
        return results

    # --- StaticComponent ---
    for static_comp in root.findall(".//StaticComponent"):
        comp_name_elem = static_comp.find("WorkpieceComponentName")
        comp_name = comp_name_elem.attrib.get("value","") if comp_name_elem is not None else ""

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
        def_comp = static_comp.find("DeformableCompShortening")
        if def_comp is not None:
            dc_name_elem = def_comp.find("DeformableComponentName")
            dc_name = dc_name_elem.attrib.get("value","") if dc_name_elem is not None else ""
            sc_elem = def_comp.find("ShorteningContour")
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
        comp_name_elem = vdef.find("WorkpieceComponentName")
        comp_name = comp_name_elem.attrib.get("value","") if comp_name_elem is not None else ""

        # (A) BendLine
        bend_line_elem = vdef.find("VDeformableComponentBendLine")
        if bend_line_elem is not None:
            segs = parse_outline(bend_line_elem.attrib.get("value",""))
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
                # z definicji - arcLength = x2 z pierwszego segmentu
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


def create_summary_for_file(filepath, detail_rows):
    """
    Tworzy słownik, który odpowiada docelowej tabeli:
    [Nazwa pliku, Liczba odcinkow, Wymiary zewnetrzne, Wymiary wewnętrzne,
     Promień wewnętrzny, Długość złamu, Rozwinięcie wyliczeniowe, Rozwinięcie z pliku,
     Wymiary, Łuki, Typ]

    detail_rows – wszystkie wiersze (z process_file) dla *wszystkich* plików, 
                  z których wyłuskamy te pasujące do 'filepath'.
    """
    fname = os.path.basename(filepath)
    row_dict = {
        "Nazwa pliku": fname,
        "Liczba odcinkow": None,
        "Wymiary zewnetrzne": "",
        "Wymiary wewnętrzne": "",
        "Promień wewnętrzny": "",
        "Długość złamu": "",
        "Rozwinięcie wyliczeniowe": "",
        "Rozwinięcie z pliku": "",
        "Wymiary": "",
        "Łuki": "",
        "Typ": ""
    }

    # wczytujemy XML
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Błąd parsowania {filepath}: {e}")
        return row_dict

    # A) Liczba odcinków -> zliczamy <VDeformableComponent> lub <BendStep> w <BendSequence>
    bend_seq = root.find(".//BendSequence")
    if bend_seq is not None:
        bend_steps = bend_seq.findall("BendStep")
        row_dict["Liczba odcinkow"] = len(bend_steps) if bend_steps else 0
    else:
        # ewentualnie 0 lub brak
        row_dict["Liczba odcinkow"] = 0

    # B) Odczyt "Typ" = Inside / Outside
    wdim = root.find(".//Workpiece/WorkpieceDimensions")
    if wdim is not None:
        row_dict["Typ"] = wdim.attrib.get("value","")

    # C) Promień wewnętrzny (zbieramy ActualInnerRadius)
    radii = []
    for vcomp in root.findall(".//VDeformableComponent"):
        for ar in vcomp.findall("ActualInnerRadius"):
            val_str = ar.attrib.get("value","").replace(",",".")
            if val_str:
                try:
                    radii.append(float(val_str))
                except:
                    pass
    if radii:
        # np. "8.04273, 6"
        row_dict["Promień wewnętrzny"] = ", ".join(str(r) for r in radii)

    # D) Długość złamu – z <BendSequence><BendStep><DeformableSystemState><BendLength>
    bend_length_val = ""
    if bend_seq is not None:
        first_bs = bend_seq.find("BendStep")
        if first_bs is not None:
            ds_state = first_bs.find("DeformableSystemState")
            if ds_state is not None:
                bl_elem = ds_state.find("BendLength")
                if bl_elem is not None:
                    bend_length_val = bl_elem.attrib.get("value","")
    row_dict["Długość złamu"] = bend_length_val

    # E) Rozwinięcie z pliku -> <BlankLength>
    blank_val = ""
    if bend_seq is not None:
        blank_elem = bend_seq.find("BlankLength")
        if blank_elem is not None:
            blank_val = blank_elem.attrib.get("value","")
    row_dict["Rozwinięcie z pliku"] = blank_val

    # F) Rozwinięcie wyliczeniowe -> np. sumaryczna wartość z "odcinek nr 2" i source w ["StaticComponentHull", "VDeformableComponentHulls"]
    #    (to jest przykładowa logika – dostosuj wedle potrzeb).
    sum_rozwin = 0.0
    for row in detail_rows:
        # row: [filename, comp, source, odc_nr, x1, y1, x2, y2, is_arc, chord_len, arc_len, skrajny]
        if row[0] == fname and row[3] == 2 and row[2] in ["StaticComponentHull", "VDeformableComponentHulls"]:
            try:
                sum_rozwin += float(row[10])  # arc_len
            except:
                pass
    if sum_rozwin:
        row_dict["Rozwinięcie wyliczeniowe"] = str(sum_rozwin)

    # G) Wymiary zewnętrzne / wewnętrzne -> z Twoich danych. 
    #    W przykładach wpisujesz "70.0,49.96,17.96" lub "3.82189,16.984" itp.
    #    Możesz to liczyć z sum (skrajne, środkowe) albo przechowywać w pliku. 
    #    Tu – przykładowo – weźmiemy "odcinek 2, SC + DC" itp. (podobnie jak w poprzednich snippetach).
    #    Dla uproszczenia: weźmiemy 2 wartości (SC(2) + DC(2)) i wpiszemy do "Wymiary zewnetrzne".
    #    A do "Wymiary wewnętrzne" – cokolwiek innego. 
    #    W realnym kodzie wstaw tu logikę obliczania, jak w Twoich wcześniejszych wytycznych.
    
    # =============== Przykładowa, minimalna logika: =====================
    # "Wymiary zewnetrzne" – zsumuj SC(2) + DC(2)
    sc_vals = []
    dc_vals = []
    for row in detail_rows:
        if row[0] == fname and row[3] == 2:
            source = row[2]
            arc_len = row[10]
            if source == "StaticComponentHull":
                sc_vals.append(arc_len)
            elif source == "ShorteningContour":
                dc_vals.append(arc_len)
    # Tworzymy listę wymiarów z sum SC[i] + DC[i], parując wg indeksu
    # (w realnym wypadku może być inna zasada parowania)
    wymiary_zew = []
    for i in range(min(len(sc_vals), len(dc_vals))):
        val = sc_vals[i] + dc_vals[i]
        wymiary_zew.append(round(val,2))

    row_dict["Wymiary zewnetrzne"] = ",".join(str(x) for x in wymiary_zew)

    # "Wymiary wewnętrzne" – tu np. oblicz jak w pytaniu (minus grubość, itp.)
    # Na potrzeby przykładu wstawimy 2 przykładowe wartości
    # Lepiej wstawić realne obliczenia. 
    # Poniżej – jeżeli Twój <WorkpieceDimensions value="Inside"> – wypełniamy,
    # a jeżeli "Outside" – puste, i odwrotnie.
    if row_dict["Typ"].lower() == "inside":
        # wstawmy np. Wymiary wewnętrzne = [ val-3 for val in wymiary_zew ]
        # (w praktyce: zależnie od realnego sposobu)
        inner_list = [round(x-3,3) for x in wymiary_zew if x>3]
        row_dict["Wymiary wewnętrzne"] = ",".join(str(x) for x in inner_list)
    else:
        # wstawmy pusto lub cokolwiek
        row_dict["Wymiary wewnętrzne"] = ""

    # H) "Wymiary" – w Twoim przykładzie często wpisujesz tam sumy z SC(2) i ewentualnie bez DC. 
    #    Możesz też wstawić "SC(2), SC(2), SC(2)" – zależnie od definicji. 
    #    Tutaj pokażemy przykład:
    #    Zbieramy same SC(2) i zrobimy listę. 
    sc_only = [round(x,2) for x in sc_vals]
    row_dict["Wymiary"] = ",".join(str(x) for x in sc_only)

    # I) "Łuki" – np. z VDeformableComponentHulls, odcinek nr 1
    #    Zbierzmy je do listy i wpiszmy. 
    arcs_list = []
    for row in detail_rows:
        if row[0] == fname and row[2] == "VDeformableComponentHulls" and row[3] == 1:
            # row[10] – arc_length
            arcs_list.append(round(row[10],1))
    row_dict["Łuki"] = ",".join(str(x) for x in arcs_list)

    return row_dict


def main():
    dld_files = glob.glob("*.dld")
    if not dld_files:
        print("Brak plików *.dld w folderze.")
        return

    all_details = []
    # 1) Najpierw zbieramy wszystkie wiersze szczegółowe z process_file
    for fp in dld_files:
        detail = process_file(fp)
        all_details.extend(detail)

    # Zapis szczegółowy:
    cols_details = [
        "Nazwa pliku", "Komponent", "Źródło outline", "Odcinek nr",
        "X1", "Y1", "X2", "Y2", "Łuk?", "Długość cięciwy", "Długość łuku", "Skrajny"
    ]
    df_d = pd.DataFrame(all_details, columns=cols_details)
    df_d.to_excel("wyniki_odcinki_o1.xlsx", index=False)
    print("Zapisano plik 'wyniki_odcinki_o1.xlsx'.")

    # 2) Teraz tworzymy wiersze podsumowania
    all_summaries = []
    for fp in dld_files:
        row_sum = create_summary_for_file(fp, all_details)
        all_summaries.append(row_sum)

    # Ustalamy finalną kolejność kolumn w exactly the same order:
    final_cols = [
        "Nazwa pliku",
        "Liczba odcinkow",
        "Wymiary zewnetrzne",
        "Wymiary wewnętrzne",
        "Promień wewnętrzny",
        "Długość złamu",
        "Rozwinięcie wyliczeniowe",
        "Rozwinięcie z pliku",
        "Wymiary",
        "Łuki",
        "Typ"
    ]
    df_summ = pd.DataFrame(all_summaries, columns=final_cols)
    df_summ.to_excel("wyniki_zw_o1.xlsx", index=False)
    print("Zapisano plik 'wyniki_zw_o1.xlsx'.")

if __name__ == "__main__":
    main()
