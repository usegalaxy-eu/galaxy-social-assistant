import os

from dateutil import parser
from pyzotero import zotero, zotero_errors
from utils import utils


def main():
    citation_bot_path = os.environ.get("CITATION_BOT_PATH", "posts/citation_bot")
    config_name = "citations"
    utils_obj = utils(citation_bot_path, config_name)

    for citation in utils_obj.list:
        if citation.get("zotero_group_id") is None:
            raise ValueError(
                f"No zotero group id found in the file for citation {citation}"
            )
        try:
            zot = zotero.Zotero(citation.get("zotero_group_id"), "group")
            if citation.get("tag"):
                zot.add_parameters(tag=citation.get("tag"))
            try:
                items = zot.everything(zot.top())
            except zotero_errors.HTTPError:
                # try again
                items = zot.everything(zot.top())
        except Exception as e:
            print(
                f"Error in connecting to zotero group {citation.get('zotero_group_id')}: {e}"
            )
            continue

        folder = citation.get("zotero_group_id")
        format_string = citation.get("format")
        for item in items:
            data = item["data"]

            data["title"] = (
                data.get("title", "").encode("ASCII", "ignore").decode("ASCII")
            )
            data["creators"] = ", ".join(
                (
                    f"{creator.get('lastName', '')}, {creator.get('firstName', '')[0]}."
                    if creator.get("firstName") is not None
                    else f"{creator.get('lastName', '')}"
                )
                for creator in data.get("creators", [])[:3]
            ) + (", et. al." if len(data.get("creators", [])) > 3 else "")

            data["dateAdded"] = (
                parser.isoparse(data["dateAdded"]).date() if "dateAdded" in data else ""
            )

            formatted_text = format_string.format(**data)

            entry_data = {
                "title": data["title"],
                "config": citation,
                "date": data["dateAdded"],
                "rel_file_path": f"{folder}/{item['key']}",
                "formatted_text": formatted_text,
                "link": data.get("url"),
            }
            utils_obj.process_entry(entry_data)


if __name__ == "__main__":
    main()
