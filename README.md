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

## Usage

This bot will work automatically and you just need to change the `config.yml` file to config what to be posted and what to include when the PR has been created.
Also the [Galaxy Social bot app](https://github.com/apps/galaxy-social-bot) should be installed on the Galaxy Social repository and the app id and the private key should be given to this repo as variable (vars.APP_ID) and secret (secrets.APP_PRIVATE_KEY).
