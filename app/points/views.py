from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from .services import get_points_by_city, get_points_by_city_stream, get_points_by_location
from .ai import recommend
import json
import math


# ══════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════

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
            # ── pola potrzebne do filtrowania client-side ──
            "type":                 p.get("type", []),
            "location_type":        p.get("location_type", ""),
            "easy_access_zone":     p.get("easy_access_zone", False),
        })
    return simplified


def get_filters_from_request(request):
    return {
        "only_locker":      request.GET.get("only_locker")      == "true",
        "only_247":         request.GET.get("only_247")          == "true",
        "only_operating":   request.GET.get("only_operating")    == "true",
        "only_outdoor":     request.GET.get("only_outdoor")      == "true",
        "only_easy_access": request.GET.get("only_easy_access")  == "true",
    }


# ══════════════════════════════════════════
#  WIDOKI
# ══════════════════════════════════════════

def _haversine(lat1, lng1, lat2, lng2) -> float:
    R    = 6371
    dlat = math.radians(float(lat2) - float(lat1))
    dlng = math.radians(float(lng2) - float(lng1))
    a    = (math.sin(dlat / 2) ** 2 +
            math.cos(math.radians(float(lat1))) *
            math.cos(math.radians(float(lat2))) *
            math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))

def points_view(request):
    city = request.GET.get("city", "")
    lat  = request.GET.get("lat")
    lng  = request.GET.get("lng")

    if lat and lng:
        points = get_points_by_location(float(lat), float(lng))
    else:
        points = get_points_by_city(city)

    filters = get_filters_from_request(request)
    points  = filter_points(points, filters)
    result  = simplify_points(points)

    # Sortuj po odległości od usera — żeby slice(0,3) dało naprawdę najbliższe
    if lat and lng:
        ref_lat, ref_lng = float(lat), float(lng)

        def dist(p):
            if not p.get("lat") or not p.get("lng"):
                return 9999
            return _haversine(ref_lat, ref_lng, p["lat"], p["lng"])

        result.sort(key=dist)
        print(f"[VIEW] Posortowano {len(result)} punktów. Top 3: {[p['name'] for p in result[:3]]}", flush=True)

    return JsonResponse(result, safe=False)


@require_GET
def points_stream_view(request):
    """
    SSE endpoint — streamuje postęp pobierania paczkomatów strona po stronie.
    Frontend odbiera eventy z polami: found, page, total_pages, done, points.
    """
    city    = request.GET.get("city", "").strip()
    filters = get_filters_from_request(request)

    def event_stream():
        last_points = []

        try:
            for points, page, total_pages in get_points_by_city_stream(city):
                last_points = points

                payload = json.dumps({
                    "found":       len(points),
                    "page":        page,
                    "total_pages": total_pages,
                    "done":        False,
                })
                yield f"data: {payload}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
            return

        # Wszystkie strony pobrane — zastosuj filtry i wyślij finalne dane
        filtered  = filter_points(last_points, filters)
        final     = json.dumps({
            "found":       len(filtered),
            "page":        1,
            "total_pages": 1,
            "done":        True,
            "points":      simplify_points(last_points),
        })
        yield f"data: {final}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream"
    )
    response["Cache-Control"]     = "no-cache"
    response["X-Accel-Buffering"] = "no"   # wyłącza buforowanie nginx
    return response


@csrf_exempt
def ai_recommend_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Tylko POST"}, status=405)

    body       = json.loads(request.body)
    user_query = body.get("query", "")
    city       = body.get("city", "")
    lat        = body.get("lat")
    lng        = body.get("lng")

    if not user_query:
        return JsonResponse({"error": "Brak query"}, status=400)

    if lat and lng:
        # Mamy GPS — pobierz tylko najbliższe 25 przez API lokalizacyjne
        points = get_points_by_location(float(lat), float(lng), radius=5)
    elif city:
        # Pobierz wszystkie dla miasta (teraz równolegle — szybko)
        points = get_points_by_city(city)
    else:
        return JsonResponse({"error": "Brak city lub lokalizacji"}, status=400)

    # Ogranicz do 25 punktów przed wysłaniem do AI
    # (ai.py i tak sortuje po odległości — weźmie top 5 do prompta)
    data = simplify_points(points[:100])   # max 100 do sortowania, AI weźmie top 5

    response = recommend(user_query, data, city, lat=lat, lng=lng)
    return JsonResponse({"recommendation": response})
