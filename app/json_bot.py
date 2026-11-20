import json
import os
import re
from urllib.parse import urlsplit

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser
from markdownify import markdownify
from utils import utils


def normalize_link(link):
    return (link or "").strip().lower().rstrip("/")


def get_base_url(url):
    parsed_url = urlsplit(url)
    protocol = parsed_url.scheme or "http"
    domain = parsed_url.netloc or parsed_url.path.split("/")[0]
    return f"{protocol}://{domain}"


def evaluate_selection(media_data, entry_subsites, entry_main_subsite):
    """Evaluate a feed's media config against an item's subsites.

    Follows the regular feed mechanics: a main_subsite known to this feed's
    config takes precedence over the item's subsites — regular channels are
    then only selected through "global", while main_subsite selects channels
    on its own. Returns (selected_channels, main_channels, channel_groups).
    """
    mapped_subsites = set()
    for group, channel_data in media_data.items():
        for subsites in channel_data.values():
            mapped_subsites.update(subsites)

    main_subsite = entry_main_subsite
    if main_subsite and main_subsite not in mapped_subsites:
        # ignore main_subsite if feed config doesn't know about it
        main_subsite = None
    if main_subsite:
        if "global" in entry_subsites:
            effective_subsites = ["global"]
        else:
            effective_subsites = []
    else:
        effective_subsites = entry_subsites

    selected_channels = set()
    main_channels = set()
    channel_groups = {}
    for group, channels in media_data.items():
        for channel, subsites in channels.items():
            if any(subsite in effective_subsites for subsite in subsites):
                selected_channels.add(channel)
                channel_groups.setdefault(channel, group)
            if main_subsite and main_subsite in subsites:
                main_channels.add(channel)
                channel_groups.setdefault(channel, group)
    return selected_channels, main_channels, channel_groups


def matching_config_values(config, channel, subsites):
    """Collect values configured for a channel under matching subsite keys.

    The special key "all" matches every item.
    """
    values = []
    channel_config = (config or {}).get(channel) or {}
    for subsite, subsite_values in channel_config.items():
        if subsite == "all" or subsite in (subsites or []):
            for value in subsite_values:
                if value not in values:
                    values.append(value)
    return values


def add_config_values(item, config, channels, subsites, key):
    for channel in channels:
        values = item[key].setdefault(channel, [])
        for value in matching_config_values(config, channel, subsites):
            if value not in values:
                values.append(value)


