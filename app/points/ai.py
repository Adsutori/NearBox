import os
import requests
import math
import json
import re
from openai import OpenAI, OpenAIError

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

# ─────────────────────────────────────────────
#  KROK 1 — GPT wyciąga nazwę miejsca z zapytania
# ─────────────────────────────────────────────

def _extract_location_ai(user_query: str, city: str, client: OpenAI) -> str | None:
    """
    GPT wyciąga z zapytania punkt odniesienia (miejsce, obiekt, ulicę)
    i od razu wzbogaca go o nazwę miasta — gotowy do geokodowania.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Użytkownik szuka paczkomatu w mieście {city}. "
                        "Twoim zadaniem jest wyciągnięcie z zapytania PUNKTU ODNIESIENIA — "
                        "czyli miejsca, obiektu lub ulicy, w pobliżu której szuka paczkomatu. "
                        "\n\nPrzykłady:\n"
                        "'paczkomat obok pkp' → 'PKP " + city + "'\n"
                        "'paczkomat blisko sklepu aldi' → 'Aldi " + city + "'\n"
                        "'paczkomat przy dworcu' → 'dworzec PKP " + city + "'\n"
                        "'paczkomat na osiedlu kopernika' → 'osiedle Kopernika " + city + "'\n"
                        "'paczkomat przy ul. Królewskiej' → 'ul. Królewska " + city + "'\n"
                        "'paczkomat możliwie najbliżej stawów walczewskiego' → 'stawy Walczewskiego " + city + "'\n"
                        "\nZasady:\n"
                        "1. Zawsze dołącz nazwę miasta na końcu.\n"
                        "2. Odpowiedz TYLKO nazwą miejsca z miastem — bez żadnego innego tekstu.\n"
                        "3. Jeśli zapytanie nie zawiera ŻADNEGO punktu odniesienia "
                        "(np. 'daj mi jakiś paczkomat', 'dowolny paczkomat'), "
                        "odpowiedz dokładnie: NULL"
                    )
                },
                {
                    "role": "user",
                    "content": user_query
                }
            ],
            max_tokens=40,
            temperature=0,
        )
        result = response.choices[0].message.content.strip()
        print(f"[AI] GPT raw response: '{result}'", flush=True)

        if result.upper() in ("NULL", "NONE", "NIL", "BRAK", ""):
            return None

        return result

    except OpenAIError as e:
        print(f"[AI] OpenAI API error w _extract_location_ai: {e}", flush=True)
        return None
    except Exception as e:
        print(f"[AI] Nieoczekiwany błąd w _extract_location_ai: {e}", flush=True)
        return None
    

# ─────────────────────────────────────────────
#  KROK 2 — Google Geocoding API
# ─────────────────────────────────────────────

def _geocode_google(location_name: str, city: str) -> tuple[float, float, bool] | None:
    """
    Geokoduje nazwę miejsca przez Google Geocoding API.

    Zwraca (lat, lon, is_precise) gdzie:
      - is_precise = True  → Google znalazł konkretny obiekt
      - is_precise = False → Google zwrócił tylko miasto (partial_match lub result_type=locality)

    Zwraca None jeśli Google nic nie znalazł.
    """
    if not GOOGLE_MAPS_API_KEY:
        raise ValueError("Brak GOOGLE_MAPS_API_KEY w zmiennych środowiskowych.")

    query = f"{location_name}, {city}" if city else location_name

    try:
        res = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={
                "address": query,
                "key": GOOGLE_MAPS_API_KEY,
                "language": "pl",
            },
            timeout=5,
        )
        data = res.json()
    except Exception as e:
        print(f"[GEOCODE] Błąd połączenia z Google: {e}", flush=True)
        return None

    if data.get("status") != "OK" or not data.get("results"):
        print(f"[GEOCODE] Google nie znalazł: '{query}' — status: {data.get('status')}", flush=True)
        return None

    result = data["results"][0]
    loc    = result["geometry"]["location"]
    lat    = float(loc["lat"])
    lon    = float(loc["lng"])

    # Sprawdź czy Google zwrócił konkretny obiekt czy tylko miasto/region
    result_types    = result.get("types", [])
    is_partial      = result.get("partial_match", False)
    vague_types     = {"locality", "administrative_area_level_1",
                       "administrative_area_level_2", "country", "postal_code"}
    is_precise      = not is_partial and not bool(vague_types & set(result_types))

    print(
        f"[GEOCODE] Google: '{query}' → ({lat:.5f}, {lon:.5f}) | "
        f"types={result_types} | partial={is_partial} | precise={is_precise}",
        flush=True
    )

    return lat, lon, is_precise


# ─────────────────────────────────────────────
#  KROK 3 — Haversine
# ─────────────────────────────────────────────

def _distance_km(lat1, lon1, lat2, lon2) -> float:
    """Haversine — odległość w km między dwoma punktami."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# ─────────────────────────────────────────────
