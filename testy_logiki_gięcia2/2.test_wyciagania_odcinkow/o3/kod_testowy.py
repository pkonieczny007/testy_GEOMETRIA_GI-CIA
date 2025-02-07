import pandas as pd

def compute_inside_dimensions(file_name, df_odcinki):
    """
    Dla danego pliku (Nazwa pliku) z wyniki_odcinki_v3.xlsx
    pobiera wiersze dla odcinek nr 2 i dzieli je na:
      - bazowe wartości (z StaticComponentHull),
      - wartości DC (z ShorteningContour) – dla komponentów zaczynających się od "DC".
    Następnie, przyjmując, że liczba wartości bazowych = n, wylicza nowe wymiary wg:
      * Jeśli n == 2 i jest 1 wartość DC:
             new[0] = baza[0] + DC[0]
             new[1] = baza[1] + DC[0]
      * Jeśli n > 2 i liczba wartości DC = n - 1:
             new[0] = baza[0] + DC[0]
             dla i = 1..n-2: new[i] = DC[i-1] + baza[i] + DC[i]
             new[n-1] = baza[-1] + DC[-1]
    Zwraca ciąg liczb (oddzielonych przecinkiem) z wartościami zaokrąglonymi do 6 miejsc.
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
            
    # Pobieramy wartości DC z ShorteningContour, dla których "Komponent" zaczyna się od "DC"
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
        # Jeśli nie pasuje do oczekiwanego schematu, zwracamy bazowe wartości
        computed_dims = base_values
    
    return ",".join(str(round(x, 6)) for x in computed_dims)

def compute_dc_shortening(file_name, df_odcinki):
    """
    Dla danego pliku (Nazwa pliku) z wyniki_odcinki_v3.xlsx
    pobiera wiersze dla odcinek nr 2, dla których:
      - "Źródło outline" = "ShorteningContour"
      - "Komponent" zaczyna się od "DC"
    Zwraca ciąg w postaci "DC00=<value>, DC01=<value>, ..." gdzie <value> to wartość "Długość łuku"
    zaokrąglona do 6 miejsc.
    """
    df_file = df_odcinki[df_odcinki["Nazwa pliku"] == file_name]
    df_dc = df_file[(df_file["Odcinek nr"] == 2) &
                    (df_file["Źródło outline"] == "ShorteningContour") &
                    (df_file["Komponent"].str.startswith("DC"))]
    dc_items = []
    for _, row in df_dc.iterrows():
        comp = row["Komponent"]
        try:
            val = float(str(row["Długość łuku"]).replace(',', '.'))
            dc_items.append(f"{comp}={round(val, 6)}")
        except:
            pass
    return ", ".join(dc_items)

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
    
    for idx, row in df_test.iterrows():
        file_name = row["Nazwa pliku"]
        typ = str(row["Typ"]).strip().lower()
        # Jeśli typ to "inside" – obliczamy nowe wymiary (można też modyfikować dla innych typów)
        if typ == "inside":
            computed_dim = compute_inside_dimensions(file_name, df_odcinki)
            computed_dimensions_list.append(computed_dim)
        else:
            computed_dimensions_list.append("")
        
        # Obliczamy wartości DC shortening dla odcinka nr 2
        dc_val = compute_dc_shortening(file_name, df_odcinki)
        dc_shortening_list.append(dc_val)
    
    df_test["Wymiary wewnętrzne (test)"] = computed_dimensions_list
    df_test["DC Shortening"] = dc_shortening_list
    
    try:
        df_test.to_excel("TESTY.xlsx", index=False)
        print("Plik TESTY.xlsx został zapisany.")
    except Exception as e:
        print("Błąd zapisu pliku TESTY.xlsx:", e)

if __name__ == "__main__":
    main()
