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
            self.configs = yaml.safe_load(file)

        if self.configs is None:
            raise ValueError("No config found in the file")

        self.list = self.configs.get(item_type)
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

        self.existing_files = set(
            pr_file.filename
            for pr in self.repo.get_pulls(state="open")
            for pr_file in pr.get_files()
            if pr_file.filename.startswith(self.bot_path)
        )
        git_tree = self.repo.get_git_tree(self.repo.default_branch, recursive=True)
        self.existing_files.update(
            file.path
            for file in git_tree.tree
            if file.path.startswith(self.bot_path) and file.path.endswith(".md")
        )
        self.branch_name = (
            f"{self.bot_path}-update-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        self.repo.create_git_ref(
            ref=f"refs/heads/{self.branch_name}",
            sha=self.repo.get_branch("main").commit.sha,
        )
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

        file_path = f"{self.bot_path}/{rel_file_path}"

        if date < self.start_date:
            print(f"Skipping as it is older: {title}")
            return False

        if file_path in self.existing_files:
            print(f"Skipping as file already exists: {file_path} for {title}")
            return False

        print(f"Processing {file_path} from {title}")

        md_config = yaml.dump(
            {
                key: config[key]
                for key in ["media", "mentions", "hashtags"]
                if key in config
            }
        )

        md_content = f"---\n{md_config}---\n{formatted_text}"

        self.repo.create_file(
            path=file_path,
            message=f"Add {title}",
            content=md_content,
            branch=self.branch_name,
        )
        return True

    def create_pull_request(self, title, body):
        base_sha = self.repo.get_branch("main").commit.sha
        compare_sha = self.repo.get_branch(self.branch_name).commit.sha
        comparison = self.repo.compare(base_sha, compare_sha).total_commits

        if comparison == 0:
            self.repo.get_git_ref(f"heads/{self.branch_name}").delete()
            print(f"No new item found.\nRemoving branch {self.branch_name}")
            return False

        try:
            pr = self.repo.create_pull(
                title=title,
                body=body,
                base="main",
                head=self.branch_name,
            )
            print(f"PR created: {pr.html_url}")
            return True
        except GithubException as e:
            self.repo.get_git_ref(f"heads/{self.branch_name}").delete()
            print(
                f"Error in creating PR: {e.data.get('errors')[0].get('message')}\nRemoving branch {self.branch_name}"
            )
            return False