#  KROK 4 — Sortowanie paczkomatów
# ─────────────────────────────────────────────

def _sort_by_location(
    user_query: str,
    points: list,
    city: str,
    client: OpenAI
) -> tuple[list, tuple[float, float] | None, bool]:
    """
    Sortuje paczkomaty wg odległości od miejsca z zapytania.

    Zwraca (posortowana_lista, coords, is_precise).
    Jeśli geokodowanie zawiodło — zwraca oryginalną listę, None, False.
    """

    # Krok 1 — GPT wyciąga nazwę miejsca
    location_name = _extract_location_ai(user_query, city, client) if client else None
    print(f"[AI] Wyciągnięta nazwa miejsca: '{location_name}'", flush=True)

    # Krok 2 — Google geokoduje
    coords = None
    is_precise = False

    if location_name:
        result = _geocode_google(location_name, city)
        if result:
            lat, lon, is_precise = result
            coords = (lat, lon)

    # Fallback — jeśli GPT zwrócił NULL lub Google nic nie znalazł,
    # próbujemy geokodować samo miasto
    if not coords:
        result = _geocode_google(city, "")
        if result:
            lat, lon, _ = result
            coords = (lat, lon)
            is_precise = False
            print(f"[GEOCODE] Fallback do centrum miasta: {coords}", flush=True)

    if not coords:
        return points, None, False

    # Krok 3 — Haversine dla każdego paczkomatu
    lat, lon = coords
    for p in points:
        p_lat = p.get("lat")
        p_lon = p.get("lng")
        p["_dist"] = (
            _distance_km(lat, lon, float(p_lat), float(p_lon))
            if p_lat and p_lon else 9999
        )

    return sorted(points, key=lambda p: p["_dist"]), coords, is_precise


# ─────────────────────────────────────────────
#  GŁÓWNA FUNKCJA
# ─────────────────────────────────────────────

def recommend(user_query: str, points: list, city: str = "") -> str:
    client = OpenAI()

    sorted_points, coords, is_precise = _sort_by_location(
        user_query, points, city, client
    )

    # ── DEBUG ────────────────────────────────
    print(f"\n{'='*50}", flush=True)
    print(f"[DEBUG] query      = '{user_query}'", flush=True)
    print(f"[DEBUG] city       = '{city}'", flush=True)
    print(f"[DEBUG] coords     = {coords}", flush=True)
    print(f"[DEBUG] is_precise = {is_precise}", flush=True)
    print(f"[DEBUG] top5 dists = {[round(p.get('_dist', 9999), 2) for p in sorted_points[:5]]}", flush=True)
    print(f"[DEBUG] top5 names = {[p.get('name') for p in sorted_points[:5]]}", flush=True)
    print(f"{'='*50}\n", flush=True)
    # ── KONIEC DEBUG ─────────────────────────

    top_points = sorted_points[:5]

    points_text = "\n".join([
        f"- {p['name']} | {p['address']} | "
        f"status: {p['status']} | godziny: {p.get('opening_hours', '?')} | "
        f"odległość: {p.get('_dist', 9999):.2f} km"
        for p in top_points
    ])

    # Jeśli geokodowanie było nieprecyzyjne — poinformuj GPT
    geocode_note = (
        "UWAGA: Nie udało się zlokalizować konkretnego miejsca z zapytania — "
        "paczkomaty są posortowane wg centrum miasta, nie wg podanego miejsca. "
        "Poinformuj o tym użytkownika krótko i naturalnie."
        if not is_precise and coords
        else ""
    )

    messages = [
        {
            "role": "system",
            "content": (
                "Jesteś pomocnym asystentem InPost. "
                "Pomagasz użytkownikom znaleźć najlepszy paczkomat. "
                "Odpowiadaj w tym samym języku co zapytanie użytkownika. "
                "Bądź konkretny i zwięzły — maksymalnie 3-4 zdania. "
                "Opieraj się WYŁĄCZNIE na danych z listy paczkomatów — "
                "nie wymyślaj lokalizacji ani odległości. "
                f"{geocode_note}"
            )
        },
        {
            "role": "user",
            "content": (
                f"Zapytanie: {user_query}\n"
                f"Miasto: {city}\n\n"
                f"Najbliższe paczkomaty (posortowane wg odległości od szukanego miejsca):\n"
                f"{points_text}\n\n"
                "Poleć najlepszą opcję. Podaj nazwę i adres. "
                "Jeśli odległość jest większa niż 1 km, wspomnij o tym."
            )
        }
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=300,
            temperature=0.4,
            timeout=15,
        )
        return response.choices[0].message.content

    except OpenAIError as e:
        return f"❌ Błąd AI: {str(e)}"
    except Exception as e:
        return f"❌ Nieoczekiwany błąd: {str(e)}"


