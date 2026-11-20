# Galaxy Social Assistant

## About

This bot automatically creates posts on Galaxy Social by adding pull requests to the [Galaxy Social repository](https://github.com/usegalaxy-eu/galaxy-social/).

## Currently Supported Inputs

* RSS and Atom feeds
* JSON feeds from Galaxy Project
* YouTube
* Citations from Zotero

## In Development

The bot is being extended to support input from:

* GitHub issues and PRs
* Galaxy User Statistics
* Galaxy citations
* Galaxy tools

## Tag feeds

News and events on the [Galaxy Community Hub](https://galaxyproject.org/) can carry tags (e.g. `esg4stars`). For whitelisted tags (see `TAG_FEED_WHITELIST` in the Hub's `astro/src/content.config.ts`), the Hub publishes a combined Atom feed at `/tags/<tag>/feed.atom`.

Tag feeds define **complete, standalone processing rules**. A tag feed only takes effect for items that are also present in the `json_feeds` sections — entries are matched by URL, and items found only in a tag feed are skipped.
For a matching item, a tag feed's rules fully replace the rules of the JSON feeds, but they follow all the regular mechanics:

- the item's `subsites` and `main_subsite` are evaluated against the tag feed's own `media` config, so `media`, `media_conflicts` and `main_media_conflicts` work exactly as in `json_feeds` entries;
- `hashtags` and `mentions` support the `all` key and subsite keys matching the item's `subsites`;

Tag feeds can, optionally, define their own `format`, which then replaces the JSON feed's format.

If several tag feeds match the same item, the first one (in the order they are defined in the config file) wins and the others are skipped.

## Usage

This bot will work automatically and you just need to change the `config.yml` file to config what to be posted and what to include when the PR has been created.
Also the [Galaxy Social bot app](https://github.com/apps/galaxy-social-bot) should be installed on the Galaxy Social repository and the app id and the private key should be given to this repo as variable (vars.APP_ID) and secret (secrets.APP_PRIVATE_KEY).

To try out config changes without posting, run the bot with `DRY_RUN=true`: it will print the files and content it would create instead of creating pull requests (no GitHub token needed).
