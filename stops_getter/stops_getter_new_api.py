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

url_routes = "https://routes.sofiatraffic.bg/resources/routes.json"
url_stops = "https://routes.sofiatraffic.bg/resources/stops-bg.json"

logging.basicConfig(format='[%(asctime)s : %(filename)s] %(message)s', filename=log_file_name, level=logging.INFO)

coord_file_name = os.path.join(ROOT_DIR, "stops_getter", "coordinates.json")
hash_file_name = os.path.join(ROOT_DIR, "stops_getter" ,"hash.txt")
hash_file_name_temp = os.path.join(ROOT_DIR,"stops_getter","hash_new.txt")

def get_routes_from_sumc():
    routes = None
    try:
        routes = requests.get(url_routes).json()
    except Exception:
        logging.info("Couldn't get routes from url '{0}'".format(url_routes))
        sys.exit(0)
    return routes

def get_stops_from_sumc():
    stops = None
    try:
        stops = requests.get(url_stops).json()
    except Exception:
        logging.info("Couldn't get stops from url '{0}'".format(url_stops))
        sys.exit(0)
    return stops

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

def get_routes_for_lines(lines):
    return list(map(lambda line: line["routes"], lines))

def get_codes_for_routes(routes):
    return list(map(lambda route: route["codes"], routes))

def get_codes_for_lines(lines)->set:
    routes = get_routes_for_lines(lines)
    routes = list(chain.from_iterable(routes))
    codes = get_codes_for_routes(routes)
    #flatten codes
    return set(map(lambda code: int(code),chain.from_iterable(codes)))

def get_codes_per_line_type(routes:dict) -> dict:
    """Returns a dict where the key is the line type: [0, 1, 2] and the value is a set
    of all the stop codes of stops that have a line type of the kind stopping on them.

    For e.g. if stop code 1234 is in the set of codes for line type 0 it means that some line of type 0 
    stops on this Stop.
    """
    bus_lines = routes[0]["lines"]
    trolley_lines = routes[1]["lines"]
    tram_lines = routes[2]['lines']

    bus_line_codes = get_codes_for_lines(bus_lines)
    tram_line_codes = get_codes_for_lines(tram_lines)
    trolley_line_codes = get_codes_for_lines(trolley_lines)
    print(len(bus_line_codes.union(tram_line_codes).union(trolley_line_codes)))
    return {
        0: bus_line_codes,
        1: tram_line_codes,
        2: trolley_line_codes
    }

def get_line_types_at_stop(stop_code, codes_per_line_type):
    line_types_for_stop_code = set()
    for line_type in codes_per_line_type.keys():
        if stop_code in codes_per_line_type[line_type]:
            line_types_for_stop_code.add(line_type)
    return line_types_for_stop_code



def get_all_stops():
    logging.info("Started getting stop info!")

    routes = get_routes_from_sumc()
    stops_sumc = get_stops_from_sumc()
    codes_per_line_type = get_codes_per_line_type(routes)

    stops = set()
    code_to_stop = dict()

    for stop_sumc in stops_sumc:
        stop_code = int(stop_sumc["c"])
        stop_name = stop_sumc["n"]
        coordinates = [stop_sumc["y"], stop_sumc["x"]]
        line_types = get_line_types_at_stop(stop_code, codes_per_line_type)
        stop = Stop(stop_code, stop_name, coordinates, line_types)
        stops.add(stop)
        code_to_stop[stop_code] = stop

    calculate_hash(stops, code_to_stop)
    logging.info("Done getting stop info by line!")

    return stops, code_to_stop


def calculate_hash(stops, code_to_stop):
    stops = code_to_stop.values()
    stops = list(stops)
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

def manage_new_coordinates_information(code_to_stop, should_upload, should_push):
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
    stops, code_to_stop = get_all_stops()
    manage_new_coordinates_information(code_to_stop, should_upload, False)
    end = time.time()
    logging.info("Finished execution in {0}s, downloaded {1} stops".format((end - start), len(code_to_stop.keys())))


if __name__ == '__main__':
    parser = prepare_commandline_parser()
    (options, args) = parser.parse_args()

    run_stop_getter(options.should_upload)