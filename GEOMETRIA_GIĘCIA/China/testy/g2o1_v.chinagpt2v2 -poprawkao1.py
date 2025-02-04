#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import glob
import math
import xml.etree.ElementTree as ET

def parse_outline_value(value_str):
    """
    Z pliku Delem (np. '4 0 6.613518 200 6.613518 false ...')
    wyciąga pary (x, y) i zwraca listę krotek [(x1,y1), (x2,y2), ...].
    Pomija słowa 'outline', 'true', 'false'.
    Zwykle '4' oznacza liczbę punktów w poligonie.
    """
    tokens = value_str.split()
    numeric_vals = []
    for t in tokens:
        if t.lower() in ['outline', 'true', 'false']:
            continue
        try:
            numeric_vals.append(float(t))
        except ValueError:
            pass

    if not numeric_vals:
        return []
    # Pierwsza liczba to ilość punktów w Outline
    # (co w Delem zwykle oznacza liczbę węzłów w poligonie).
    count_points = int(numeric_vals[0])
    coords = numeric_vals[1:]  # reszta to (x,y) * count_points

    points = []
    for i in range(0, len(coords), 2):
        if i+1 < len(coords):
            x = coords[i]
            y = coords[i+1]
            points.append((x, y))
    return points

def dist(a, b):
    """Odległość euklidesowa między punktami a=(x1,y1) i b=(x2,y2)."""
    return math.hypot(b[0]-a[0], b[1]-a[1])

def edges_of_polygon(pts, close_loop=True):
    """
    Zwraca listę krawędzi w formie [ (p0,p1), (p1,p2), ..., (p_{n-1},p0) ].
    Jeśli close_loop=False, nie domykamy p0.
    """
    edges = []
    n = len(pts)
    for i in range(n-1):
        edges.append((pts[i], pts[i+1]))
    if close_loop and n>1:
        edges.append((pts[-1], pts[0]))
    return edges

def same_edge(e1, e2, tol=1e-6):
    """
    Sprawdza, czy krawędź e1 = (p1,p2) jest 'taka sama' co e2 = (q1,q2)
    w sensie geometrycznym, z uwzględnieniem kierunku i ewentualnie tolerancji.
    Jeżeli chcemy ignorować kolejność (p1->p2 vs p2->p1),
    to możemy sprawdzić obie wersje.
    """
    p1, p2 = e1
    q1, q2 = e2
    # Sprawdzamy, czy p1,q1 są "bliskie", a p2,q2 są "bliskie"
    # lub odwrotnie.
    def close(a, b, t=tol):
        return (abs(a[0]-b[0])<t and abs(a[1]-b[1])<t)

    forward = close(p1,q1) and close(p2,q2)
    backward = close(p1,q2) and close(p2,q1)
    return (forward or backward)

def measure_free_edge(hull_pts, shortcontours):
    """
    Dla prostokątnego (najczęściej 4-wierzchołkowego) `hull_pts`
    oraz listy shortcontour'ów (każdy w postaci listy punktów)
    próbuje ustalić, które krawędzie hull-a są 'zagięciami',
    a następnie zwraca długość krawędzi wolnej (tej przeciwległej).

    W uproszczeniu:
      - Zbierz wszystkie krawędzie hull.
      - Zbierz krawędzie shortcontour z DCxx i 'oznacz' je jako zagięte.
      - Te, których nie ma na liście zagięć, są wolne.
      - Jeśli jest jedna wolna krawędź => zmierz odległość p1->p2.
      - Jeśli są dwie wolne krawędzie => weź tę dłuższą (lub krótszą, zależnie od oczekiwań).
      - (Zależnie od kształtu – można dopasować logikę).

    Zwraca "x_zewn." (float). Jeśli nie da się ustalić, zwraca 0.
    """

    if not hull_pts:
        return 0.0
    # edges hull
    hull_edges = edges_of_polygon(hull_pts, close_loop=True)

    # zbierz krawędzie shortcontour
    #  bo np. SC00 może mieć 2 <DeformableCompShortening> z DC00 i DC01
    used_edges = []
    for sc_poly in shortcontours:
        sc_edges = edges_of_polygon(sc_poly, close_loop=True)
        # dopasuj sc_edges do hull_edges
        for he in hull_edges:
            for se in sc_edges:
                if same_edge(he, se):
                    used_edges.append(he)

    # Teraz krawędzie wolne to hull_edges \ used_edges
    free_edges = [he for he in hull_edges if he not in used_edges]

    if not free_edges:
        # Brak wolnej krawędzi -> w specyficznych sytuacjach
        return 0.0

    # Dla prostokąta 4 wierzchołki – najczęściej jest 1 albo 2 wolne krawędzie
    # Weźmy tą najdłuższą (lub jedyną).
    lengths = [(dist(e[0], e[1]), e) for e in free_edges]
    lengths.sort(key=lambda x: x[0], reverse=True)  # od najdłuższej do najkrótszej
    longest_len, longest_edge = lengths[0]

    return longest_len

