#!/usr/bin/env python3

import os
import json
import time
import requests
import argparse
import traceback
from tqdm import tqdm
from multiprocessing import Pool
from datetime import datetime, timedelta


class FindUnwatchedRequests:
    def __init__(self):
        with open(f"{os.path.dirname(os.path.abspath(__file__))}/config.json") as f:
            defaults = json.load(f)
        parser = argparse.ArgumentParser()
        parser.add_argument("--skip-health-check", action="store_true",
                            help="skip the pre-run health check")
        parser.add_argument("--overseerr-host", default=defaults["overseerr_host"],
                            help="overseerr host url")
        parser.add_argument("--overseerr-token", default=defaults["overseerr_token"],
                            help="overseerr api token")
        parser.add_argument("--tautulli-host", default=defaults["tautulli_host"],
                            help="tautulli host url")
        parser.add_argument("--tautulli-token", default=defaults["tautulli_token"],
                            help="tautulli api token")
        parser.add_argument("--num-requests", default=defaults["num_requests"],
                            help="number of overseerr requests to look through")
        parser.add_argument("--ignore-users", default=defaults["ignore_users"], action="extend",
                            nargs='+', type=str, help="users to not include in unwatched requests scan")
        parser.add_argument("--verbose", default=defaults["verbose"], action="store_true",
                            help="Run in verbose mode")
        self.docker = defaults["DOCKER"]
        self.args = parser.parse_args()

        self.print_timestamp_if_docker()
        print("Starting prune")

        if not self.args.overseerr_host \
                or not self.args.overseerr_token \
                or not self.args.tautulli_host \
                or not self.args.tautulli_token:
            print("the following arguments are required: overseerr-host, overseerr-token, tautulli-host, tautulli-token")
            exit(1)

        # Some hosts APIs get real fussy about extra slashes
        self.args.tautulli_host = self.args.tautulli_host.rstrip("/")
        self.args.overseerr_host = self.args.overseerr_host.rstrip("/")

        # Check to make sure an availability sync is not currently being run on Overseerr
        if not self.args.skip_health_check:
            self._check_health()

        self.radarr_host = None
        self.radarr_token = None
        self.sonarr_host = None
        self.sonarr_token = None

        self.unwatched_media_types = []
        self.unwatched_requests = []
        self.all_content = []
        self.delete = []

    def print_timestamp_if_docker(self):
        if self.docker:
            print(f"{time.time()}: ", end="")

    def _check_health(self):
        issues = []
        jobs = self._get_overseerr_jobs()
        for job in jobs:
            if job["id"] == "availability-sync":
                if job["running"]:
                    issues.append("[ERROR] Overseerr availability sync is running. Invalid content could be detected.\n"
                                  "\tPlease try running again in a couple of minutes.")
        if issues:
            for issue in issues:
                self.print_timestamp_if_docker()
                print(issue)
            exit(0)

    def _overseerr_get_request(self, endpoint):
        headers = {
            "Content-type": "application/json",
            "x-api-key": self.args.overseerr_token
        }
        # return json.loads(requests.get(f"{endpoint}", headers=headers).text)
        return requests.get(f"{endpoint}", headers=headers).json()

    def _overseerr_post_request(self, endpoint, data={}):
        headers = {
            "Content-type": "application/json",
            "x-api-key": self.args.overseerr_token
        }
        # return json.loads(requests.get(f"{endpoint}", headers=headers).text)
        response = requests.post(f"{endpoint}", data=data, headers=headers)
        if response.status_code == 404:
            self.print_timestamp_if_docker()
            print(f"Error with POST request:\n\tError: {response}\n\t{endpoint}: {data}")

    def _find_management_hosts(self):
        def add_scheme(host):
            if host["useSsl"]:
                host["scheme"] = "https://"
            else:
                host["scheme"] = "http://"
            return host
        sonarr_host = add_scheme(self._overseerr_get_request(f"{self.args.overseerr_host}/api/v1/settings/sonarr")[0])
        radarr_host = add_scheme(self._overseerr_get_request(f"{self.args.overseerr_host}/api/v1/settings/radarr")[0])
        self.sonarr_host = f"{sonarr_host['scheme']}{sonarr_host['hostname']}:{sonarr_host['port']}"
        self.radarr_host = f"{radarr_host['scheme']}{radarr_host['hostname']}:{radarr_host['port']}"
        self.sonarr_token = sonarr_host["apiKey"]
        self.radarr_token = radarr_host["apiKey"]

    def _grab_content_library(self):
        self._find_management_hosts()
        all_series, all_movies = [], []
        if "series" in self.delete:
            series_request = f"{self.sonarr_host}/api/v3/series/?apikey={self.sonarr_token}"
            all_series = json.loads(requests.get(series_request).text)
        if "movie" in self.delete:
            movies_request = f"{self.radarr_host}/api/v3/movie/?apikey={self.radarr_token}"
            all_movies = json.loads(requests.get(movies_request).text)
        self.all_content += all_series + all_movies

    def _get_host_info(self, content_type):
        if content_type == "movie":
            return {"host": self.radarr_host, "token": self.radarr_token,
                    "content_type": content_type, "platform": "Radarr"}
        elif content_type == "series":
            return {"host": self.sonarr_host, "token": self.sonarr_token,
                    "content_type": content_type, "platform": "Sonarr"}

    def _get_overseerr_jobs(self):
        url = f"{self.args.overseerr_host}/api/v1/settings/jobs/"
        return self._overseerr_get_request(url)

    def run_post_job(self, job, data=None):
        url = f"{self.args.overseerr_host}/api/v1/settings/jobs/{job}/run"
        self._overseerr_post_request(url, data)

    def delete_content(self):
        content_deleted = False
        self._grab_content_library()
        for request in self.unwatched_requests:
            try:
                content_id = None
                if bool([content for content in self.delete if(content in request['service_url'])]):
                    host = self._get_host_info(request["type"])
                    title_slug = request['service_url'].split("/")[-1]
                    for content in self.all_content:
                        if content["titleSlug"] == title_slug:
                            content_id = content["id"]
                            break
                    if content_id:
                        delete_url = f"{host['host']}/api/v3/{host['content_type']}/{content_id}" \
                                     f"?apikey={host['token']}&deleteFiles=true"
                    else:
                        self.print_timestamp_if_docker()
                        print(f"Failed to find the {host['content_type']} {request['title']} on "
                              f"{host['platform']}. Skipping")
                        continue
                else:
                    continue

                response = requests.delete(delete_url)
                self.print_timestamp_if_docker()
                if response.status_code == 200:
                    print(f"Deleted {request['title']}")
                    content_deleted = True
                else:
                    print(f"Failed to delete {request['title']}")
            except Exception as e:
                self.print_timestamp_if_docker()
                print(f"Error deleting \"{request['title']}\". Skipping.")
                if self.args.verbose:
                    print(traceback.format_exc())
        return content_deleted

    def display_unwatched_requests(self):
        if not self.unwatched_requests:
            print("No unwatched content found :)")
            exit()

        print("| {:60} | {:6} | {:20} | {:30} | {:100} |".format(
            *["Title", "Type", "Requested By", "Date Available", "Management URL"]
        ))
        print("-"*223)
        for request in self.unwatched_requests:
            print("| {:60} | {:6} | {:20} | {:30} | {:100} |".format(*request.values()))

    def find_unwatched_requests(self):
        request_url = f"{self.args.overseerr_host}/api/v1/request?take={self.args.num_requests}&filter=available"
        plex_requests = self._overseerr_get_request(request_url)["results"]
        results = []
        with Pool(processes=8) as pool:
            with tqdm(total=self.args.num_requests) as pbar:
                for result in pool.imap_unordered(self._get_request, plex_requests):
                    pbar.update()
                    if result is not None and result["media_requested_by"] not in self.args.ignore_users:
                        results.append(result)
                        if result["type"] not in self.unwatched_media_types:
                            self.unwatched_media_types.append(result["type"])

        # Sort by oldest request to most recent
        self.unwatched_requests = sorted(results, key=lambda d: d["media_added_at"])

    def _get_request(self, plex_request):
        plex_request["type"] = "series" if plex_request["type"] == "tv" else plex_request["type"]
        media_added_at = plex_request["media"]["mediaAddedAt"]
        media_requested_by = plex_request["requestedBy"]["plexUsername"]
        one_month_ago = (datetime.utcnow() - timedelta(days=30))
        if media_added_at:
            media_added_at = datetime.strptime(media_added_at, "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None)

        if not media_added_at or media_added_at > one_month_ago:
            return None

        tautulli_request = f"{self.args.tautulli_host}/api/v2?apikey={self.args.tautulli_token}" \
                           f"&cmd=get_item_watch_time_stats&rating_key={plex_request['media']['ratingKey']}"
        response = requests.get(tautulli_request)
        watch_data = json.loads(response.text)["response"]["data"]
        watch_number = [item["total_plays"] for item in watch_data]
        if not any(watch_number):
            response = requests.get(f"{self.args.tautulli_host}/api/v2?apikey={self.args.tautulli_token}"
                                    f"&cmd=get_metadata&rating_key={plex_request['media']['ratingKey']}")
            try:
                title = json.loads(response.text)["response"]["data"]["title"]
            except Exception as e:
                return None  # This show was probably recently deleted, found on overseerr but not on Tautulli

            return {
                "title": title,
                "type": plex_request["type"],
                "media_requested_by": media_requested_by,
                "media_added_at": str(media_added_at),
                "service_url": plex_request["media"]["serviceUrl"]
            }


if __name__ == '__main__':
    find_unwatched = FindUnwatchedRequests()
    find_unwatched.find_unwatched_requests()

    if not find_unwatched.docker:
        find_unwatched.display_unwatched_requests()
        if ("movie" in find_unwatched.unwatched_media_types
                and input(f"Delete all unwatched movies? Y/N: ").lower() == "y"):
            find_unwatched.delete.append("movie")
        if ("series" in find_unwatched.unwatched_media_types
                and input(f"Delete all unwatched shows? Y/N: ").lower() == "y"):
            find_unwatched.delete.append("series")
    else:
        find_unwatched.delete = ["series", "movie"]

    if find_unwatched.delete:
        run_availability_sync = False
        try:
            run_availability_sync = find_unwatched.delete_content()
        except Exception as e:
            find_unwatched.print_timestamp_if_docker()
            print(traceback.format_exc())
        finally:
            if run_availability_sync:
                find_unwatched.print_timestamp_if_docker()
                print("Waiting 60 seconds for Plex to detect changes and refresh, and then triggering an Overseer "
                      "availability sync job.")
                for timer in range(60):
                    print(f"\r{timer}", end="")
                    time.sleep(1)
                find_unwatched.run_post_job("availability-sync")
        if not run_availability_sync and not find_unwatched.docker:
            print("\nNothing was deleted, so an availability sync was not triggered.")
            if input("Would you like to run one anyways? Y/N: ").lower() == "y":
                find_unwatched.run_post_job("availability-sync")
    find_unwatched.print_timestamp_if_docker()
    print("Done!")
