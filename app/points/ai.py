# # OPENAI
# import os
# from openai import OpenAI, OpenAIError


# def recommend(user_query: str, points: list) -> str:
#     """
#     Rekomenduje najlepsze paczkomaty na podstawie zapytania użytkownika.
#     Używa GPT-4o-mini przez OpenAI API.
#     """

#     client = OpenAI()  # bierze OPENAI_API_KEY z env automatycznie

#     top_points = points[:10]  # top 10 żeby nie przepalać tokenów

#     # Czytelny tekst zamiast surowego dict — mniej tokenów, lepszy kontekst
#     points_text = "\n".join([
#         f"- {p['name']} | {p['address']} | "
#         f"status: {p['status']} | godziny: {p.get('opening_hours', '?')} | "
#         f"score: {p.get('score', 0)}"
#         for p in top_points
#     ])

#     messages = [
#         {
#             "role": "system",
#             "content": (
#                 "Jesteś pomocnym asystentem InPost. "
#                 "Pomagasz użytkownikom znaleźć najlepszy paczkomat. "
#                 "Odpowiadaj w tym samym języku co zapytanie użytkownika. "
#                 "Bądź konkretny i zwięzły — maksymalnie 3-4 zdania."
#             )
#         },
#         {
#             "role": "user",
#             "content": (
#                 f"Zapytanie: {user_query}\n\n"
#                 f"Dostępne paczkomaty (posortowane wg oceny):\n{points_text}\n\n"
#                 "Poleć 2-3 najlepsze opcje i krótko wyjaśnij dlaczego."
#             )
#         }
#     ]

#     try:
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=messages,
#             max_tokens=300,
#             temperature=0.4,  # niższa = bardziej konkretne odpowiedzi
#         )
#         return response.choices[0].message.content

#     except OpenAIError as e:
#         return f"❌ Błąd AI: {str(e)}"


# BIELIK
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


# MISTRAL
import os
import requests

HF_TOKEN = os.environ.get("HF_TOKEN")
HF_MODEL = "google/gemma-2-2b-it"  # oficjalnie rekomendowany przez HF docs
HF_URL   = f"https://router.huggingface.co/hf-inference/models/{HF_MODEL}/v1/chat/completions"


def recommend(user_query: str, points: list) -> str:

    top_points = points[:10]

    points_text = "\n".join([
        f"- {p['name']} | {p['address']} | "
        f"status: {p['status']} | godziny: {p.get('opening_hours', '?')} | "
        f"score: {p.get('score', 0)}"
        for p in top_points
    ])

    messages = [
        {
            "role": "user",
            "content": (
                f"Jesteś pomocnym asystentem InPost. "
                f"Odpowiadaj w tym samym języku co zapytanie. Bądź zwięzły.\n\n"
                f"Zapytanie: {user_query}\n\n"
                f"Dostępne paczkomaty (posortowane wg oceny):\n{points_text}\n\n"
                "Poleć 2-3 najlepsze opcje i krótko wyjaśnij dlaczego."
            )
        }
    ]

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type":  "application/json"
    }

    payload = {
        "model":       HF_MODEL,
        "messages":    messages,
        "max_tokens":  300,
        "temperature": 0.4,
        "stream":      False
    }

    try:
        res = requests.post(HF_URL, headers=headers, json=payload, timeout=30)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]

    except requests.exceptions.Timeout:
        return "⏳ Model ładuje się — spróbuj za chwilę."
    except Exception as e:
        return f"❌ Błąd AI: {str(e)}"
