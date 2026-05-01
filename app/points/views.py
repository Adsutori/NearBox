from django.http import JsonResponse
from django.shortcuts import render
from .services import get_points_by_city
from .scoring import score_point
from .ai import recommend
from django.views.decorators.csrf import csrf_exempt


def simplify_points(points):
    simplified = []

    for p in points:
        simplified.append({
            "name":         p.get("name"),
            "lat":          p.get("location", {}).get("latitude"),
            "lng":          p.get("location", {}).get("longitude"),
            "address":      p.get("address", {}).get("line1"),
            "city":         p.get("address_details", {}).get("city"),
            "status":       p.get("status"),
            "opening_hours": p.get("opening_hours"),
            "image_url":    p.get("image_url"),
            "location_description": p.get("location_description"),
            "score":    score_point(p),
        })

    return simplified


def points_view(request):
    city = request.GET.get("city")

    if not city:
        return JsonResponse({"error": "City parameter is required"}, status=400)

    points = get_points_by_city(city)

    # Sortuje przed uproszczeniem
    points = sorted(points, key=lambda p: score_point(p), reverse=True)

    data = simplify_points(points)
    return JsonResponse(data, safe=False)


@csrf_exempt
def ai_recommend_view(request):
    """Osobny endpoint dla AI — POST żeby nie było query w URL."""
    if request.method != "POST":
        return JsonResponse({"error": "Tylko POST"}, status=405)

    import json
    body       = json.loads(request.body)
    user_query = body.get("query", "")
    city       = body.get("city", "")

    if not user_query or not city:
        return JsonResponse({"error": "Brak query lub city"}, status=400)

    points = get_points_by_city(city)
    points = sorted(points, key=lambda p: score_point(p), reverse=True)
    data   = simplify_points(points)

    response = recommend(user_query, data)
    return JsonResponse({"recommendation": response})