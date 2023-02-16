#!/usr/bin/python3

import re
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
parser.add_argument("--radarr-token", default=defaults["radarr_token"], help="radarr api token")
parser.add_argument("--sonarr-token", default=defaults["sonarr_token"], help="sonarr api token")
args = parser.parse_args()
args.tautulli_url = args.tautulli_url.rstrip("/")

def delete_content(delete_series=False, delete_movies=False):
    series = None
    movies = None
    sonarr_host = None
    radarr_host = None
    for result in results:
        if delete_series and "series" in result[3]:
            sonarr_host = re.search(r"http.*?://[^/]*", result[3]).group(0)
            series_request = f"{sonarr_host}/api/v3/series/?apikey={args.sonarr_token}"
            series = json.loads(requests.get(series_request).text)
        elif delete_movies and "movie" in result[3]:
            radarr_host = re.search(r"http.*?://[^/]*", result[3]).group(0)
            movies_request = f"{radarr_host}/api/v3/movie/?apikey={args.radarr_token}"
            movies = json.loads(requests.get(movies_request).text)

    if delete_series and not sonarr_host or not series:
        delete_series = False
    if delete_movies and not radarr_host or not movies:
        delete_movies = False

    for result in results:
        id = None
        endpoint = result[3].split("/")[-1]
        if "/series/" in result[3]:
            if not delete_series:
                continue
            for show in series:
                if show["titleSlug"] == endpoint:
                    id = show["id"]
            if id:
                delete_url = f"{sonarr_host}/api/v3/series/{id}?apikey={args.sonarr_token}&deleteFiles=true"
            else:
                print(f"Failed to delete {result[0]}")
                continue
        elif "/movie/" in results[3]:
            if not delete_movies:
                continue
            endpoint = result[3].split("/")[-1]
            id = None
            for movie in movies:
                if movie["titleSlug"] == endpoint:
                    id = movie["id"]
            if id:
                delete_url = f"{radarr_host}/api/v3/movie/{id}?apikey={args.radarr_token}&deleteFiles=true"
            else:
                print(f"Failed to delete {result[0]}")
                continue

        response = requests.delete(delete_url)
        if response.status_code == 200:
            print(f"Deleted {result[0]}")
        else:
            print(f"Failed to delete {result[0]}")

overseerr_request = f"{args.overseerr_url}/api/v1/request?take=500&filter=available"
headers = {
    "Content-type": "application/json",
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
if not results:
    print("No unwatched content found :)")
    exit()

print("| {:60} | {:20} | {:30} | {:100} |".format(*["Title", "Requested By", "Date Available", "Management URL"]))
print("-"*223)
for result in results:
    print("| {:60} | {:20} | {:30} | {:100} |".format(*result))

delete_movies, delete_series = False, False
if args.radarr_token and input(f"Delete all unwatched movies? Y/N: ").lower() == "y":
    delete_series = True
if args.sonarr_token and input(f"Delete all unwatched shows? Y/N: ").lower() == "y":
    delete_movies = True
delete_content(delete_series, delete_movies)
