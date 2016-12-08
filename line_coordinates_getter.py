import requests
import xml.etree.ElementTree
import urllib.request
import codecs
from bs4 import BeautifulSoup
import json
from pyproj import Proj, transform

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
				
			
for transportation_type in transportation_types:
	response = urllib.request.urlopen(base_url_line_ids.format(transportation_type))
	html = response.read()

	soup = BeautifulSoup(html, "html.parser")

	all_inputs = soup.find_all("input")

	for input in all_inputs:
		lineId = input.get("value")
		if lineId != "-1":
			get_stops_by_line_id(lineId)
		
json_repr = json.dumps(stops, cls=Encoder, ensure_ascii=False, indent=4)

print("Number of stops: {0}".format(len(stops)))

f = codecs.open("coordinates.json", "w+", "utf-8")
f.write(json_repr)
f.close()
	
	