def main():
    json_feed_bot_path = os.environ.get("JSON_BOT_PATH", "posts/json_bot")
    config_name = "json_feeds"
    utils_obj = utils(json_feed_bot_path, config_name)
    tag_feeds = utils_obj.get_config("tag_feeds")

    # Items are collected across all feeds before anything is emitted, keyed by
    # their Hub URL. Tag feeds only take effect for items collected here, so
    # the override has to happen before the per-item files are created.
    items = {}

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
        media_conflicts = feed.get("media_conflicts", {})
        main_media_conflicts = feed.get("main_media_conflicts", {})
        hashtags_data = feed.get("hashtags")
        mentions_data = feed.get("mentions")

        base_url = get_base_url(url)

        for entry in feed_data.get(feed_list_key, []):
            published_date = parser.parse(entry.get("date")).date()

            path = entry.get("path")
            if path is None:
                print(f"No path found: {entry.get('title')}")
                continue

            days_ago = entry.get("days_ago") or 0
            if feed_list_key == "events" and days_ago > 0:
                print(f"Skipping {entry.get('title')} as it is past the date")
                continue

            hub_link = f"{base_url}/{path.lstrip('/')}"
            item_key = normalize_link(hub_link)
            if item_key in items:
                print(f"Skipping duplicate entry: {entry.get('title')}")
                continue

            entry_subsites = entry.get("subsites") or []
            selected_channels, main_channels, channel_groups = evaluate_selection(
                media_data, entry_subsites, entry.get("main_subsite")
            )

            item = {
                "title": entry.get("title"),
                "date": published_date,
                "folder": folder,
                "file_name": path.rstrip("/").split("/")[-1],
                "hub_link": hub_link,
                "base_url": base_url,
                "format": format_string,
                "entry": entry,
                "entry_subsites": entry_subsites,
                "main_subsite": entry.get("main_subsite"),
                "selected_channels": selected_channels,
                "main_channels": main_channels,
                "channel_groups": channel_groups,
                "hashtag_values": {},
                "mention_values": {},
                "media_conflicts": [media_conflicts],
                "main_media_conflicts": [main_media_conflicts],
                "overridden_by": None,
            }
            items[item_key] = item

            selected_and_main = selected_channels | main_channels
            add_config_values(item, hashtags_data, selected_and_main, entry_subsites, "hashtag_values")
            add_config_values(item, mentions_data, selected_and_main, entry_subsites, "mention_values")

    for feed in tag_feeds:
        url = feed.get("url")
        if url is None:
            raise ValueError(f"No url found in the file for tag feed {feed}")
        media_data = feed.get("media")
        if media_data is None:
            raise ValueError(f"No media found in the config file for {feed} in tag_feeds")
        try:
            tag_feed_data = feedparser.parse(url)
        except Exception as e:
            print(f"Error in parsing tag feed {url}: {e}")
            continue

        for entry in tag_feed_data.entries:
            item_key = normalize_link(entry.get("link"))
            item = items.get(item_key)
            if item is None:
                print(
                    f"Skipping tagged item {entry.get('title')}: "
                    f"no matching item in the JSON feeds (outside their time windows?)"
                )
                continue
            if item["overridden_by"]:
                print(
                    f"Skipping tag feed entry {entry.get('title')}: "
                    f"item already handled by tag feed {item['overridden_by']}"
                )
                continue

            # Tag feeds define complete processing rules that override the
            # rules of the JSON feeds for matching items, but they follow the
            # regular feed mechanics: the item's subsites and main_subsite are
            # evaluated against this feed's own media config.
            entry_subsites = item["entry_subsites"]
            item["selected_channels"], item["main_channels"], item["channel_groups"] = evaluate_selection(
                media_data, entry_subsites, item["main_subsite"]
            )
            item["hashtag_values"] = {}
            item["mention_values"] = {}
            item["media_conflicts"] = [feed.get("media_conflicts", {})]
            item["main_media_conflicts"] = [feed.get("main_media_conflicts", {})]

            selected_and_main = item["selected_channels"] | item["main_channels"]
            add_config_values(item, feed.get("hashtags"), selected_and_main, entry_subsites, "hashtag_values")
            add_config_values(item, feed.get("mentions"), selected_and_main, entry_subsites, "mention_values")

            if feed.get("format"):
                item["format"] = feed["format"]
            item["overridden_by"] = feed.get("title") or url

    for item in items.values():
        selected_channels = item["selected_channels"]
        main_channels = item["main_channels"]

        # channels selected through main_subsite suppress regular channels
        for conflicts in item["main_media_conflicts"]:
            for name, conflicting_names in conflicts.items():
                if name in main_channels:
                    selected_channels -= set(conflicting_names)

        # resolve conflicts among the remaining regularly selected channels
        for conflicts in item["media_conflicts"]:
            for name, conflicting_names in conflicts.items():
                if name in selected_channels:
                    selected_channels -= set(conflicting_names)

        final_channels = selected_channels | main_channels
        if not final_channels:
            print(
                f"Skipping {item['title']}: no match between subsites/tag feeds and configured media channels"
            )
            continue

        new_media = {}
        for channel, group in item["channel_groups"].items():
            if channel in final_channels:
                new_media.setdefault(group, []).append(channel)

        json_config = {
            "media": new_media,
            "mentions": {
                channel: values
                for channel, values in item["mention_values"].items()
                if channel in final_channels and values
            },
            "hashtags": {
                channel: values
                for channel, values in item["hashtag_values"].items()
                if channel in final_channels and values
            },
        }

        entry = item["entry"]
        entry["link"] = entry.get("external_url") or item["hub_link"]

        content = entry.get("content", "").strip()
        entry["content"] = markdownify(content)

        soup = BeautifulSoup(content, "html.parser")
        images = []
        for img in soup.find_all("img"):
            src = img.get("src")
            if not src or src.startswith(("http", "data:")):
                continue
            alt = img.get("alt", "")
            img_url = f"{item['base_url']}/{src.lstrip('/')}"
            try:
                response = requests.head(img_url, timeout=5)
                response.raise_for_status()
            except:
                continue
            images.append(f"![{alt}]({img_url})")
        entry["images"] = "\n".join(images)

        entry["location"] = (entry.get("location") or {}).get("name") or ""

        safe_entry = {}
        for key, value in entry.items():
            if value is None:
                safe_entry[key] = ""
            else:
                safe_entry[key] = value
        formatted_text = item["format"].format(**safe_entry)
        formatted_text = re.sub(r"\n{3,}", "\n\n", formatted_text).strip()

        entry_data = {
            "title": item["title"],
            "config": json_config,
            "date": item["date"],
            "rel_file_path": f"{item['folder']}/{item['file_name']}",
            "formatted_text": formatted_text,
            "link": entry["link"],
        }
        utils_obj.process_entry(entry_data)


if __name__ == "__main__":
    main()
