import math

def oblicz_prostke(odcinki, grubosc, katy, promien_wewn):
    """
    Oblicza długość rozwinięcia (prostki) dla giętej blachy.
    
    Parametry:
      - odcinki: lista długości zewnętrznych odcinków (np. [200, 50] lub [200, 50, 30])
      - grubosc: grubość blachy (np. 2 lub 3)
      - katy: lista kątów gięcia w stopniach (np. [90] lub [90, 80])
      - promien_wewn: promień wewnętrzny gięcia
      
    Zwraca:
      - Całkowitą długość rozwinięcia (prostki)
    """
    # Przyjmujemy, że włókno obojętne znajduje się w połowie grubości
    wspolczynnik_neutralny = 0.5  
    promien_neutralny = promien_wewn + wspolczynnik_neutralny * grubosc

    # Długość wszystkich prostych odcinków (podawanych jako "zewnętrzne" długości)
    dlugosc_odcinkow = sum(odcinki)

    # Długość łuków gięcia: suma (kąt [w radianach] * promień_neutralny) dla każdego gięcia
    dlugosc_lukow = sum(math.radians(kat) * promien_neutralny for kat in katy)
    
    return dlugosc_odcinkow + dlugosc_lukow

# Przykłady użycia:
# Przykład 1: "200x50, grubość 2, kąt 90°", przyjmując promień wewnętrzny = 2
prostka1 = oblicz_prostke([200, 50], 2, [90], 2)

# Przykład 2: "200x50x30, grubość 3, kąty 90° i 80°", przyjmując promień wewnętrzny = 3
prostka2 = oblicz_prostke([200, 50, 30], 3, [90, 80], 3)

print("Długość prostki (200x50, grubość 2, kąt 90°): {:.2f} mm".format(prostka1))
print("Długość prostki (200x50x30, grubość 3, kąty 90° i 80°): {:.2f} mm".format(prostka2))
