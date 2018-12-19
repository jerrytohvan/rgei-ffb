import json
import requests

response = requests.get("https://rge-cv.herokuapp.com/")
json_data = json.loads(response.text)
print json_data