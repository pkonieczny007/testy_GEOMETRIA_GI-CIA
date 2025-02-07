import pandas as pd
import xml.etree.ElementTree as ET
import math
import os

def normalize_angle(angle_deg):
    if angle_deg > 180:
        return angle_deg - 360
    return angle_deg

def compute_inside_dimensions(file_name, df_odcinki):
    """
    Dla detalu file_name z wyniki_odcinki_v3.xlsx pobiera wiersze z odcinka nr 2 i dzieli je na:
      - bazowe wartości (StaticComponentHull)
      - wartości DC (ShorteningContour, Komponent zaczyna się od "DC")
    Następnie, jeśli:
      * liczba bazowych wartości wynosi 2 i mamy 1 wartość DC:
             new[0] = baza[0] + DC[0]
             new[1] = baza[1] + DC[0]
      * jeżeli liczba bazowych wartości > 2 i liczba DC = (liczba_baz - 1):
             new[0] = baza[0] + DC[0]
             dla i = 1..(n-2): new[i] = DC[i-1] + baza[i] + DC[i]
             new[n-1] = baza[-1] + DC[-1]
    Zwraca ciąg liczb oddzielonych przecinkami (zaokrąglonych do 6 miejsc).
    """
    df_file = df_odcinki[df_odcinki["Nazwa pliku"] == file_name]
    df_seg2 = df_file[df_file["Odcinek nr"] == 2]
    
    # Pobieramy bazowe wartości z StaticComponentHull
    df_base = df_seg2[df_seg2["Źródło outline"] == "StaticComponentHull"]
    base_values = []
    for _, row in df_base.iterrows():
        try:
            val = float(str(row["Długość łuku"]).replace(',', '.'))
            base_values.append(val)
        except:
            pass
            
    # Pobieramy wartości DC z ShorteningContour (Komponent zaczyna się od "DC")
    df_dc = df_seg2[(df_seg2["Źródło outline"] == "ShorteningContour") &
                    (df_seg2["Komponent"].str.startswith("DC"))]
    dc_values = []
    for _, row in df_dc.iterrows():
        try:
            val = float(str(row["Długość łuku"]).replace(',', '.'))
            dc_values.append(val)
        except:
            pass
            
    computed_dims = []
    if len(base_values) == 2 and len(dc_values) == 1:
        computed_dims.append(base_values[0] + dc_values[0])
        computed_dims.append(base_values[1] + dc_values[0])
    elif len(base_values) > 2 and len(dc_values) == len(base_values) - 1:
        computed_dims.append(base_values[0] + dc_values[0])
        for i in range(1, len(base_values)-1):
            computed_dims.append(dc_values[i-1] + base_values[i] + dc_values[i])
        computed_dims.append(base_values[-1] + dc_values[-1])
    else:
        computed_dims = base_values
    return ",".join(str(round(x, 6)) for x in computed_dims)

def compute_dc_shortening(file_name, df_odcinki):
    """
    Dla danego detalu (file_name) z wyniki_odcinki_v3.xlsx pobiera wiersze z odcinka nr 2,
    gdzie "Źródło outline" = "ShorteningContour" oraz Komponent zaczyna się od "DC".
    Zwraca ciąg wartości z kolumny "Długość łuku" oddzielonych przecinkami,
    zaokrąglonych do 2 miejsc (np. "4.55,3.82").
    """
    df_file = df_odcinki[df_odcinki["Nazwa pliku"] == file_name]
    df_dc = df_file[(df_file["Odcinek nr"] == 2) &
                    (df_file["Źródło outline"] == "ShorteningContour") &
                    (df_file["Komponent"].str.startswith("DC"))]
    dc_values = []
    for _, row in df_dc.iterrows():
        try:
            val = float(str(row["Długość łuku"]).replace(',', '.'))
            dc_values.append(val)
        except:
            pass
    return ",".join(str(round(x, 2)) for x in dc_values)

def compute_bending_angles_from_xml(file_name):
    """
    Dla danego pliku XML (np. "prd.40047020.dld") pobiera elementy VDeformableComponent,
    których WorkpieceComponentName zaczyna się od "DC". Dla takich elementów:
      - Próbuje odczytać kąt gięcia z "VDeformableComponentAngle"
      - Jeśli brak, sprawdza "VBendDeformation/AngleAfter"
      - Normalizuje kąt i zaokrągla do całości.
    Zwraca ciąg kątów oddzielonych przecinkami (np. "-90,150").
    """
    try:
        tree = ET.parse(file_name)
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
                angle_elem = v.find("VDeformableComponentAngle")
                if angle_elem is not None:
                    try:
                        angle_after = float(angle_elem.attrib.get("value", "0"))
                    except ValueError:
                        angle_after = 0.0
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
    return ",".join(str(x) for x in angles)

