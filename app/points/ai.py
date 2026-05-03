import os
import requests
import math
import json
import re
from openai import OpenAI, OpenAIError

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")


# ─────────────────────────────────────────────
#  KROK 0 — KLASYFIKACJA ZAPYTANIA
# ─────────────────────────────────────────────

INTENT_SYSTEM_PROMPT = """
Jesteś moderatorem zapytań dla aplikacji NearBox — aplikacji do znajdowania paczkomatów InPost.

Twoim zadaniem jest sklasyfikować zapytanie użytkownika do jednej z kategorii:

1. ON_TOPIC       — zapytanie dotyczy szukania paczkomatu blisko jakiegoś miejsca/obiektu,
                    LUB użytkownik pyta o paczkomat blisko siebie / swojej lokalizacji
                    Przykłady: "paczkomat blisko PKP", "paczkomat obok Lidla",
                    "paczkomat przy ul. Królewskiej", "najbliższy paczkomat centrum",
                    "paczkomat blisko mnie", "najbliższy paczkomat", "co jest obok mnie",
                    "znajdź paczkomat w pobliżu", "paczkomat niedaleko mnie"

2. TOO_VAGUE      — zapytanie jest o paczkomat, ale nie podaje żadnego miejsca odniesienia
                    i NIE sugeruje lokalizacji użytkownika
                    Przykłady: "daj mi paczkomat", "pokaż jakiś paczkomat", "dowolny"

3. OFF_TOPIC      — zapytanie jest kompletnie nie na temat paczkomatów
                    Przykłady: "kocham Legię", "jaka jest pogoda", "napisz mi wiersz",
                    "co to jest fotosynteza", "kim jesteś"

4. OFFENSIVE      — zapytanie zawiera wulgaryzmy, obraźliwe treści lub hejt

Odpowiedz WYŁĄCZNIE jednym słowem: ON_TOPIC, TOO_VAGUE, OFF_TOPIC lub OFFENSIVE.
Żadnego dodatkowego tekstu.
""".strip()

EASTER_EGG_SYSTEM_PROMPT = """
Jesteś zabawnym asystentem aplikacji NearBox do znajdowania paczkomatów InPost.
Użytkownik napisał coś kompletnie nie na temat.

Twoim zadaniem jest:
1. Odnieść się krótko i śmiesznie do tego co napisał (1 zdanie, z humorem, ale bez złośliwości)
2. Delikatnie dać do zrozumienia, że to nie jest miejsce na takie pytania
3. Zaproponować pomoc w znalezieniu paczkomatu blisko jakiegoś miejsca

Odpowiedz po polsku, max 3 zdania. Bądź ciepły i zabawny, nie sarkastyczny.
Nie używaj emoji na początku zdania.
""".strip()


OFFENSIVE_RESPONSES = [
    "Hej, nie ładnie tak mówić! 🫵 Jestem tu po to, żeby pomagać znajdować paczkomaty — może zamiast tego powiesz mi, blisko jakiego miejsca szukasz?",
    "Oj, oj... takich słów tu nie używamy. 😅 Wróćmy do tematu — mogę Ci znaleźć paczkomat blisko dowolnego miejsca w mieście!",
    "To nie przeszło przez mój filtr kulturalności. 😇 Ale serio — jeśli potrzebujesz paczkomatu blisko jakiegoś miejsca, chętnie pomogę!",
]

TOO_VAGUE_RESPONSE = (
    "Chętnie pomogę! 📦 Powiedz mi tylko, blisko jakiego miejsca szukasz paczkomatu — "
    "np. 'paczkomat blisko dworca', 'obok Lidla' albo 'przy ul. Królewskiej'. "
    "Im dokładniej, tym lepiej trafię!"
)


