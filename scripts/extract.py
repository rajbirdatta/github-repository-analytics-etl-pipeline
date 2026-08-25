import json
import requests

username = "microsoft"

url = f"https://api.github.com/users/{username}/repos"

response = requests.get(url)

if response.status_code == 200:

    repositories = response.json()

    with open("data/raw/repos.json", "w") as file:
        json.dump(repositories, file, indent=4)

    print("Data saved successfully.")

else:
    print("Request failed.")