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
        meta = data.get("meta", {})

        all_points.extend(items)

        if page >= meta.get("total_pages", 1):
            break

        page += 1

    return all_points


def get_points_by_location(lat, lng, radius=5):
    url = "https://api-global-points.easypack24.net/v1/points"
    params = {
        "relative_point": f"{lat},{lng}",
        "max_distance": radius,
        "per_page": 25,
        "page": 1
    }
    response = requests.get(url, params=params, timeout=5)
    response.raise_for_status()
    data = response.json()
    return data.get("items", [])