def _classify_intent(user_query: str, client: OpenAI) -> str:
    """
    Klasyfikuje zapytanie użytkownika.
    Zwraca: ON_TOPIC | TOO_VAGUE | OFF_TOPIC | OFFENSIVE
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user",   "content": user_query}
            ],
            max_tokens=10,
            temperature=0,
        )
        result = response.choices[0].message.content.strip().upper()
        print(f"[AI] Klasyfikacja zapytania: '{result}'", flush=True)

        if result in ("ON_TOPIC", "TOO_VAGUE", "OFF_TOPIC", "OFFENSIVE"):
            return result

        # Fallback — jeśli GPT zwrócił coś innego
        return "ON_TOPIC"

    except OpenAIError as e:
        print(f"[AI] Błąd klasyfikacji: {e}", flush=True)
        return "ON_TOPIC"


def _generate_easter_egg(user_query: str, client: OpenAI) -> str:
    """
    Generuje śmieszną odpowiedź dla off-topic zapytań.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": EASTER_EGG_SYSTEM_PROMPT},
                {"role": "user",   "content": f"Użytkownik napisał: \"{user_query}\""}
            ],
            max_tokens=120,
            temperature=0.9,
        )
        return response.choices[0].message.content.strip()

    except OpenAIError as e:
        print(f"[AI] Błąd easter egg: {e}", flush=True)
        return (
            "Hmm, to ciekawe... ale tu zajmujemy się paczkomatami! 📦 "
            "Jeśli chcesz znaleźć paczkomat blisko jakiegoś miejsca, chętnie pomogę."
        )


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
                "key":     GOOGLE_MAPS_API_KEY,
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

    result      = data["results"][0]
    loc         = result["geometry"]["location"]
    lat         = float(loc["lat"])
    lon         = float(loc["lng"])

    result_types = result.get("types", [])
    is_partial   = result.get("partial_match", False)
    vague_types  = {"locality", "administrative_area_level_1",
                    "administrative_area_level_2", "country", "postal_code"}
    is_precise   = not is_partial and not bool(vague_types & set(result_types))

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
    R    = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a    = (math.sin(dlat / 2) ** 2 +
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

    location_name = _extract_location_ai(user_query, city, client) if client else None
    print(f"[AI] Wyciągnięta nazwa miejsca: '{location_name}'", flush=True)

    coords     = None
    is_precise = False

    if location_name:
        result = _geocode_google(location_name, city)
        if result:
            lat, lon, is_precise = result
            coords = (lat, lon)

    if not coords:
        result = _geocode_google(city, "")
        if result:
            lat, lon, _ = result
            coords      = (lat, lon)
            is_precise  = False
            print(f"[GEOCODE] Fallback do centrum miasta: {coords}", flush=True)

    if not coords:
        return points, None, False

    lat, lon = coords
    for p in points:
        p_lat    = p.get("lat")
        p_lon    = p.get("lng")
        p["_dist"] = (
            _distance_km(lat, lon, float(p_lat), float(p_lon))
            if p_lat and p_lon else 9999
        )

    return sorted(points, key=lambda p: p["_dist"]), coords, is_precise


# ─────────────────────────────────────────────
#  GŁÓWNA FUNKCJA
# ─────────────────────────────────────────────

def recommend(user_query: str, points: list, city: str = "", lat=None, lng=None) -> str:
    client = OpenAI()

    # ── KROK 0: Klasyfikacja zapytania ──────────────────────────
    intent = _classify_intent(user_query, client)

    if intent == "OFFENSIVE":
        import random
        return random.choice(OFFENSIVE_RESPONSES)

    if intent == "OFF_TOPIC":
        return _generate_easter_egg(user_query, client)

    if intent == "TOO_VAGUE":
        # Jeśli mamy lokalizację usera — traktuj jak ON_TOPIC
        if not (lat and lng):
            return TOO_VAGUE_RESPONSE

    # ── Sprawdź czy zapytanie dotyczy lokalizacji usera ──────────
    USER_LOCATION_PHRASES = (
        "blisko mnie", "obok mnie", "w pobliżu mnie", "niedaleko mnie",
        "najbliższy", "najbliżej mnie", "przy mnie", "koło mnie",
        "w moim pobliżu", "gdzie jestem", "moja okolica",
    )
    is_user_location_query = any(
        phrase in user_query.lower() for phrase in USER_LOCATION_PHRASES
    )

    # ── KROK 1-3: Sortowanie ────────────────────────────────────
    if is_user_location_query and lat and lng:
        # Sortuj bezpośrednio po współrzędnych usera — bez geocodingu
        ref_lat, ref_lng = float(lat), float(lng)
        for p in points:
            p_lat = p.get("lat")
            p_lng = p.get("lng")
            p["_dist"] = (
                _distance_km(ref_lat, ref_lng, float(p_lat), float(p_lng))
                if p_lat and p_lng else 9999
            )
        sorted_points = sorted(points, key=lambda p: p["_dist"])
        coords        = (ref_lat, ref_lng)
        is_precise    = True   # mamy dokładne GPS — nie pokazuj ostrzeżenia
        print(f"[AI] Tryb: lokalizacja usera ({ref_lat:.5f}, {ref_lng:.5f})", flush=True)

    else:
        sorted_points, coords, is_precise = _sort_by_location(
            user_query, points, city, client
        )

    # print(f"\n{'='*50}", flush=True)
    # print(f"[DEBUG] query      = '{user_query}'", flush=True)
    # print(f"[DEBUG] city       = '{city}'", flush=True)
    # print(f"[DEBUG] intent     = '{intent}'", flush=True)
    # print(f"[DEBUG] coords     = {coords}", flush=True)
    # print(f"[DEBUG] is_precise = {is_precise}", flush=True)
    # print(f"[DEBUG] top5 dists = {[round(p.get('_dist', 9999), 2) for p in sorted_points[:5]]}", flush=True)
    # print(f"[DEBUG] top5 names = {[p.get('name') for p in sorted_points[:5]]}", flush=True)
    # print(f"{'='*50}\n", flush=True)

    top_points  = sorted_points[:5]
    points_text = "\n".join([
        f"- {p['name']} | {p['address']} | "
        f"status: {p['status']} | godziny: {p.get('opening_hours', '?')} | "
        f"odległość: {p.get('_dist', 9999):.2f} km"
        for p in top_points
    ])

    geocode_note = (
        "UWAGA: Nie udało się zlokalizować konkretnego miejsca z zapytania — "
        "paczkomaty są posortowane wg centrum miasta, nie wg podanego miejsca. "
        "Poinformuj o tym użytkownika krótko i naturalnie."
        if not is_precise and coords
        else ""
    )

    # Kontekst lokalizacji usera dla GPT
    location_note = (
        f"Użytkownik znajduje się na współrzędnych ({float(lat):.5f}, {float(lng):.5f}). "
        "Paczkomaty są posortowane od najbliższego jego lokalizacji."
        if lat and lng and is_user_location_query
        else ""
    )

    messages = [
        {
            "role": "system",
            "content": (
                "Jesteś pomocnym asystentem NearBox. "
                "Pomagasz użytkownikom znaleźć najlepszy paczkomat InPost. "
                "Odpowiadaj w tym samym języku co zapytanie użytkownika. "
                "Bądź konkretny i zwięzły — maksymalnie 3-4 zdania. "
                "Opieraj się WYŁĄCZNIE na danych z listy paczkomatów — "
                "nie wymyślaj lokalizacji ani odległości. "
                f"{location_note} "
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
