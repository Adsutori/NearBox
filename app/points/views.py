from django.http import JsonResponse
from django.shortcuts import render
from .services import get_points_by_city, get_points_by_location
from .ai import recommend
from django.views.decorators.csrf import csrf_exempt
import json


def filter_points(points, filters):
    """Filtruje surowe punkty z API InPost (przed simplify)."""
    result = []
    for p in points:
        if filters.get("only_locker") and "parcel_locker" not in p.get("type", []):
            continue
        if filters.get("only_247") and "24/7" not in str(p.get("opening_hours", "")):
            continue
        if filters.get("only_operating") and p.get("status") != "Operating":
            continue
        if filters.get("only_outdoor") and p.get("location_type") != "Outdoor":
            continue
        if filters.get("only_easy_access") and not p.get("easy_access_zone"):
            continue
        result.append(p)
    return result


def simplify_points(points):
    """Spłaszcza surowe dane API do formatu używanego przez frontend."""
    simplified = []
    for p in points:
        simplified.append({
            "name":                 p.get("name"),
            "lat":                  p.get("location", {}).get("latitude"),
            "lng":                  p.get("location", {}).get("longitude"),
            "address":              p.get("address", {}).get("line1"),
            "city":                 p.get("address_details", {}).get("city"),
            "status":               p.get("status"),
            "opening_hours":        p.get("opening_hours"),
            "image_url":            p.get("image_url"),
            "location_description": p.get("location_description"),
        })
    return simplified


def points_view(request):
    city = request.GET.get("city", "")
    lat  = request.GET.get("lat")
    lng  = request.GET.get("lng")

    # Pobierz surowe punkty
    if lat and lng:
        points = get_points_by_location(float(lat), float(lng))
    else:
        points = get_points_by_city(city)

    # Filtruj na surowych danych (mają type, status, location_type itd.)
    filters = {
        "only_locker":      request.GET.get("only_locker") == "true",
        "only_247":         request.GET.get("only_247") == "true",
        "only_operating":   request.GET.get("only_operating") == "true",
        "only_outdoor":     request.GET.get("only_outdoor") == "true",
        "only_easy_access": request.GET.get("only_easy_access") == "true",
    }
    points = filter_points(points, filters)

    # Dopiero teraz spłaszcz do formatu frontendowego
    return JsonResponse(simplify_points(points), safe=False)  # lista, nie dict


@csrf_exempt
def ai_recommend_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Tylko POST"}, status=405)

    body       = json.loads(request.body)
    user_query = body.get("query", "")
    city       = body.get("city", "")

    if not user_query or not city:
        return JsonResponse({"error": "Brak query lub city"}, status=400)

    points = get_points_by_city(city)
    data   = simplify_points(points)

    response = recommend(user_query, data, city)
    return JsonResponse({"recommendation": response})
