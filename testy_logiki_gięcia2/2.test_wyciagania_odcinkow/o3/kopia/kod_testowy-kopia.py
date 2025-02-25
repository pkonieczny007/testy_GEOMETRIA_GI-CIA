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
    Dla danego detalu (file_name) z wyniki_odcinki_v3.xlsx
    pobiera wiersze z odcinka nr 2 i dzieli je na:
      - bazowe wartości (pochodzące z StaticComponentHull)
      - wartości DC (pochodzące z ShorteningContour, Komponent zaczyna się od "DC")
    Następnie, przyjmując, że liczba bazowych wartości = n, wylicza nowe wymiary wewnętrzne wg:
      - Jeśli n == 2 i 1 wartość DC:
            new[0] = baza[0] + DC[0]
            new[1] = baza[1] + DC[0]
      - Jeśli n > 2 i liczba DC = n - 1:
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
    # Tu nie usuwamy duplikatów – gdyż w tym wariancie chcemy zachować kolejność
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
        computed_dims = base_values  # jeżeli schemat nie pasuje
    return ",".join(str(round(x, 6)) for x in computed_dims)

def compute_dc_shortening(file_name, df_odcinki):
    """
    Dla danego detalu (file_name) z wyniki_odcinki_v3.xlsx
    pobiera wiersze dla odcinka nr 2, gdzie "Źródło outline" to "ShorteningContour"
    oraz Komponent zaczyna się od "DC". Teraz – dodatkowo – usuwamy duplikaty
    (według kolumny "Komponent") i zwracamy ciąg wartości z kolumny "Długość łuku"
    oddzielonych przecinkami, zaokrąglonych do 2 miejsc (np. "4.55,3.82").
    """
    df_file = df_odcinki[df_odcinki["Nazwa pliku"] == file_name]
    df_dc = df_file[(df_file["Odcinek nr"] == 2) &
                    (df_file["Źródło outline"] == "ShorteningContour") &
                    (df_file["Komponent"].str.startswith("DC"))]
    df_dc = df_dc.drop_duplicates(subset=["Komponent"])
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
    Funkcja grupuje dane z odcinka nr 2 dla danego pliku (file_name) z wyniki_odcinki_v3.xlsx.
    Iteruje w kolejności – przyjmujemy, że wiersze są zapisane zgodnie z kolejnością występowania w XML.
    
    Dla każdego wiersza, gdzie "Źródło outline" = "StaticComponentHull" (czyli statyczny komponent),
    rozpoczyna nową grupę. Następnie, kolejne wiersze, gdzie "Źródło outline" = "ShorteningContour" i
    Komponent zaczyna się od "DC", dodawane są do bieżącej grupy (przy czym usuwamy duplikaty według nazwy).
    
    Dla każdej grupy wylicza:
      - Liczbę przypisanych skróceń (DC)
      - Listę DC w postaci "DCxx=<value>" (zaokrąglonych do 2 miejsc)
      - Dla każdego DC oblicza computed_value = (wartość z StaticComponentHull) + (wartość DC)
    
    Zwraca tekstowy raport z grup, oddzielonych nowymi liniami.
    """
    df_file = df_odcinki[df_odcinki["Nazwa pliku"] == file_name]
    df_seg2 = df_file[df_file["Odcinek nr"] == 2]
    
    groups = []
    current_group = None
    for idx, row in df_seg2.iterrows():
        source = row["Źródło outline"]
        comp = row["Komponent"]
        try:
            value = float(str(row["Długość łuku"]).replace(',', '.'))
        except:
            continue
        if source == "StaticComponentHull":
            # Nowa grupa – zapisz poprzednią, jeśli istnieje
            if current_group is not None:
                groups.append(current_group)
            current_group = {"static": comp, "static_value": value, "dc": {}, "dc_order": []}
        elif source == "ShorteningContour" and comp.startswith("DC"):
            if current_group is not None:
                # Dodajemy tylko jeśli jeszcze nie wystąpiło dla tego DC
                if comp not in current_group["dc"]:
                    current_group["dc"][comp] = value
                    current_group["dc_order"].append(comp)
    if current_group is not None:
        groups.append(current_group)
    
    output_lines = []
    for group in groups:
        static_comp = group["static"]
        static_val = group["static_value"]
        dc_dict = group["dc"]
        dc_order = group["dc_order"]
        count_dc = len(dc_order)
        # Obliczamy computed value dla każdych przypisanych DC
        computed_values = []
        dc_values_str = []
        for dc_comp in dc_order:
            dc_val = dc_dict[dc_comp]
            computed = static_val + dc_val
            computed_values.append(computed)
            dc_values_str.append(f"{dc_comp}={round(dc_val,2)}")
        line = (f"{static_comp}: static={round(static_val,6)}, DC count={count_dc}, "
                f"DC values: {', '.join(dc_values_str)}; "
                f"Computed dims: {', '.join(str(round(x,6)) for x in computed_values)}")
        output_lines.append(line)
    return "\n".join(output_lines)

def main():
    try:
        df_zw = pd.read_excel("wyniki_zw_v3.xlsx")
        df_odcinki = pd.read_excel("wyniki_odcinki_v3.xlsx")
    except Exception as e:
        print("Błąd wczytywania plików Excel:", e)
        return
    
    # Skrypt testowy – działamy na danych z wyniki_zw_v3.xlsx
    df_test = df_zw.copy()
    computed_dimensions_list = []
    dc_shortening_list = []
    bending_angles_list = []
    grouped_dimensions_list = []
    
    for idx, row in df_test.iterrows():
        file_name = row["Nazwa pliku"]
        typ = str(row["Typ"]).strip().lower()
        # Jeśli typ = "inside", obliczamy wymiary wewnętrzne (metodą compute_inside_dimensions)
        if typ == "inside":
            computed_dim = compute_inside_dimensions(file_name, df_odcinki)
            computed_dimensions_list.append(computed_dim)
        else:
            computed_dimensions_list.append("")
        
        # Obliczamy DC Shortening – korzystamy z funkcji compute_dc_shortening (bez duplikatów)
        dc_val = compute_dc_shortening(file_name, df_odcinki)
        dc_shortening_list.append(dc_val)
        
        # Obliczamy kąty gięcia z pliku XML
        angles_val = compute_bending_angles_from_xml(file_name)
        bending_angles_list.append(angles_val)
        
        # Grupujemy dane – dla każdego statycznego komponentu (WorkpieceComponentName)
        grouped_dims = compute_grouped_dimensions(file_name, df_odcinki)
        grouped_dimensions_list.append(grouped_dims)
    
    df_test["Wymiary wewnętrzne (test)"] = computed_dimensions_list
    df_test["DC Shortening (test)"] = dc_shortening_list
    df_test["Kąty gięcia (test)"] = bending_angles_list
    df_test["Grouped Dimensions (test)"] = grouped_dimensions_list
    
    try:
        df_test.to_excel("TESTY.xlsx", index=False)
        print("Plik TESTY.xlsx został zapisany.")
    except Exception as e:
        print("Błąd zapisu pliku TESTY.xlsx:", e)

if __name__ == "__main__":
    main()
