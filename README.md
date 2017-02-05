## Installation
> Note this code only works with python 3.* 

First run `pip install -r requirements.txt`.

If you have more than one python version installed, to use python 3's pip instead run `python3 -m pip install -r requirements.txt`.

## Prerequisites

The script expects to find a config file named `configuration.config ` in the following format:

```
[git-repo]
repo_path = <PATH_TO_FOLDER_CONTAINING_GIT_REPO>

[coord]
coord_file_name = <COORDINATE_FILE_NAME>.json

[log]
log_file_name = <LOG_FILE_NAME>.log

```
The git repo should have its user.name and user.email set. Also it expects that the username and password for the remote repo are stored.

## Usage

To get all stop information run `python line_coordinates.py`

The script will generate a <LOG_FILE_NAME>.log file containing information about when it tried to obtain stop data and when it found that the data has changed and tried to upload it to github.

## Bonus

To clean the log file once a month and run the script once a day use the following jobs in cron:
```
0 0 1 * * rm <PATH_TO_REPO>/<LOG_FILE_NAME>.log
0 0 * * * cd <PATH_TO_REPO> && python3 <PATH_TO_REPO>/line_coordinates_getter.py
```

