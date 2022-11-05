import json
import requests
import argparse
from tqdm import tqdm
from datetime import datetime, timedelta

with open("config.json") as f:
    defaults = json.load(f)
parser = argparse.ArgumentParser()
parser.add_argument("--overseerr-url", default=defaults["overseerr_url"], help="overseerr host url")
parser.add_argument("--overseerr-token", default=defaults["overseerr_token"], help="overseerr api token")
parser.add_argument("--tautulli-url", default=defaults["tautulli_url"], help="tautulli host url")
parser.add_argument("--tautulli-token", default=defaults["tautulli_token"], help="tautulli api token")
args = parser.parse_args()

overseerr_request = f"{args.overseerr_url}/api/v1/request?take=500&filter=available"
headers = {
    "Content-type": "application/jso",
    "x-api-key": args.overseerr_token
}

response = requests.get(f"{overseerr_request}", headers=headers)
plex_requests = json.loads(response.text)
results = []
for plex_request in tqdm(plex_requests["results"]):
    mediaAddedAt = plex_request["media"]["mediaAddedAt"]
    requestedBy = plex_request["requestedBy"]["plexUsername"]
    oneMonthAgo = (datetime.utcnow() - timedelta(days=30))
    if mediaAddedAt:
        mediaAddedAt = datetime.strptime(mediaAddedAt, "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None)

    if not mediaAddedAt or mediaAddedAt > oneMonthAgo:
        continue

    tautulli_request = f"{args.tautulli_url}/api/v2?apikey={args.tautulli_token}&cmd=get_item_watch_time_stats&rating_key={plex_request['media']['ratingKey']}"
    response = requests.get(tautulli_request)
    watch_data = json.loads(response.text)["response"]["data"]
    watch_number = [item["total_plays"] for item in watch_data]
    if not any(watch_number):
        response = requests.get(f"{args.tautulli_url}/api/v2?apikey={args.tautulli_token}&cmd=get_metadata&rating_key={plex_request['media']['ratingKey']}")
        try:
            title = json.loads(response.text)["response"]["data"]["title"]
        except Exception as e:
            continue  # This show was probably recently deleted, found on overseerr but not on tautulli
        results.append([title, requestedBy, str(mediaAddedAt), plex_request["media"]["serviceUrl"]])

results = sorted(results, key=lambda l: l[2])  # Sort by oldest request to most recent
print("| {:60} | {:20} | {:30} | {:100} |".format(*["Title", "Requested By", "Date Available", "Sonarr URL"]))
print("-"*223)
for result in results:
    print("| {:60} | {:20} | {:30} | {:100} |".format(*result))
