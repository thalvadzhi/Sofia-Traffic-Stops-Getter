from git import Repo
import os
import sys
from definitions import ROOT_DIR

# os.environ['GIT_ASKPASS'] = os.path.join(ROOT_DIR, 'ask_pass.py')
# repo_path = get_info_from_config(ROOT_DIR, "git-repo", "repo_path")
repo = Repo(ROOT_DIR)
assert not repo.bare
index = repo.index
origin = repo.remotes["origin"]

def add_file(filename):
	index.add([filename])

def commit(commit_message):
	index.commit(commit_message)

def push():
	origin.push()

