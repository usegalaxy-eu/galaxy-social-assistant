import os
from datetime import datetime, timedelta

import yaml
from github import Github, GithubException


class utils:
    def __init__(self, bot_path, item_type):
        self.bot_path = bot_path

        config_file = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                os.environ.get("CONFIG_FILE", "config.yml"),
            )
        )
        with open(config_file, "r") as file:
            configs = yaml.safe_load(file)

        if configs is None:
            raise ValueError("No config found in the file")

        self.list = configs.get(item_type)
        if self.list is None:
            raise ValueError(f"No {item_type} found in the config file")

        for list_items in self.list:
            if list_items.get("media") is None:
                raise ValueError(
                    f"No media found in the config file for {list_items} in {item_type}"
                )
            elif list_items.get("format") is None:
                raise ValueError(
                    f"No format found in the config file for {list_items} in {item_type}"
                )

        access_token = os.environ.get("GALAXY_SOCIAL_BOT_TOKEN")
        repo_name = os.environ.get("REPO")
        g = Github(access_token)
        self.repo = g.get_repo(repo_name)

        self.existing_files = {
            pr.title
            for pr in g.search_issues(
                f"repo:{repo_name} is:pr base:main head:{self.bot_path}"
            )
        }

        self.start_date = datetime.now().date() - timedelta(
            days=int(os.environ.get("DAYS", 1))
        )
        print(f"Processing items since {self.start_date}.")

    def process_entry(self, entry):
        title = entry.get("title")
        config = entry.get("config")
        date = entry.get("date")
        rel_file_path = entry.get("rel_file_path")
        formatted_text = entry.get("formatted_text")
        pr_title = entry.get("pr_title")
        pr_body = entry.get("pr_body")

        file_path = f"{self.bot_path}/{rel_file_path}"

        if date < self.start_date:
            print(f"Skipping as it is older: {title}")
            return False

        if entry.get("link") in self.existing_files:
            print(f"Skipping as file already exists: {file_path} for {title}")
            return False

        print(f"Processing {file_path} from {title}")

        md_config = yaml.dump(
            {
                key: config[key]
                for key in ["media", "mentions", "hashtags"]
                if key in config
            },
            sort_keys=False,
        )

        md_content = f"---\n{md_config}---\n{formatted_text}"

        branch_name = f"{file_path}-update-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.repo.create_git_ref(
            ref=f"refs/heads/{branch_name}",
            sha=self.repo.get_branch("main").commit.sha,
        )
        self.repo.create_file(
            path=file_path,
            message=f"Add {title}",
            content=md_content,
            branch=branch_name,
        )

        try:
            pr = self.repo.create_pull(
                title=pr_title,
                body=pr_body,
                base="main",
                head=branch_name,
            )
            print(f"PR created: {pr.html_url}")
            return True
        except GithubException as e:
            self.repo.get_git_ref(f"heads/{branch_name}").delete()
            print(
                f"Error in creating PR: {e.data.get('errors')[0].get('message')}\nRemoving branch {branch_name}"
            )
            return False
