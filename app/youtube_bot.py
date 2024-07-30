import os

import feedparser
from dateutil import parser
from markdownify import markdownify
from pytube import Channel
from utils import utils


def main():
    youtube_bot_path = os.environ.get("YOUTUBE_BOT_PATH", "posts/youtube_bot")
    config_name = "youtube_channels"
    utils_obj = utils(youtube_bot_path, config_name)

    for youtube_channel in utils_obj.list:
        if youtube_channel.get("channel") is None:
            raise ValueError(f"No channel url found in the file for {youtube_channel}")
        try:
            channel = Channel(youtube_channel.get("channel"))
            feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel.channel_id}"
            feed_data = feedparser.parse(feed_url)
        except Exception as e:
            print(
                f"Error in parsing feed of {youtube_channel.get('channel')} youtube channel: {e}"
            )
            continue

        folder = feed_data.feed.title.replace(" ", "_").lower()
        format_string = youtube_channel.get("format")
        for entry in feed_data.entries:
            date_entry = (
                entry.get("published") or entry.get("pubDate") or entry.get("updated")
            )
            published_date = parser.isoparse(date_entry).date()

            if entry.link is None:
                print(f"No link found: {entry.title}")
                continue

            file_name = entry.link.split("/")[-1] or entry.link.split("/")[-2]
            file_name = file_name.split("?v=")[-1] if "?v=" in file_name else file_name

            for key, value in entry.items():
                if isinstance(value, list):
                    entry[key] = markdownify(value[0].value).strip()
            entry["media_thumbnail"] = (
                f'![{entry.title}]({entry.media_thumbnail[0]["url"]})'
                if "media_thumbnail" in entry
                else ""
            )
            formatted_text = format_string.format(**entry)

            title = f"Update from Youtube: {entry.link}"
            body = (
                f"This PR is created automatically by a youtube bot.\n"
                f"Update since {utils_obj.start_date.strftime('%Y-%m-%d')}\n\n"
                f"Youtube video processed:\n{[{entry.title}]({entry.link})}"
            )
            entry_data = {
                "title": entry.title,
                "config": youtube_channel,
                "date": published_date,
                "rel_file_path": f"{folder}/{file_name}.md",
                "formatted_text": formatted_text,
                "link": entry.link,
                "pr_title": title,
                "pr_body": body,
            }
            utils_obj.process_entry(entry_data)


if __name__ == "__main__":
    main()