def compute_grouped_dimensions(file_name, df_odcinki):
    """
    Poprzednia wersja "Grouped Dimensions (test)" – iteruje wiersze odcinka nr 2
    i tworzy grupy w kolejności w pliku Excel (Static + DC). 
    """
    df_file = df_odcinki[df_odcinki["Nazwa pliku"] == file_name]
    df_seg2 = df_file[df_file["Odcinek nr"] == 2]
    
    groups = []
    current_group = None
    for idx, row in df_seg2.iterrows():
        source = str(row["Źródło outline"]).strip().upper()
        comp = str(row["Komponent"]).strip().upper()
        try:
            value = float(str(row["Długość łuku"]).replace(',', '.'))
        except:
            continue
        if source == "STATICCOMPONENTHULL":
            if current_group is not None:
                groups.append(current_group)
            current_group = {"static": comp, "static_value": value, "dc": [], "dc_order": []}
        elif source == "SHORTENINGCONTOUR" and comp.startswith("DC"):
            if current_group is not None:
                current_group["dc"].append(value)
                current_group["dc_order"].append(comp)
    if current_group is not None:
        groups.append(current_group)
    
    output_lines = []
    for group in groups:
        static_comp = group["static"]
        static_val = group["static_value"]
        dc_order = group["dc_order"]
        dc_values = group["dc"]
        count_dc = len(dc_order)
        computed_values = []
        dc_values_str = []

        for i in range(count_dc):
            cval = static_val
            # Przykład – po kolei dodajemy DC:
            #  Gdy DC count=2 => 
            #   i=0 => cval = static + DC00
            #   i=1 => cval = static + DC00 + DC01
            for j in range(i+1):
                cval += dc_values[j]
            computed_values.append(cval)
            dc_values_str.append(f"{dc_order[i]}={round(dc_values[i],2)}")

        if not dc_values:
            # brak DC => tylko static
            line = f"{static_comp}: static={round(static_val,6)}, DC count=0; Computed dims: {round(static_val,6)}"
        else:
            line = (f"{static_comp}: static={round(static_val,6)}, DC count={count_dc}, "
                    f"DC values: {', '.join(dc_values_str)}; "
                    f"Computed dims: {', '.join(str(round(x,6)) for x in computed_values)}")
        output_lines.append(line)
    return "\n".join(output_lines)

def compute_grouped2(file_name, df_odcinki):
    """
    NOWA FUNKCJA: Tworzy "grouped2" – podsumowanie na podstawie oryginalnej struktury .dld:
      - Wczytujemy plik .dld
      - Dla każdego <StaticComponent>:
        * bierzemy <WorkpieceComponentName> => np. "MainPlane", "SC00", ...
        * w df_odcinki (odcinek nr=2, source=StaticComponentHull) szukamy wiersza z Komponent="MainPlane" => to staticVal
        * w tym samym <StaticComponent> szukamy <DeformableCompShortening> => <DeformableComponentName value="DCxx"/>
          i pobieramy z df_odcinki (odcinek nr=2, source=ShorteningContour, Komponent="DCxx") => dcVal
        * Jeśli występuje kilka DC w tym samym <StaticComponent>, sumujemy w stylu:
           - static + DC0
           - static + DC0 + DC1
           - ...
        * Generujemy 1 linię tekstu dla każdego <StaticComponent>
    Zwraca wielolinijkowy string gotowy do wstawienia do kolumny 'grouped2'.
    """

    # Wczytujemy .dld i parsujemy <StaticComponent>
    try:
        tree = ET.parse(file_name)
        root = tree.getroot()
    except ET.ParseError:
        return ""

    # Dla wygody stwórz "słownik" mapujący (komponent) -> (arcLength static).
    # Odczytamy to z df_odcinki
    def get_static_value(comp_name):
        df_stat = df_odcinki[
            (df_odcinki["Nazwa pliku"] == file_name) &
            (df_odcinki["Odcinek nr"] == 2) &
            (df_odcinki["Źródło outline"] == "StaticComponentHull") &
            (df_odcinki["Komponent"] == comp_name)
        ]
        if len(df_stat) < 1:
            return None
        try:
            val = float(str(df_stat.iloc[0]["Długość łuku"]).replace(',', '.'))
            return val
        except:
            return None

    # analogicznie do pobrania DC
    def get_dc_value(dc_name):
        df_dc = df_odcinki[
            (df_odcinki["Nazwa pliku"] == file_name) &
            (df_odcinki["Odcinek nr"] == 2) &
            (df_odcinki["Źródło outline"] == "ShorteningContour") &
            (df_odcinki["Komponent"] == dc_name)
        ]
        # W pliku .dld, ShorteningContour może mieć kilka segmentów. 
        # Załóżmy, że interesuje nas Suma? Albo pierwsza wartość?
        # W przykładach wygląda, że bierzemy całość z "Długość łuku" (zwykle 1 wiersz). 
        # Jeśli jest ich kilka, można sumować.
        vals = []
        for i2, row2 in df_dc.iterrows():
            try:
                v = float(str(row2["Długość łuku"]).replace(',', '.'))
                vals.append(v)
            except:
                pass
        if not vals:
            return []
        return vals

    lines = []
    # Iterujemy po <StaticComponent> w pliku .dld
    for sc in root.findall(".//StaticComponent"):
        wcn = sc.find("WorkpieceComponentName")
        if wcn is None:
            continue
        static_name = wcn.attrib.get("value","")
        # Odczytaj staticVal z df_odcinki
        static_val = get_static_value(static_name)
        if static_val is None:
            # Może brak odcinka nr2? Pomijamy
            continue

        # Szukamy <DeformableCompShortening>
        dc_values_all = []
        dc_names = []
        for def_comp in sc.findall("DeformableCompShortening"):
            dcn = def_comp.find("DeformableComponentName")
            if dcn is not None:
                dc_name = dcn.attrib.get("value","")
                # Odczyt z df_odcinki
                found_vals = get_dc_value(dc_name)
                if found_vals:
                    # Bywa, że jest kilka wierszy => np. segmenty
                    # W example sumowaliśmy je? 
                    # W tym zadaniu sumowanie jest zależne od Twojej definicji.
                    # Ale w przykładzie "DC00=8.0" to raczej 1 wiersz albo 1 sum. 
                    # Załóżmy, że jak jest wiele segmentów, je sumujemy:
                    ssum = sum(found_vals)
                    dc_values_all.append(ssum)
                    dc_names.append(dc_name)

        # Mamy np. dc_names=["DC00","DC01"], dc_values_all=[8.0,10.04]
        # Tworzymy computed dims:
        # Gdy jest 2 DC => computed: (static+DC[0]), (static+DC[0]+DC[1])
        # Gdy 1 DC => (static+DC[0])
        # Gdy 0 DC => samo static
        computed_list = []
        if len(dc_values_all)==0:
            # brak DC
            computed_list = [static_val]
        else:
            # np. 2 DC => generujemy partial sums
            # i=0 => static+DC[0]
            # i=1 => static+DC[0]+DC[1]
            for i in range(len(dc_values_all)):
                cval = static_val
                for j in range(i+1):
                    cval += dc_values_all[j]
                computed_list.append(cval)

        # Budujemy linię w stylu:
        # "MainPlane: static=62.0, DC count=1, DC values: DC00=8.0; Computed dims: 70.0"
        # "SC00: static=41.957274, DC count=2, DC values: DC00=8.0; DC01=10.04; Computed dims: 49.96,59.997"
        dc_str_list = []
        for i, dn in enumerate(dc_names):
            dc_str_list.append(f"{dn}={round(dc_values_all[i],2)}")

        if len(dc_names)==0:
            line = f"{static_name}: static={round(static_val,6)}, DC count=0; Computed dims: {round(static_val,6)}"
        else:
            line = (f"{static_name}: static={round(static_val,6)}, "
                    f"DC count={len(dc_names)}, "
                    f"DC values: {', '.join(dc_str_list)}; "
                    f"Computed dims: {', '.join(str(round(x,6)) for x in computed_list)}")
        lines.append(line)
    
    return "\n".join(lines)

