import json
import os
import re
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup
from dateutil import parser
from markdownify import markdownify
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
        mapped_subsites = set()
        for group, channel_data in media_data.items():
            for subsites in channel_data.values():
                mapped_subsites.update(subsites)
        media_conflicts = feed.get("media_conflicts", {})
        mentions_data = feed.get("mentions")
        hashtags_data = feed.get("hashtags")

        for entry in feed_data.get(feed_list_key, []):
            entry_main_subsite = entry.get("main_subsite")
            if entry_main_subsite and entry_main_subsite not in mapped_subsites:
                # ignore main_subsite if feed config doesn't know about it
                entry_main_subsite = None
            entry_subsites = entry.get("subsites")
            if not entry_main_subsite and not any(subsite in entry_subsites for subsite in mapped_subsites):
                print(
                    f"Skipping {entry.get('title')}: no match between subsites and configured media channels"
                )
                continue

            published_date = parser.parse(entry.get("date")).date()

            path = entry.get("path")
            if path is None:
                print(f"No path found: {entry.get('title')}")
                continue
            file_name = path.rstrip("/").split("/")[-1]

            parsed_url = urlsplit(url)
            protocol = parsed_url.scheme or "http"
            domain = parsed_url.netloc or parsed_url.path.split("/")[0]
            base_url = f"{protocol}://{domain}"
            link = f"{base_url}/{path.lstrip('/')}"
            entry["link"] = entry.get("external_url") or link

            if feed_list_key == "events" and entry.get("days_ago") > 0:
                print(f"Skipping {entry.get('title')} as it is past the date")
                continue

            content = entry.get("content", "").strip()
            entry["content"] = markdownify(content)

            soup = BeautifulSoup(content, "html.parser")
            images = []
            for img in soup.find_all("img"):
                src = img.get("src")
                if not src or src.startswith(("http", "data:")):
                    continue
                alt = img.get("alt", "")
                img_url = f"{base_url}/{src.lstrip('/')}"
                try:
                    response = requests.head(img_url, timeout=5)
                    response.raise_for_status()
                except:
                    continue
                images.append(f"![{alt}]({img_url})")
            entry["images"] = "\n".join(images)

            entry["location"] = entry.get("location", {}).get("name") or ""

            safe_entry = {}
            for key, value in entry.items():
                if value is None:
                    safe_entry[key] = ""
                else:
                    safe_entry[key] = value
            formatted_text = format_string.format(**safe_entry)
            formatted_text = re.sub(r"\n{3,}", "\n\n", formatted_text).strip()

            selected_channels = set()
            effective_subsites = [entry_main_subsite] if entry_main_subsite else entry_subsites
            for group, channels in media_data.items():
                for channel, subsites in channels.items():
                    if any(subsite in effective_subsites for subsite in subsites):
                        selected_channels.add(channel)
            for name, conflicting_names in media_conflicts.items():
                if name in selected_channels:
                    for conflicting in conflicting_names:
                        selected_channels.discard(conflicting)
            new_media = {}
            for group, channels in media_data.items():
                selected_group_channels = []
                for channel in channels:
                    if channel in selected_channels:
                        selected_group_channels.append(channel)
                if selected_group_channels:
                    new_media[group] = selected_group_channels

            def map_config(feed_config):
                new_config = {}
                for channel, config in feed_config.items():
                    if channel in selected_channels:
                        channel_values = []
                        for subsite, values in config.items():
                            if subsite == "all" or subsite in entry_subsites:
                                channel_values += [
                                    v for v in values if v not in channel_values
                                ]
                        if channel_values:
                            new_config[channel] = channel_values
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
                "link": link,
            }

            utils_obj.process_entry(entry_data)


if __name__ == "__main__":
    main()
