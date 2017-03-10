import urllib.request
from config_parser import get_info_from_config

key = get_info_from_config("configuration.config", "notification", "key")
url = "https://appnotify.herokuapp.com/notify?to={0}&text={1}"

def push_notification(message):
	urllib.request.urlopen(url.format(key, message.replace(" ", "+")))