def main():
    try:
        df_zw = pd.read_excel("wyniki_zw_v3.xlsx")
        df_odcinki = pd.read_excel("wyniki_odcinki_v3.xlsx")
    except Exception as e:
        print("Błąd wczytywania plików Excel:", e)
        return
    
    df_test = df_zw.copy()
    computed_dimensions_list = []
    dc_shortening_list = []
    bending_angles_list = []
    grouped_dimensions_list = []
    grouped2_list = []  # NOWA KOLUMNA

    for idx, row in df_test.iterrows():
        file_name = row["Nazwa pliku"]
        typ = str(row["Typ"]).strip().lower()

        # 1) Wymiary wewn. (test)
        if typ == "inside":
            computed_dim = compute_inside_dimensions(file_name, df_odcinki)
            computed_dimensions_list.append(computed_dim)
        else:
            computed_dimensions_list.append("")

        # 2) DC Shortening (test)
        dc_val = compute_dc_shortening(file_name, df_odcinki)
        dc_shortening_list.append(dc_val)

        # 3) Kąty gięcia (test)
        angles_val = compute_bending_angles_from_xml(file_name)
        bending_angles_list.append(angles_val)

        # 4) Grouped Dimensions (test)
        grouped_dims = compute_grouped_dimensions(file_name, df_odcinki)
        grouped_dimensions_list.append(grouped_dims)

        # 5) NOWA KOLUMNA: grouped2
        g2 = compute_grouped2(file_name, df_odcinki)
        grouped2_list.append(g2)

    df_test["Wymiary wewnętrzne (test)"] = computed_dimensions_list
    df_test["DC Shortening (test)"] = dc_shortening_list
    df_test["Kąty gięcia (test)"] = bending_angles_list
    df_test["Grouped Dimensions (test)"] = grouped_dimensions_list
    df_test["grouped2"] = grouped2_list  # Nowa kolumna z naszą logiką

    try:
        df_test.to_excel("TESTY.xlsx", index=False)
        print("Plik TESTY.xlsx został zapisany (z kolumną 'grouped2').")
    except Exception as e:
        print("Błąd zapisu pliku TESTY.xlsx:", e)

if __name__ == "__main__":
    main()
