#!/usr/bin/python3

import re
import json
import requests
import argparse
from tqdm import tqdm
from datetime import datetime, timedelta

class FindUnwatchedRequests:
    def __init__(self):
        with open("config.json") as f:
            defaults = json.load(f)
        parser = argparse.ArgumentParser()
        parser.add_argument("--overseerr-url", default=defaults["overseerr_url"], help="overseerr host url")
        parser.add_argument("--overseerr-token", default=defaults["overseerr_token"], help="overseerr api token")
        parser.add_argument("--tautulli-url", default=defaults["tautulli_url"], help="tautulli host url")
        parser.add_argument("--tautulli-token", default=defaults["tautulli_token"], help="tautulli api token")
        self.args = parser.parse_args()
        self.args.tautulli_url = self.args.tautulli_url.rstrip("/")
        self.radarr_token = None
        self.sonarr_token = None

        self.unwatched_requests = []
        self.sonarr_host = None
        self.radarr_host = None
        self.all_content = None
        self.delete = []

    def _overseerr_request(self, endpoint):
        headers = {
            "Content-type": "application/json",
            "x-api-key": self.args.overseerr_token
        }
        return json.loads(requests.get(f"{endpoint}", headers=headers).text)


    def _find_management_hosts(self):
        def add_scheme(host):
            if host["useSsl"]:
                host["scheme"] = "https://"
            else:
                host["scheme"] = "http://"
            return host
        sonarr_host = add_scheme(self._overseerr_request(f"{self.args.overseerr_url}/api/v1/settings/sonarr")[0])
        radarr_host = add_scheme(self._overseerr_request(f"{self.args.overseerr_url}/api/v1/settings/radarr")[0])
        self.sonarr_host = f"{sonarr_host['scheme']}{sonarr_host['hostname']}:{sonarr_host['port']}"
        self.radarr_host = f"{radarr_host['scheme']}{radarr_host['hostname']}:{radarr_host['port']}"
        self.sonarr_token = sonarr_host["apiKey"]
        self.radarr_token = radarr_host["apiKey"]

    def _grab_content_library(self):
        self._find_management_hosts()
        all_series, all_movies = {}, {}
        if "series" in self.delete:
            series_request = f"{self.sonarr_host}/api/v3/series/?apikey={self.sonarr_token}"
            all_series = json.loads(requests.get(series_request).text)[0]
        if "movies" in self.delete:
            movies_request = f"{self.radarr_host}/api/v3/movie/?apikey={self.radarr_token}"
            all_movies = json.loads(requests.get(movies_request).text)[0]
        self.all_content = {**all_series, **all_movies}

    def _get_host_info(self, url):
        content_type = re.search(r"(movies|series)", url).group(1)
        if content_type == "movies":
            return {"host": self.radarr_host, "token": self.radarr_token}
        elif content_type == "series":
            return {"host": self.sonarr_host, "token": self.sonarr_token, "content_type": content_type}

    def delete_content(self):
        self._grab_content_library()
        for request in self.unwatched_requests:
            id = None
            endpoint = request[3].split("/")[-1]
            if bool([content for content in self.delete if(content in request[3])]):
                host = self._get_host_info(request[3])
                for content in self.all_content:
                    if content["titleSlug"] == endpoint:
                        id = content["id"]
                if id:
                    delete_url = f"{host['host']}/api/v3/series/{host['content_type']}?apikey={host['token']}&deleteFiles=true"
                else:
                    print(f"Failed to delete {request[0]}")
                    continue
            else:
                continue

            response = requests.delete(delete_url)
            if response.status_code == 200:
                print(f"Deleted {request[0]}")
            else:
                print(f"Failed to delete {request[0]}")


    def display_unwatched_requests(self):
        if not self.unwatched_requests:
            print("No unwatched content found :)")
            exit()

        print("| {:60} | {:20} | {:30} | {:100} |".format(*["Title", "Requested By", "Date Available", "Management URL"]))
        print("-"*223)
        for request in self.unwatched_requests:
            print("| {:60} | {:20} | {:30} | {:100} |".format(*request))


    def find_unwatched_requests(self):
        request_url = f"{self.args.overseerr_url}/api/v1/request?take=500&filter=available"
        plex_requests = self._overseerr_request(request_url)
        results = []
        for plex_request in tqdm(plex_requests["results"]):
            media_added_at = plex_request["media"]["mediaAddedAt"]
            media_requested_by = plex_request["requestedBy"]["plexUsername"]
            one_month_ago = (datetime.utcnow() - timedelta(days=30))
            if media_added_at:
                media_added_at = datetime.strptime(media_added_at, "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None)

            if not media_added_at or media_added_at > one_month_ago:
                continue

            tautulli_request = f"{self.args.tautulli_url}/api/v2?apikey={self.args.tautulli_token}&cmd=get_item_watch_time_stats&rating_key={plex_request['media']['ratingKey']}"
            response = requests.get(tautulli_request)
            watch_data = json.loads(response.text)["response"]["data"]
            watch_number = [item["total_plays"] for item in watch_data]
            if not any(watch_number):
                response = requests.get(f"{self.args.tautulli_url}/api/v2?apikey={self.args.tautulli_token}&cmd=get_metadata&rating_key={plex_request['media']['ratingKey']}")
                try:
                    title = json.loads(response.text)["response"]["data"]["title"]
                except Exception as e:
                    continue  # This show was probably recently deleted, found on overseerr but not on Tautulli
                results.append([title, media_requested_by, str(media_added_at), plex_request["media"]["serviceUrl"]])

        self.unwatched_requests = sorted(results, key=lambda l: l[2])  # Sort by oldest request to most recent

if __name__ == '__main__':
    find_unwatched = FindUnwatchedRequests()
    find_unwatched.find_unwatched_requests()
    find_unwatched.display_unwatched_requests()

    if find_unwatched.args.radarr_token and input(f"Delete all unwatched movies? Y/N: ").lower() == "y":
        find_unwatched.delete.append("movies")
    if find_unwatched.args.sonarr_token and input(f"Delete all unwatched shows? Y/N: ").lower() == "y":
        find_unwatched.delete.append("series")
    if find_unwatched.delete:
        find_unwatched.delete_content()