# # BIELIK (nie mogę podpiąć bo darmowy plan na hugging face go nie obejmuje a ollama za dużo waży😭)
# import os
# import requests

# # ── OPCJA A: Hugging Face Inference API (bezpłatne, wymaga tokenu) ──
# HF_TOKEN  = os.environ.get("HF_TOKEN")
# HF_MODEL  = "speakleash/Bielik-7B-Instruct-v0.1"
# HF_URL   = f"https://api-inference.huggingface.co/models/{HF_MODEL}/v1/chat/completions"

# def recommend_hf(user_query: str, points: list) -> str:
#     """Rekomendacja przez Hugging Face Inference API."""

#     top = points[:8]  # bierzemy top 8 żeby nie przepalać tokenów

#     points_text = "\n".join([
#         f"- {p['name']} | {p['address']}, {p['city']} | "
#         f"status: {p['status']} | godziny: {p.get('opening_hours','?')} | "
#         f"score: {p.get('score', 0)}"
#         for p in top
#     ])

#     messages = [
#         {
#             "role": "system",
#             "content": (
#                 "Jesteś pomocnym asystentem InPost. "
#                 "Pomagasz użytkownikom znaleźć najlepszy paczkomat. "
#                 "Odpowiadaj krótko i konkretnie po polsku."
#             )
#         },
#         {
#             "role": "user",
#             "content": (
#                 f"Zapytanie użytkownika: {user_query}\n\n"
#                 f"Dostępne paczkomaty (posortowane wg oceny):\n{points_text}\n\n"
#                 "Poleć 2-3 najlepsze opcje i krótko wyjaśnij dlaczego."
#             )
#         }
#     ]

#     headers = {
#         "Authorization": f"Bearer {HF_TOKEN}",
#         "Content-Type":  "application/json"
#     }

#     payload = {
#         "model":       HF_MODEL,
#         "messages":    messages,
#         "max_tokens":  300,
#         "temperature": 0.4,   # niższa = bardziej konkretne odpowiedzi
#         "stream":      False
#     }

#     try:
#         res = requests.post(HF_URL, headers=headers, json=payload, timeout=30)
#         res.raise_for_status()
#         return res.json()["choices"][0]["message"]["content"]

#     except requests.exceptions.Timeout:
#         return "⏳ Model ładuje się (cold start) — spróbuj za chwilę."
#     except Exception as e:
#         return f"❌ Błąd AI: {str(e)}"
    

# # ── GŁÓWNA FUNKCJA — automatyczny fallback ──
# def recommend(user_query: str, points: list) -> str:
#     """
#     Próbuje HuggingFace, fallback na Ollama.
#     W views.py wywołujesz tylko tę funkcję.
#     """

#     return recommend_hf(user_query, points)