import requests
import xml.etree.ElementTree
import urllib.request
import codecs
from bs4 import BeautifulSoup
import json
from pyproj import Proj, transform
from utils.git_client import *
import logging
from optparse import OptionParser
import workerpool
import time
import hashlib
import os
from definitions import ROOT_DIR

log_file_name = os.path.join(ROOT_DIR,"stops_log.txt")

logging.basicConfig(format='[%(asctime)s : %(filename)s] %(message)s', filename=log_file_name, level=logging.INFO)

coord_file_name = os.path.join(ROOT_DIR, "stops_getter", "coordinates.json")
hash_file_name = os.path.join(ROOT_DIR, "stops_getter" ,"hash.txt")
hash_file_name_temp = os.path.join(ROOT_DIR,"stops_getter","hash_new.txt")

class Stop:
    def __init__(self, stopCode, stopName, coordinates, lineTypes):
        self.stopCode = stopCode
        self.coordinates = coordinates
        self.stopName = stopName
        self.lineTypes = lineTypes

    def __eq__(self, other):
        if isinstance(other, Stop):
            return self.stopCode == other.stopCode

    def __hash__(self):
        return hash(self.stopCode)

    def __str__(self):
        return "code: " + str(self.stopCode) + " | stopName: " + str(self.stopName) + " | coordinates: " + str(self.coordinates)


class Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Stop):
            d = obj.__dict__
            d["lineTypes"] = list(d["lineTypes"])
            return d

        return json.JSONEncoder.default(self, obj)

class Decoder(json.JSONDecoder):
    def __init__(self):
        json.JSONDecoder.__init__(self, object_hook=self.deserialize)

    def deserialize(self, d):
        return Stop(d["stopCode"], d["stopName"], d["coordinates"], d["lineTypes"])

stops = set()
code_to_stop = dict()

transportation_types = [1, 2, 3]
base_url_line_ids = "https://www.sofiatraffic.bg/interactivecard/lines/{0}"
base_url_line_information = "https://www.sofiatraffic.bg/interactivecard/lines/stops/geo?line_id={0}"

inProj = Proj(init='epsg:3857')
outProj = Proj(init='epsg:4326')



def get_stops_by_line_id(lineId, lineType):
    resp = requests.get(base_url_line_information.format(lineId), verify=False)
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
            stop = None
            if code in code_to_stop:
                stop = code_to_stop[code]
            else:
                stop = Stop(code, name, coordinates, set())
                code_to_stop[code] = stop
            stop.lineTypes.add(lineType - 1)
            # stops.add(stop)

class DownloadJob(workerpool.Job):
    "Job for downloading a given URL."
    def __init__(self, lineId, lineType):
        self.lineId = lineId
        self.lineType = lineType
    def run(self):
        get_stops_by_line_id(self.lineId, self.lineType)


def calculate_hash():
    stops = code_to_stop.values()
    stops = list(stops)
    stops.sort(key=lambda s: s.stopCode)
    stops_string = json.dumps(stops, cls=Encoder, ensure_ascii=False, indent=4, sort_keys=True).encode()
    sha256 = hashlib.sha256()
    sha256.update(stops_string)
    new_hash = sha256.hexdigest()
    with open(hash_file_name_temp, "w") as f:
        f.write(new_hash)

def get_all_stops():
    pool = workerpool.WorkerPool(size=4)
    logging.info("Initialized getting stop info by line!")
    for transportation_type in transportation_types:
        response = urllib.request.urlopen(base_url_line_ids.format(transportation_type))
        html = response.read()

        soup = BeautifulSoup(html, "html.parser")

        all_inputs = soup.find_all("input")

        for input in all_inputs:
            lineId = input.get("value")
            if lineId != "-1":
                job = DownloadJob(lineId, transportation_type)
                pool.put(job)
    pool.shutdown()
    pool.wait()
    # stops = code_to_stop.values()
    calculate_hash()

    logging.info("Done getting stop info by line!")

def upload_coordinates():
    '''
        uploads the coordinates file to github
    '''
    logging.info("Uploading coordinates to remote server...")
    add_file(coord_file_name)
    add_file(hash_file_name)
    commit("latest update to coordinates")
    push()
    logging.info("Done uploading!")


def coords_have_changed_hash():
    if not os.path.isfile(hash_file_name):
        os.rename(hash_file_name_temp, hash_file_name)
        return True

    with open(hash_file_name_temp, "r") as new, open(hash_file_name, "r") as old:
        new_read = new.read()
        old_read = old.read()
        if old_read != new_read:
            os.remove(hash_file_name)
            os.rename(hash_file_name_temp, hash_file_name)
            return True
        else:
            os.remove(hash_file_name_temp)
            return False

def manage_new_coordinates_information(should_upload, should_push):
    '''
        writes the file containing coordinates only if changes were made compared to the last run of the script
        also upload the file to github if should_upload is true
        push notification if should_push is true
    '''
    stops = code_to_stop.values()
    if len(stops) < 100:
        logging.info("Stops are suspiciosly low, aborting...")
        return
        
    if coords_have_changed_hash():
        logging.info("There are changes in the coordinates file!")
        stops = list(stops)
        stops.sort(key=lambda s: s.stopCode)
        new_coordinates = json.dumps(stops, cls=Encoder, ensure_ascii=False, indent=4, sort_keys=True)
        f = codecs.open(coord_file_name, "w+", "utf-8")
        f.write(new_coordinates)
        f.close()
        if should_upload:
            upload_coordinates()
        if should_push:
            pass
            # push_notification("Stops info has changed!")
    else:
        logging.info("No changes in the coordinates file.")

def prepare_commandline_parser():
    parser = OptionParser()
    parser.add_option("-u", "--upload", action="store_true", dest="should_upload", help="whether to upload to github or not", default=False)
    parser.add_option("-p", "--push", action="store_true", dest="should_push_notification", help="whether should push notification to phone", default=False)
    return parser


def run_stop_getter(should_upload:bool):
    start = time.time()
    get_all_stops()
    manage_new_coordinates_information(should_upload, False)
    end = time.time()
    logging.info("Finished execution in {0}s, downloaded {1} stops".format((end - start), len(code_to_stop.keys())))


if __name__ == '__main__':
    parser = prepare_commandline_parser()
    (options, args) = parser.parse_args()

    run_stop_getter(options.should_upload)