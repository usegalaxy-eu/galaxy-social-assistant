import os
from datetime import datetime, timedelta

import yaml
from github import Github, GithubException


class utils:
    def __init__(self, bot_path, item_type):
        self.bot_path = bot_path
        self.item_type = item_type

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

        self.list = configs.get(self.item_type)
        if self.list is None:
            raise ValueError(f"No {self.item_type} found in the config file")

        errors = []
        for item in self.list:
            if item.get("media") is None:
                errors.append(
                    f"No media found in the config file for {item} in {self.item_type}"
                )
            if item.get("format") is None:
                errors.append(
                    f"No format found in the config file for {item} in {self.item_type}"
                )
        if errors:
            raise ValueError("\n".join(errors))

        access_token = os.environ.get("GALAXY_SOCIAL_BOT_TOKEN")
        repo_name = os.environ.get("REPO")
        g = Github(access_token)
        self.repo = g.get_repo(repo_name)

        self.existing_files = set()
        for pr in g.search_issues(
            f"repo:{repo_name} is:pr base:main head:{self.bot_path}"
        ):
            self.existing_files.add(pr.title)

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
        link = entry.get("link")

        file_path = f"{self.bot_path}/{rel_file_path}"

        if date < self.start_date:
            print(f"Skipping as it is older: {title}")
            return False

        if any(link in pr_title for pr_title in self.existing_files):
            print(f"Skipping as file already exists: {file_path} for {title}")
            return False

        print(f"Processing {file_path} from {title}")

        branch_name = f"{file_path}-update-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.repo.create_git_ref(
            ref=f"refs/heads/{branch_name}",
            sha=self.repo.get_branch("main").commit.sha,
        )

        for media_group in config.get("media"):
            config_dict = {"media": media_group}
            for key in ["mentions", "hashtags"]:
                if key in config:
                    config_dict[key] = {
                        media: config[key][media]
                        for media in media_group
                        if media in config[key]
                    }

            md_config = yaml.dump(config_dict, sort_keys=False)

            md_content = f"---\n{md_config}---\n{formatted_text}"

            self.repo.create_file(
                path=f"{file_path}-{'_'.join(media_group)}.md",
                message=f"Add {title} for {', '.join(media_group)}",
                content=md_content,
                branch=branch_name,
            )

        pr_title = f"Update from {self.item_type}: {link}"
        pr_body = (
            f"This PR is created automatically by a {self.item_type} bot.\n"
            f"Update since {self.start_date.strftime('%Y-%m-%d')}\n\n"
            f"Processed:\n[{title}]({link})"
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
