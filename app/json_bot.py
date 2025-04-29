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
            print(f"Error in parsing feed {url}: {e}")
            continue

        feed_title = feed.get("title")
        feed_list_key = feed.get("list_key")
        if feed_title is None:
            raise ValueError(f"No title found in the file for feed {feed}")
        if feed_list_key is None:
            raise ValueError(f"No list_key found in the file for feed {feed}")

        folder = feed_title.replace(" ", "_").lower()
        format_string = feed.get("format")
        media_data = feed.get("media")
        mentions_data = feed.get("mentions")
        hashtags_data = feed.get("hashtags")

        for entry in feed_data.get(feed_list_key, []):
            entry_subsites = entry.get("subsites")
            if not any(subsite in entry_subsites for subsite in media_data.keys()):
                print(f"Skipping {entry.get('title')} as it is not in the subsites")
                continue

            published_date = parser.parse(entry.get("date")).date()

            path = entry.get("path")
            if path is None:
                print(f"No path found: {entry.get('title')}")
                continue
            file_name = path.rstrip("/").split("/")[-1]

            if "external_link" in entry:
                entry["link"] = entry["external_link"]
            else:
                if "://" in url:
                    protocol = url.split("://")[0] + "://"
                    url = url.split("://")[1]
                else:
                    protocol = "http://"
                path = path if path.startswith("/") else f"/{path}"
                entry["link"] = protocol + url.split("/")[0] + path

            if feed_list_key == "events":
                if entry.get("days_ago") > 0:
                    print(f"Skipping {entry.get('title')} as it is past the date")
                    continue
                if entry.get("days_ago") < -14:
                    print(
                        f"Skipping {entry.get('title')} as it is more than 14 days till now"
                    )
                    continue

            formatted_text = format_string.format(**entry)

            new_media = {}
            for subsite, content in media_data.items():
                if subsite not in entry_subsites:
                    continue
                if isinstance(content, dict):
                    for group_name, media_list in content.items():
                        new_media[f"{subsite}_{group_name}"] = media_list
                elif isinstance(content, list):
                    new_media[subsite] = content

            used_media_names = set()
            for media_list in new_media.values():
                used_media_names.update(media_list)

            def map_config(feed_config):
                new_config = {}
                feed_config_all = feed_config.get("all", {})
                for media in used_media_names:
                    if media in feed_config_all:
                        new_config[media] = feed_config_all[media].copy()
                for subsite in entry_subsites:
                    for media, value in feed_config.get(subsite, {}).items():
                        if media in used_media_names:
                            new_config.setdefault(media, []).extend(value)
                return new_config

            json_config = {
                "media": new_media,
                "mentions": map_config(mentions_data),
                "hashtags": map_config(hashtags_data),
            }

            entry_data = {
                "title": entry.get("title"),
                "config": json_config,
                "date": published_date,
                "rel_file_path": f"{folder}/{file_name}",
                "formatted_text": formatted_text,
                "link": entry.get("link"),
            }
            utils_obj.process_entry(entry_data)


if __name__ == "__main__":
    main()
