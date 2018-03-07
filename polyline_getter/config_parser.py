import configparser

config_parser = configparser.RawConfigParser()

def get_info_from_config(config_file_path, config_name, key):
	config_parser.read(config_file_path)
	return config_parser.get(config_name, key)