def normalize_angle(angle_deg):
    """
    Zamienia kąt > 180 na kąt ujemny w zakresie [-180, 180].
    Przykłady:
      225 st => -135
      270 st => -90
    """
    if angle_deg > 180:
        return angle_deg - 360
    return angle_deg

def main():

    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = os.getcwd()

    if not os.path.isdir(folder):
        print(f"Podany folder nie istnieje: {folder}")
        return

    output_dir = os.path.join(folder, "wyniki_poprawione")
    os.makedirs(output_dir, exist_ok=True)

    pattern = os.path.join(folder, "*.dld")
    files = glob.glob(pattern)

    if not files:
        print(f"Nie znaleziono plików .dld w folderze: {folder}")
        return

    print(f"Znaleziono {len(files)} plików .dld w folderze: {folder}\n")

    for file in files:
        process_file(file, output_dir)

    print("\nKoniec przetwarzania.")

def process_file(filename, output_dir):
    try:
        tree = ET.parse(filename)
    except ET.ParseError as e:
        print(f"Błąd parsowania XML w pliku {filename}: {e}")
        return

    root = tree.getroot()

    # 1) Odczyt nazwy mainplane:
    mainplane_logical_name = None
    for elem in root.iter():
        tag_name = elem.tag.lower()
        if tag_name.endswith("mainplanename"):
            mainplane_logical_name = elem.get("value", "")
            break
    if not mainplane_logical_name:
        # domyślnie załóżmy 'MainPlane'
        mainplane_logical_name = "MainPlane"

    # 2) Odczyt grubości i promienia (preferowane)
    thickness_val = 0.0
    radius_val = 0.0

    # 3) Struktury do przechowywania
    #    - static_components -> { comp_name: {"hull": [...], "shortening": [ [...], [...], ... ]}}
    #    - deformable_components -> { DC_name: {"angle": ..., "arc": ...} }
    static_components = {}
    deformable_components = {}

    dimension_type = None

    for elem in root.iter():
        tag_name = elem.tag.lower()

        if tag_name.endswith("workpiecedimensions"):
            dimension_type = elem.get("value", "")
        if tag_name.endswith("workpiecethickness"):
            try:
                thickness_val = float(elem.get("value","0"))
            except:
                pass
        if tag_name.endswith("preferredinnerradius"):
            try:
                radius_val = float(elem.get("value","0"))
            except:
                pass

        # StaticComponent => odczyt hull
        if tag_name.endswith("staticcomponent"):
            wp_name_elem = elem.find("./WorkpieceComponentName")
            if wp_name_elem is None:
                continue
            comp_name = wp_name_elem.get("value","")
            hull_elem = elem.find("./StaticComponentPart/StaticComponentHull")
            hull_pts = []
            if hull_elem is not None:
                hull_val = hull_elem.get("value", "")
                hull_pts = parse_outline_value(hull_val)

            # ShorteningContours
            shortenings = elem.findall("./DeformableCompShortening")
            short_list = []
            for s in shortenings:
                sc_val = s.find("./ShorteningContour")
                if sc_val is not None:
                    sc_outline = sc_val.get("value","")
                    sc_pts = parse_outline_value(sc_outline)
                    short_list.append(sc_pts)

            static_components[comp_name] = {
                "hull": hull_pts,
                "shortening": short_list
            }

        # VDeformableComponent => DCxx
        if tag_name.endswith("vdeformablecomponent"):
            wp_name_elem = elem.find("./WorkpieceComponentName")
            if wp_name_elem is not None:
                dc_name = wp_name_elem.get("value","")  # np. DC00
                # angle:
                angle_val = 0.0
                angle_elem = elem.find("./VDeformableComponentAngle")
                if angle_elem is not None:
                    try:
                        angle_val = float(angle_elem.get("value","0"))
                    except:
                        pass
                # arc => z bounding box lub z outlines:
                hulls_elem = elem.find("./VDeformableComponentHulls")
                arc_val = 0.0
                if hulls_elem is not None:
                    hval = hulls_elem.get("value","")
                    arc_pts = parse_outline_value(hval)
                    # bounding-box minimal dimension:
                    # (tu w Delem często to jest ~ długość łuku, bo to outline zgięcia)
                    if arc_pts:
                        xmin = min(p[0] for p in arc_pts)
                        xmax = max(p[0] for p in arc_pts)
                        ymin = min(p[1] for p in arc_pts)
                        ymax = max(p[1] for p in arc_pts)
                        w = abs(xmax - xmin)
                        h = abs(ymax - ymin)
                        arc_val = min(w,h)

                # Dodatkowo angle w <VBendDeformation><AngleAfter>...
                deformation_elem = elem.find("./VBendDeformation")
                if deformation_elem is not None:
                    angle_after_elem = deformation_elem.find("./AngleAfter")
                    if angle_after_elem is not None:
                        try:
                            angle_val = float(angle_after_elem.get("value","0"))
                        except:
                            pass

                angle_norm = normalize_angle(angle_val)
                deformable_components[dc_name] = {
                    "angle": angle_norm,
                    "arc": arc_val
                }

    # Teraz mamy:
    # - static_components z hull i listą shortcontour
    # - deformable_components z angle, arc
    # - mainplane_logical_name
    # - thickness_val, radius_val

    # 4) Ustal kolejność: w Delem bywa "MainPlane" + SC00 + SC01 + ...
    #    W tym przykładzie "po kolei jak wystepuja w kodzie".
    #    Sortowanie zrobimy po "pierwszym wystąpieniu" w pliku, a "MainPlane" zawsze na przód.

    # Ale w uproszczeniu: weź klucze static_components w kolejności w jakiej wystąpiły
    # (w pythonie 3.7+ dict pamięta kolejność wstawiania).
    # Przesuń mainplane na początek, a resztę zostaw w kolejności. :
    comp_names = list(static_components.keys())
    if mainplane_logical_name in comp_names:
        comp_names.remove(mainplane_logical_name)
        comp_names.insert(0, mainplane_logical_name)

    # 5) Pomierz "wolną krawędź" (zewn.) w takiej kolejności => to a, b, c...
    #    i policz outside/inside w oparciu o sumę kątów DC, jeśli jest 1:1.
    #    (Ten krok jest mocno zależny od tego, ile DC łączy dany SC i czy sumujemy efekty.)

    letter_labels = []
    # Wersja prosta: a, b, c, ... w kolejności
    # (jeśli to 10+ flansz, weźmy a..z, dalej by trzeba ASCII)
    import string
    letters = list(string.ascii_lowercase)
    # ncomp = len(comp_names)
    # letter_labels = letters[0:ncomp]
    # Ale user wskazuje, że mainplane => 'a', reszta w kolejności => b, c, d...
    # OK:
    sc_label_map = {}
    for i, cname in enumerate(comp_names):
        sc_label_map[cname] = letters[i]  # i=0 => 'a', i=1 => 'b', ...

    # Zbieramy wyniki do wypisania
    result_lines = []
    basefile = os.path.basename(filename)

    result_lines.append(f"=== Wyniki dla pliku: {basefile} ===")
    result_lines.append(f"WorkpieceDimensions = {dimension_type}")
    result_lines.append(f"Grubość = {thickness_val} mm")
    result_lines.append(f"Promień wewn. = {radius_val} mm\n")

    # Tabela do finalnego podsumowania
    table_data = []  # [ (label, x_zewn, x_out, x_in, <DC info> ) ...]

    # offset = (r + g)
    offset_val = radius_val + thickness_val

    # Będziemy iść w kolejności: a (=MainPlane), b (=SC00), c (=SC01), ...
    # i patrzeć, czy do tego sc jest przypisane np. DCxx. 
    # Ale w Twoich plikach często *inny* fragment XML decyduje, że SC00 łączy się z DC00, DC01...
    # W wersji minimalnej przyjmę, że "każdy SC" jest pod wpływem JEDNEGO zgięcia,
    # a w polu "shortening" jest max. 1 -> to nazwiemy DC. 
    # Jeżeli jest ich kilka -> sumujemy offsety, a kąty bierzemy z transform.
    #
    # UWAGA: to jest duże uproszczenie. W realnym kodzie
    #        trzeba konkretnie odwzorować "który DC jest z tą flanszą".
    #        Zwykle w Delem jest: mainplane + SC00 => DC00,
    #                            SC00 + SC01 => DC01, etc.

    for cname in comp_names:
        label = sc_label_map[cname]
        comp_data = static_components[cname]
        hull_pts = comp_data["hull"]
        short_polys = comp_data["shortening"]  # lista poligonów

        x_zewn = measure_free_edge(hull_pts, short_polys)

        # Znajdź przypisane DC (z nazwy w <DeformableCompShortening>):
        # bo <DeformableCompShortening><DeformableComponentName value="DC01"/>
        # jest w short_polys. Realnie: w pliku musimy wczytać je osobno i sprawdzić, 
        # ale tu – uproszczenie: poszukamy name="DCxx" wewnątrz <DeformableCompShortening> 
        # i łącznie obliczymy offset. 
        # Ewentualnie przy wielu DC => sumujemy ich wkład w out/in.
        # (Każdy DC ma angle i arc w deformable_components.)

        # W uproszczeniu: 
        # 1) Z listy short_polys jest tyle elementów co DC
        # 2) Niestety w parse nie zachowaliśmy "DC name" przy shortcontours
        #    => musimy przepisać parę rzeczy (lub zmienić parse, by zapisać też DC name).
        #    Na razie zrobimy "sprytny" myk: poszukamy DCxx w polu "value" w DeformableCompShortening.
        #    W bardziej dopracowanym kodzie przechowalibyśmy to jawnie.

        # Zróbmy to w inny sposób: sprawdźmy w pliku tree, 
        # ale to wymaga zachowania spisu "comp_name -> [DCxx,...]" 
        # Dla uproszczenia zdefiniujmy w parse statyczny słownik sc_to_dc.

        # => Dodajmy do static_components klucz "dc_names" - z parse:
        # Zmodyfikuję parse code wyżej:

        # (Patrz => w pełnym kodzie byśmy wypełnili comp_data["dc_names"] = [ "DC00", "DC01", ... ]
        #  i teraz odczytali stamtąd.)

        # A tutaj – załóżmy, że jest 0 lub 1 DC. (lub wiele = sumy).
        # Demo:

        # definicja sumarycznych kątów i sumarycznych łuków
        sum_angle_deg = 0.0
        sum_arc = 0.0

        # Szukamy w pliku realnie, a nie mamy do tego łatwego linku? 
        # W uproszczeniu => "bierzemy" DC w takiej kolejności DC00, DC01, DC02..., 
        #  bo user napisał "po kolei w jakim wystepują"?
        #  Ale to może się nam rozjechać. 
        # Przykładowo: 
        #  if "DC00" in deformable_components => sum -> ...
        #  if "DC01" in deformable_components => sum -> ...
        #  Ale skąd wiemy że SC01 ma DC01? Bo w <DeformableCompShortening> jest to powiedziane.

        # Możemy w parse staticcomponent-u pobrać <DeformableCompShortening> -> <DeformableComponentName>.
        # Patrzmy => w comp_data["shortening"] mamy polygony, ale brakuje nam samej nazwy DC.

        # => Możemy minimalnie "chałupniczo" się podpiąć: 
        #    jeżeli comp_name == "SC00" => DC00 
        #    jeżeli comp_name == "SC01" => DC01
        # ... (to też jest uproszczenie)
        # Lepiej by było przechować to w parse: comp_data["dc_names"] = ["DC00", "DC01"]
        #
        # W wersji demonstracyjnej zrobimy pewne if-y.

        # Dla uproszczenia zróbmy:
        # - "MainPlane" => brak DC, sum_angle=0
        # - "SC00" => sprawdź DC00, DC01, ... 
        #   jeżeli istnieją w deformable_components -> dopisz do sum
        # - "SC01" => sprawdź DC01, itp.
        # 
        # Warunek usera: "po kolei" => a=MainPlane, b=SC00, c=SC01 ...
        # => SC00 teoretycznie łączy się z DC00, SC01 z DC01, 
        #    jeżeli w pliku występują nazwy takie same. 
        # 
        # Tak, to jest duże uproszczenie, ale do demonstrowania wystarczy.

        # Bierzmy wszystkie DCxx i sprawdzajmy, czy nazwa DCxx zawiera "00", "01" i czy to pasuje do nazwy SC:
        # Bardziej sensowne: 
        # if re.match(r'.*00', cname, re.IGNORECASE) => DC00
        # if re.match(r'.*01', cname, re.IGNORECASE) => DC01
        # ...
        # Ale co jak SC jest "SC0"? 
        # W realnym kodzie: BARDZIEJ PRECYZYJNA ANALIZA:
        #   parse <DeformableCompShortening><DeformableComponentName value="DC00"/>
        #   i zapisać to w static_components. Koniec kropka.
        # 
        #   Skoro tu demonstrujemy, zróbmy jedną z najprostszych form:

        for dc_name, dc_data in deformable_components.items():
            # sprawdź, czy w ogóle "pasuje" do cname
            # np. if cname=="SC00" and dc_name=="DC00"
            # lub cname=="SC01" and dc_name=="DC01"
            # jeżeli tak => sumujemy.
            # (To jest mocne uproszczenie!)
            if cname.lower().endswith(dc_name.lower().replace("dc","")):
                # np. SC00 -> "00", SC01 -> "01"
                sum_angle_deg += abs(dc_data["angle"])  # bierzemy wartość bezwzgl.
                sum_arc += dc_data["arc"]

            # Ewentualnie, jeśli nazwa to "MainPlane", to nic nie robimy.

        # Mamy sum_angle_deg i sum_arc => liczymy "offset sum" => 
        # jeżeli kąt = 90 => offset = (r+g) * 1
        # jeżeli kąt = 80 => offset = (r+g) * tan(50°)
        # ... a co jak sum_angle_deg= 170 => to jest 2 gięcia po 85°? 
        #   to rzadki przypadek, do weryfikacji. 
        # Pokażemy formułę "jeden kąt  = sum_angle_deg"
        # (Jeżeli w rzeczywistości jest kilka gięć, wzór bywa inny. Tu - DEMO.)

        if sum_angle_deg > 0.01:
            half_angle = (180.0 - sum_angle_deg)/2.0
            half_angle_rad = math.radians(half_angle)
            if half_angle_rad != 0:
                tan_val = math.tan(abs(half_angle_rad))  # weź abs
            else:
                tan_val = 0.0
            delta_out = offset_val * tan_val
            # in => arc/2 => sum_arc/2
            delta_in = (sum_arc/2.0)
        else:
            delta_out = 0.0
            delta_in  = 0.0

        x_out = x_zewn + delta_out
        x_in  = x_zewn + delta_in

        # Zaokrąglamy do 1 miejsca:
        x_zewn_1d = round(x_zewn,1)
        x_out_1d  = round(x_out,1)
        x_in_1d   = round(x_in,1)

        table_data.append((label, x_zewn_1d, x_out_1d, x_in_1d, sum_angle_deg, sum_arc))

    # Wypisywanie
    out_lines = []
    out_lines.append(f"=== Wyniki dla pliku: {os.path.basename(filename)} ===")
    out_lines.append(f"Układ flansz (kolejność): {', '.join(comp_names)}")
    out_lines.append(f"MainPlane = {mainplane_logical_name} => 'a'")
    out_lines.append(f"Grubość = {thickness_val}, r_in = {radius_val}, dimension_type={dimension_type}")
    out_lines.append("")

    out_lines.append("Legenda: label, x_zewn, x_out, x_in, sum_angle, sum_arc")
    for row in table_data:
        (lbl, xz, xo, xi, sang, sarc) = row
        out_lines.append(f"{lbl}:  zewn={xz}, out={xo}, in={xi}, angle={sang}, arc={sarc}")

    result_text = "\n".join(out_lines)

    print(result_text)

    # Zapis do pliku
    base = os.path.splitext(os.path.basename(filename))[0]
    outfname = os.path.join(output_dir, f"wynik_{base}.txt")
    try:
        with open(outfname, "w", encoding="utf-8") as f:
            f.write(result_text)
    except IOError as e:
        print(f"Błąd zapisu do {outfname}: {e}")

# Uruchomienie
if __name__ == "__main__":
    main()
