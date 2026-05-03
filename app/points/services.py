# import requests

# def get_points_by_city(city):
#     if not city:
#         return []

#     all_points = []
#     page = 1

#     while True:
#         url = f"https://api-global-points.easypack24.net/v1/points?city={city}&page={page}"

#         try:
#             response = requests.get(url, timeout=5)
#             response.raise_for_status()
#             data = response.json()
#         except requests.RequestException:
#             break

#         items = data.get("items", [])
#         meta = data.get("meta", {})

#         all_points.extend(items)

#         if page >= meta.get("total_pages", 1):
#             break

#         page += 1

#     return all_points


# def get_points_by_location(lat, lng, radius=5):
#     url = "https://api-global-points.easypack24.net/v1/points"
#     params = {
#         "relative_point": f"{lat},{lng}",
#         "max_distance": radius,
#         "per_page": 25,
#         "page": 1
#     }
#     response = requests.get(url, params=params, timeout=5)
#     response.raise_for_status()
#     data = response.json()
#     return data.get("items", [])


import requests

def get_points_by_city(city):
    if not city:
        return []

    all_points = []
    page = 1

    while True:
        url = f"https://api-global-points.easypack24.net/v1/points?city={city}&page={page}"

        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            break

        items = data.get("items", [])
        meta  = data.get("meta", {})

        all_points.extend(items)

        if page >= meta.get("total_pages", 1):
            break

        page += 1

    return all_points


def get_points_by_city_stream(city):
    """
    Generator — yielda (items_so_far, total_pages, current_page) po każdej stronie.
    Używany przez SSE endpoint.
    """
    if not city:
        return

    all_points = []
    page       = 1

    while True:
        url = (
            f"https://api-global-points.easypack24.net/v1/points"
            f"?city={city}&page={page}"
        )

        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            break

        items       = data.get("items", [])
        meta        = data.get("meta", {})
        total_pages = meta.get("total_pages", 1)

        all_points.extend(items)

        yield all_points[:], page, total_pages   # kopia listy

        if page >= total_pages:
            break

        page += 1


def get_points_by_location(lat, lng, radius=5):
    url    = "https://api-global-points.easypack24.net/v1/points"
    params = {
        "relative_point": f"{lat},{lng}",
        "max_distance":   radius,
        "per_page":       25,
        "page":           1
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        print(f"[SERVICES] URL: {response.url}", flush=True)
        print(f"[SERVICES] Status: {response.status_code}", flush=True)
        print(f"[SERVICES] Body: {response.text[:300]}", flush=True)
        response.raise_for_status()
        data  = response.json()
        items = data.get("items", [])
        print(f"[SERVICES] relative_point: {len(items)} punktów", flush=True)

        if items:
            return items

        # ── FALLBACK: API nie zwróciło nic — pobierz przez miasto ──
        print("[SERVICES] Fallback: szukam przez miasto z Nominatim", flush=True)
        return _get_points_near_coords_fallback(lat, lng)

    except requests.RequestException as e:
        print(f"[SERVICES] Błąd: {e}", flush=True)
        return _get_points_near_coords_fallback(lat, lng)


def _get_points_near_coords_fallback(lat, lng):
    """
    Pobiera nazwę miasta z Nominatim, potem punkty przez get_points_by_city.
    Zwraca punkty posortowane po odległości od (lat, lng).
    """
    import math

    # 1. Reverse geocoding — znajdź miasto
    try:
        res = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lng, "format": "json"},
            headers={"User-Agent": "NearBox/1.0"},
            timeout=5
        )
        addr = res.json().get("address", {})
        city = (addr.get("city") or addr.get("town") or
                addr.get("village") or addr.get("county") or "")
        print(f"[SERVICES] Fallback miasto: '{city}'", flush=True)
    except Exception as e:
        print(f"[SERVICES] Nominatim error: {e}", flush=True)
        return []

    if not city:
        return []

    # 2. Pobierz punkty przez miasto
    points = get_points_by_city(city)
    print(f"[SERVICES] Fallback: pobrano {len(points)} punktów dla '{city}'", flush=True)

    # 3. Posortuj po odległości od GPS usera
    def haversine(p):
        p_lat = p.get("location", {}).get("latitude")
        p_lng = p.get("location", {}).get("longitude")
        if not p_lat or not p_lng:
            return 9999
        R    = 6371
        dlat = math.radians(float(p_lat) - float(lat))
        dlng = math.radians(float(p_lng) - float(lng))
        a    = (math.sin(dlat / 2) ** 2 +
                math.cos(math.radians(float(lat))) *
                math.cos(math.radians(float(p_lat))) *
                math.sin(dlng / 2) ** 2)
        return R * 2 * math.asin(math.sqrt(a))

    points.sort(key=haversine)
    print(f"[SERVICES] Fallback top3: {[p.get('name') for p in points[:3]]}", flush=True)
    return points
