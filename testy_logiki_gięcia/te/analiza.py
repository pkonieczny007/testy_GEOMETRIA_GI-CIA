import os
import re

def extract_points_from_file(filepath):
    """
    Ekstrakcja wartości StaticComponentHull i ShorteningContour z pliku.
    """
    with open(filepath, 'r', encoding='utf-8') as file:
        data = file.read()
    static_component_hull = re.search(r'<StaticComponentHull .*?value="([^"]+)"', data)
    shortening_contour = re.search(r'<ShorteningContour .*?value="([^"]+)"', data)

    hull = static_component_hull.group(1) if static_component_hull else "Brak danych"
    contour = shortening_contour.group(1) if shortening_contour else "Brak danych"

    return hull, contour


def main():
    # Katalog, w którym znajduje się skrypt
    current_directory = os.path.dirname(os.path.abspath(__file__))
    result = []

    # Przeszukiwanie plików .dld w katalogu
    for filename in os.listdir(current_directory):
        if filename.endswith('.dld'):
            filepath = os.path.join(current_directory, filename)
            hull, contour = extract_points_from_file(filepath)
            result.append((filename, hull, contour))

    # Generowanie raportu
    output = []
    for filename, hull, contour in result:
        output.append(f"{filename}\nStaticComponentHull\n{hull}\nShorteningContour\n{contour}\n")

    # Zapis wyników do pliku lub wyświetlenie w konsoli
    output_text = "\n".join(output)
    print(output_text)  # Wyświetlenie w konsoli
    with open("results.txt", "w", encoding="utf-8") as result_file:
        result_file.write(output_text)  # Zapis do pliku results.txt


if __name__ == "__main__":
    main()
