from git import Repo
from config_parser import get_info_from_config

repo_path = get_info_from_config("configuration.config", "git-repo", "repo_path")
repo = Repo(repo_path)
assert not repo.bare
index = repo.index
origin = repo.remotes["origin"]

def add_file(filename):
	index.add([filename])

def commit(commit_message):
	index.commit(commit_message)

def push():
	origin.push()

