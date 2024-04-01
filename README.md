## find_unwatched_requests

This is a simple script that looks through the last 500 Overseerr requests and...

1. Filters out any request that has not been marked as available
2. Filters out any request that has not been available for N days (default 14)
3. Filters out any request that has not been watched by any user
4. <b>Displays the unwatched movies/shows to the user</b>
5. <b>Delete the unwatched media from the server</b>

This allows a Plex admin to remove requests that were not truly desired by a user.

---

### Requirements

#### Required services
* Overseerr
  * To see what has been requested, and when it became available
* Tautulli
  * To see when a show has been watched

#### Optional services
* Sonarr & Radarr
  * Used to optionally delete content from the server

#### Pip packages

* requests
  * To make api calls to Overseerr and Tautulli
* tqdm
  * To display the progress of the search to the user

---

### Building

I have this built into a docker container which runs daily at midnight. You can build it yourself using

`docker build -t find-unwatched-requests .`

within this root directory to build your own image, or you can pull my docker image

`docker pull benfugate/find-unwatched-requests`

---

### Usage

#### Docker

```
docker run \
    -e overseerr_host=<OVERSEERR_HOST_URL> \
    -e overseerr_token=<OVERSEERR_TOKEN> \
    -e tautulli_host=<TAUTULLI_HOST_URL> \
    -e tautulli_token=<TAUTULLI_TOKEN> \
    -e wait_days=<NUMBER_DAYS_TO_WAIT_BEFORE_DELETE> \
    -e num_requests=<NUMBER_OF_REQUESTS_TO_CHECK> \
    -e ignore_users=<LIST,OF,USERS,TO,IGNORE>
    -e verbose=<true/false>
    benfugate/find-unwatched-requests:latest
```

#### Other

If config file has been filled out:

`python3 find_unwatched_requests.py`

Alternatively:
```
python3 find_unwatched_requests.py \
    --overseerr-host-url <overseerr_host_url> \
    --overseerr-token <overseerr_api_token> \
    --tautulli-url <tautulli_host_url> \
    --tautulli-token <tautulli_api_token> \
    --wait-days <integer_value>
    --num-requests <integer_value>
```
