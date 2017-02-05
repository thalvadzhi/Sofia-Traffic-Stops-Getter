import requests
import xml.etree.ElementTree
import urllib.request
import codecs
from bs4 import BeautifulSoup
import json
from pyproj import Proj, transform
from config_parser import get_info_from_config
from git_client import *
import logging
from optparse import OptionParser
from push_notification import push_notification
import workerpool
import time
log_file_name = get_info_from_config("configuration.config", "log", "log_file_name")
logging.basicConfig(format='%(asctime)s %(message)s', filename=log_file_name, level=logging.INFO)

coord_file_name = get_info_from_config("configuration.config", "coord", "coord_file_name")

class Stop:
	def __init__(self, stopCode, stopName, coordinates):
		self.stopCode = stopCode
		self.coordinates = coordinates
		self.stopName = stopName
		
	def __eq__(self, other):
		if isinstance(other, Stop):
			return self.stopCode == other.stopCode
			

class Encoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, Stop):
			return obj.__dict__
		
		return json.JSONEncoder.default(self, obj)
        
		
stops = []


transportation_types = [1, 2, 3]
base_url_line_ids = "https://www.sofiatraffic.bg/interactivecard/lines/{0}"
base_url_line_information = "https://www.sofiatraffic.bg/interactivecard/lines/stops/geo?line_id={0}"

inProj = Proj(init='epsg:3857')
outProj = Proj(init='epsg:4326')



def get_stops_by_line_id(lineId):
	resp = requests.get(base_url_line_information.format(lineId))
	d = resp.json()

	if 'features' in d:
		features = resp.json()['features']
		for stop in features:
			properties = stop['properties']
			code = properties['code']
			name = properties['name']
			geometry = stop['geometry']
			x, y = geometry['coordinates']
			x, y = float(x), float(y)
			x_new, y_new = transform(inProj, outProj, x, y)
			coordinates = [y_new, x_new]
			stop = Stop(code, name, coordinates)
			if(stop not in stops):
				stops.append(stop)

class DownloadJob(workerpool.Job):
    "Job for downloading a given URL."
    def __init__(self, lineId):
        self.lineId = lineId # The url we'll need to download when the job runs
    def run(self):
        get_stops_by_line_id(lineId)
				
def get_all_stops():
	pool = workerpool.WorkerPool(size=8)
	logging.info("Initialized getting stop info by line!")
	for transportation_type in transportation_types:
		response = urllib.request.urlopen(base_url_line_ids.format(transportation_type))
		html = response.read()

		soup = BeautifulSoup(html, "html.parser")

		all_inputs = soup.find_all("input")

		for input in all_inputs:
			lineId = input.get("value")
			if lineId != "-1":
				job = DownloadJob(lineId)
				pool.put(job)
	pool.shutdown()
	pool.wait()
	logging.info("Done getting stop info by line!")
	

	


def upload_coordinates():
	'''
		uploads the coordinates file to github
	'''
	logging.info("Uploading coordinates to remote server...")
	add_file(coord_file_name)
	commit("latest update to coordinates")
	push()
	logging.info("Done uploading!")
	
def coords_have_changed(new_coordinates, old_coordinates):
	for stop in new_coordinates:
		if stop not in old_coordinates:
			return True
	return False
				
def manage_new_coordinates_information(should_upload, should_push):
	'''
		writes the file containing coordinates only if changes were made compared to the last run of the script
		also upload the file to github if should_upload is true
		push notification if should_push is true
	'''	
	old_coordinates = ""
	old_coordinates_dict = {}
			
	try:
		with codecs.open(coord_file_name,'r', encoding='utf-8') as myfile:
			old_coordinates = myfile.read().replace('\n', '')
	except FileNotFoundError:
		old_coordinates = None

	if old_coordinates is not None:
		old_coordinates_dict = json.loads(old_coordinates)

	new_coordinates_dict = [stop.__dict__ for stop in stops]
		

	if coords_have_changed(new_coordinates_dict, old_coordinates_dict):
		logging.info("There are changes in the coordinates file!")
		new_coordinates = json.dumps(stops, cls=Encoder, ensure_ascii=False, indent=4)
		f = codecs.open(coord_file_name, "w+", "utf-8")
		f.write(new_coordinates)
		f.close()
		if should_upload:
			upload_coordinates()
		if should_push:
			push_notification("Stops info has changed!")
	else:
		logging.info("No changes in the coordinates file.")

def prepare_commandline_parser():
	parser = OptionParser()
	parser.add_option("-u", "--upload", action="store_true", dest="should_upload", help="whether to upload to github or not", default=False)
	parser.add_option("-p", "--push", action="store_true", dest="should_push_notification", help="whether should push notification to phone", default=False)
	return parser
	
if __name__ == '__main__':
	start = time.time()
	parser = prepare_commandline_parser()
	(options, args) = parser.parse_args()
	
	get_all_stops()
	manage_new_coordinates_information(options.should_upload, options.should_push_notification)
	end = time.time()
	print("Finished downloading {0} stops in {0}s".format(len(stops), (end - start)))
