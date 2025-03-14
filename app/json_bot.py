import json
import os

import requests
from dateutil import parser
from utils import utils


def main():
    json_feed_bot_path = os.environ.get("JSON_BOT_PATH", "posts/json_bot")
    config_name = "json_feeds"
    utils_obj = utils(json_feed_bot_path, config_name)

    for feed in utils_obj.list:
        url = feed.get("url")
        if url is None:
            raise ValueError(f"No url found in the file for feed {feed}")
        try:
            response = requests.get(url).content.decode("utf-8")
            feed_data = json.loads(response)
        except Exception as e:
            print(f"Error in parsing feed {feed.get('url')}: {e}")
            continue

        if feed.get("title") is None:
            raise ValueError(f"No title found in the file for feed {feed}")
        if feed.get("list_key") is None:
            raise ValueError(f"No list_key found in the file for feed {feed}")

        folder = feed.get("title").replace(" ", "_").lower()
        format_string = feed.get("format")
        for entry in feed_data.get(feed.get("list_key"), []):
            date_entry = entry.get("date")
            published_date = parser.parse(date_entry).date()

            path = entry.get("path")
            if path is None:
                print(f"No path found: {entry.get('title')}")
                continue
            file_name = path.rstrip("/").split("/")[-1]

            if "://" in url:
                protocol = url.split("://")[0] + "://"
                url = url.split("://")[1]
            else:
                protocol = "http://"
            entry["link"] = protocol + url.split("/")[0] + path

            if entry.get("days_ago") > 0:
                print(f"Skipping {entry.get('title')}")
                continue

            formatted_text = format_string.format(**entry)

            entry_data = {
                "title": entry.get("title"),
                "config": feed,
                "date": published_date,
                "rel_file_path": f"{folder}/{file_name}",
                "formatted_text": formatted_text,
                "link": entry["link"],
            }
            utils_obj.process_entry(entry_data)


if __name__ == "__main__":
    main()
