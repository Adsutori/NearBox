from django.http import JsonResponse
from .services import get_points_by_city


def simplify_points(points):
    simplified = []

    for p in points:
        simplified.append({
            "name": p.get("name"),
            "lat": p.get("location", {}).get("latitude"),
            "lng": p.get("location", {}).get("longitude"),
            "address": p.get("address", {}).get("line1"),
        })

    return simplified


def points_view(request):
    city = request.GET.get("city")

    if not city:
        return JsonResponse({"error": "City parameter is required"}, status=400)

    data = simplify_points(get_points_by_city(city))

    return JsonResponse(data, safe=False)