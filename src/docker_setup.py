import os
import json

with open('/usr/src/app/src/config.json') as f:
    config = json.load(f)

config["DOCKER"] = True
config["overseerr_host"] = os.environ.get("overseerr_host")
config["overseerr_token"] = os.environ.get("overseerr_token")
config["tautulli_host"] = os.environ.get("tautulli_host")
config["tautulli_token"] = os.environ.get("tautulli_token")
config["wait_days"] = int(os.environ.get("wait_days")) if os.environ.get("wait_days") else config["wait_days"]
config["num_requests"] = int(os.environ.get("num_requests")) if os.environ.get("num_requests") else config["num_requests"]
config["ignore_users"] = os.environ.get("ignore_users").split(",") if os.environ.get("ignore_users") \
    else config["ignore_users"]
config["verbose"] = True if (os.environ.get("verbose") and os.environ.get("verbose").lower() == "true") else False

with open('/usr/src/app/src/config.json', 'w', encoding='utf-8') as f:
    json.dump(config, f, ensure_ascii=False, indent=4)
