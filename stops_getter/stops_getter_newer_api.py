from collections import defaultdict
from functools import partial
# from multiprocessing.pool import ThreadPool
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote

import requests
import xml.etree.ElementTree
import urllib.request
import codecs
from bs4 import BeautifulSoup
import json
# from pyproj import Proj, transform
from utils.git_client import *
import logging
from optparse import OptionParser
import workerpool
import time
import hashlib
import os
from itertools import chain
from definitions import ROOT_DIR

log_file_name = os.path.join(ROOT_DIR, "stops_log.txt")

# url_routes = "https://routes.sofiatraffic.bg/resources/routes.json"
# url_stops = "https://routes.sofiatraffic.bg/resources/stops-bg.json"

logging.basicConfig(format='[%(asctime)s : %(filename)s] %(message)s', level=logging.INFO)

coord_file_name = os.path.join(ROOT_DIR, "stops_getter", "coordinates_v2.json")
hash_file_name = os.path.join(ROOT_DIR, "stops_getter" , "hash_v2.txt")
hash_file_name_temp = os.path.join(ROOT_DIR,"stops_getter", "hash_new_v2.txt")
new_type_to_old_type = {1: 1, 2: 0, 4: 2, 3: 3, 5: 5}

url_routes = "https://www.sofiatraffic.bg/bg/trip/getSchedule"
url_lines = "https://www.sofiatraffic.bg/bg/trip/getLines"

url_routes_old = "https://routes.sofiatraffic.bg/resources/routes.json"
url_stops_old = "https://routes.sofiatraffic.bg/resources/stops-bg.json"

session = requests.Session()
def get_xsrf_token_and_session():
    resp = requests.get("https://www.sofiatraffic.bg/")
    return resp.cookies["XSRF-TOKEN"], resp.cookies["sofia_traffic_session"]
def get_lines(xsrf_token, session_token):
    lines = None
    headers = {"cookie": f"XSRF-TOKEN={xsrf_token}; sofia_traffic_session={session_token}", "x-xsrf-token": unquote(xsrf_token)}
    try:
        lines = requests.post(url_lines, headers=headers).json()
    except Exception:
        logging.exception("Couldn't get lines from url '{0}'".format(url_lines))
    return lines
def get_route(line_id, xsrf_token, session_token):
    routes = None
    headers = {"cookie": f"XSRF-TOKEN={xsrf_token}; sofia_traffic_session={session_token}", "x-xsrf-token": unquote(xsrf_token)}
    payload = {"ext_id": line_id}
    try:
        routes = session.post(url_routes, headers=headers, json=payload).json()
    except Exception:
        logging.exception("Couldn't get routes from url '{0}', payload: {1}".format(url_routes, payload))
        sys.exit(0)
    return routes

def get_all_routes():
    xsrf_token, session = get_xsrf_token_and_session()
    lines = get_lines(xsrf_token, session)
    line_ids = list(map(lambda line: line["ext_id"], lines))
    get_route_partial = partial(get_route, xsrf_token=xsrf_token, session_token=session)
    with ThreadPoolExecutor(10) as pool:
        routes = pool.map(get_route_partial, line_ids)
    return routes


class Stop:
    def __init__(self, stopCode, stopName, coordinates, lineTypes, lineNames, extStopCode):
        self.stopCode = stopCode
        self.coordinates = coordinates
        self.stopName = stopName
        self.lineTypes = lineTypes
        self.lineNames = lineNames
        self.extStopCode = extStopCode

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
            d["lineTypes"] = sorted(list(d["lineTypes"]))
            d["lineNames"] = sorted(list(d["lineNames"]))
            return d

        return json.JSONEncoder.default(self, obj)

class Decoder(json.JSONDecoder):
    def __init__(self):
        json.JSONDecoder.__init__(self, object_hook=self.deserialize)

    def deserialize(self, d):
        return Stop(d["stopCode"], d["stopName"], d["coordinates"], d["lineTypes"])



def calculate_hash(stops):
    stops.sort(key=lambda s: s.stopCode)
    stops_string = json.dumps(stops, cls=Encoder, ensure_ascii=False, indent=4, sort_keys=True).encode()
    sha256 = hashlib.sha256()
    sha256.update(stops_string)
    new_hash = sha256.hexdigest()
    with open(hash_file_name_temp, "w") as f:
        f.write(new_hash)

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

def manage_new_coordinates_information(stops, should_upload):
    '''
        writes the file containing coordinates only if changes were made compared to the last run of the script
        also upload the file to github if should_upload is true
        push notification if should_push is true
    '''
    if len(stops) < 100:
        logging.info("Stops are suspiciously low, aborting...")
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

    else:
        logging.info("No changes in the coordinates file.")

def prepare_commandline_parser():
    parser = OptionParser()
    parser.add_option("-u", "--upload", action="store_true", dest="should_upload", help="whether to upload to github or not", default=False)
    return parser

def get_stops(all_routes):
    stop_code_to_line_type = defaultdict(set)
    stop_code_to_line_names = defaultdict(set)
    stops = set()
    stop_code_to_stop = dict()


    for line_route in all_routes:
        route = line_route['routes']
        line = line_route["line"]
        for r in route:
            for segment in r["segments"]:
                stop = segment["stop"]
                s = Stop(stopCode=int(stop["code"]), stopName=stop["name"],
                     coordinates=[float(stop["latitude"]), float(stop["longitude"])], extStopCode=stop["ext_id"], lineTypes=None, lineNames=None)
                stop_code_to_stop[stop["code"]] = s
                stop_code_to_line_type[stop["code"]].add(new_type_to_old_type[line["type"]])
                stop_code_to_line_names[stop["code"]].add((f"\"{line['name']}\"", new_type_to_old_type[line["type"]], line["id"]))
    for stop_code, stop in stop_code_to_stop.items():
        line_type = stop_code_to_line_type[stop_code]
        line_names = stop_code_to_line_names[stop_code]
        stop.lineTypes = line_type
        stop.lineNames = line_names
        stops.add(stop)
    return list(stops)


def run_stop_getter(should_upload: bool):
    start = time.time()
    all_routes = get_all_routes()
    subway_routes = filter(lambda route: route["line"]["type"] == 3, all_routes)

    ground_routes = filter(lambda route: route["line"]["type"] != 3, all_routes)

    subway_stops = get_stops(subway_routes)
    ground_stops = get_stops(ground_routes)
    stops = ground_stops + subway_stops
    calculate_hash(stops)
    manage_new_coordinates_information(stops, should_upload)
    end = time.time()
    logging.info("Finished execution in {0}s, downloaded {1} stops".format((end - start), len(stops)))


if __name__ == '__main__':
    parser = prepare_commandline_parser()
    (options, args) = parser.parse_args()

    run_stop_getter(options.should_upload)
