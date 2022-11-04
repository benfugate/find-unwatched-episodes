## find_unwatched_requests

This is a simple script that looks through the last 500 Overseerr requests and...

1. Filters out any that have not been marked as available
2. Filters out any that have not been available for 1 month
3. Filters out any that have not been available for 1 month
4. <b>Displays the unwatched movies/shows to the user</b>

This allows a Plex admin to remove requests that were not truly desired by a user.

---

### Requirements

#### Required services
* Overseerr
  * To see what has been requested, and when it became available
* Tautulli
  * To see when a show has been watched

#### Pip packages

* requests
  * To make api calls to Overseerr and Tautulli
* tqdm
  * To display the progress of the search to the user

---

### Usage

`python3 find_unwatched_requests.py <overseerr_host_url> <overseerr_api_token> <tautulli_host_url> <tautulli_api_token>`