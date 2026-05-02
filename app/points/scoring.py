# nie uzywane - zostawiam poki co jako backup

def score_point(p):
    score = 0

    # Paczkomat > punkt obsługi
    if "parcel_locker" in p.get("type", []):
        score += 3

    # Czynny 24/7
    if "24/7" in str(p.get("opening_hours", "")):
        score += 3

    # Aktywny status
    if p.get("status") == "Operating":
        score += 2

    # Na zewnątrz = łatwiej dostępny
    if p.get("location_type") == "Outdoor":
        score += 1

    # Strefa łatwego dostępu
    if p.get("easy_access_zone"):
        score += 1

    return score
