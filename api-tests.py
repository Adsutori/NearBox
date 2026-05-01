import requests

def get_points_by_city(city):
    all_points = []
    page = 1

    while True:
        url = f"https://api-global-points.easypack24.net/v1/points?city={city}&page={page}"
        response = requests.get(url)
        data = response.json()

        all_points.extend(data["items"])

        if page >= data["meta"]["total_pages"]:
            break

        page += 1

    return all_points

user_city = input('City >>> ')
json_string = get_points_by_city(user_city)

with open('json.txt', 'w') as file:
    json_string = str(json_string)
    file.write(json_string)

