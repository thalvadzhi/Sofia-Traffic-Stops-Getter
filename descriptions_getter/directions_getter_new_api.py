import sys
sys.path.insert(0, '../stops_getter/')
from bs4 import UnicodeDammit
import json
import requests
import workerpool
import time
import logging
from git_client import *
from push_notification import *
import multiprocessing
import hashlib
import os
import codecs

url_routes = "https://routes.sofiatraffic.bg/resources/routes.json"
url_stops = "https://routes.sofiatraffic.bg/resources/stops-bg.json"
desc_file_name = "descriptions.txt"
log_file_name = "desc_log.txt"
direction_template = "{0} - {1}"
stop_identity = "{0},{1},{2}={3}"
hash_file_name = "hash.txt"
hash_file_name_temp = "new_hash.txt"
logging.basicConfig(format='%(asctime)s %(message)s', filename=log_file_name, level=logging.INFO)

symbol_to_type = {"bus" : 1, "trolley" : 2, "tram" : 0}

def get_routes():
    routes = None
    try:
        routes = requests.get(url_routes).json()
    except Exception:
        logging.info("Couldn't get routes from url '{0}'".format(url_routes))
        sys.exit(0)
    return routes

def get_stops():
    stops = None
    try:
        stops = requests.get(url_stops).json()
    except Exception:
        logging.info("Couldn't get stops from url '{0}'".format(url_stops))
        sys.exit(0)
    return stops

def map_code_to_stop(stops):
    code_to_stop = dict()

    for stop in stops:
        code_to_stop[stop['c']] = stop
    return code_to_stop

def get_descriptions_all_stops(stops, routes, code_to_stop):
    stop_ids = set()
    for route in routes:
        line_type = symbol_to_type[route["type"]]
        lines = route["lines"]
        for line in lines:
            name = line["name"]
            line_routes = line["routes"]
            for line_route in line_routes:
                # there is a geo property that you can use( coords of all the stops along the way)
                codes = line_route["codes"]
                # geo = line_route["geo"]
                first = UnicodeDammit(code_to_stop[codes[0]]["n"]).unicode_markup
                last = UnicodeDammit(code_to_stop[codes[len(codes) - 1]]["n"]).unicode_markup
                direction = direction_template.format(first, last)

                for code in codes:
                    stop_id = stop_identity.format(line_type, name, code.lstrip("0"), direction)
                    stop_ids.add(stop_id)
    return list(stop_ids)

def write_to_file(stops_desc):
    with codecs.open(desc_file_name, mode='w', encoding="utf-8") as f:
        f.write(UnicodeDammit(stops_desc).unicode_markup)
    logging.info("Wrote descriptions to file!")


def write_hash_to_file(hash_to_write):
    with open(hash_file_name_temp, "w") as f:
        f.write(hash_to_write)
    logging.info("Wrote hash to file!")

def upload_coordinates():
    logging.info("Uploading changes...")
    add_file('descriptions_getter/' + desc_file_name)
    add_file('descriptions_getter/' + hash_file_name)
    commit("Descriptions update")
    push()
    logging.info("Done uploading!")


def calculate_hash(stops_descs):
    sha256 = hashlib.sha256()
    sha256.update(stops_descs.encode())
    new_hash = sha256.hexdigest()
    return new_hash

def stops_descs_have_changed_hash():
    if not os.path.isfile(hash_file_name):
        os.rename(hash_file_name_temp, hash_file_name)
        return True

    new_read, old_read = None, None
    with open(hash_file_name_temp, "r")as new, open(hash_file_name, "r") as old:
        new_read = new.read()
        old_read = old.read()

    if old_read != new_read:
        os.remove(hash_file_name)
        os.rename(hash_file_name_temp, hash_file_name)
        return True
    else:
        os.remove(hash_file_name_temp)
        return False

def join_stops_desc(stops):
    return ";".join(stops)

def main():
    start = time.time()
    logging.info("Getting stops...")
    stops = get_stops()
    logging.info("Getting routes...")
    routes = get_routes()
    logging.info("Mapping code to stops...")
    code_to_stop = map_code_to_stop(stops)

    logging.info("Generating descriptions...")
    descriptions_all = get_descriptions_all_stops(stops, routes, code_to_stop)
    if len(descriptions_all) < 100:
        # less than 100 descriptions is a suspiciosly low amount
        logging.info("Descriptions are suspiciosly low, aborting...")
        return
    descriptions_all.sort()
    descriptions_single_string = join_stops_desc(descriptions_all)

    hash_new = calculate_hash(descriptions_single_string)
    write_hash_to_file(hash_new)

    if stops_descs_have_changed_hash():
        logging.info("Stops descriptions have changed!")
        write_to_file(descriptions_single_string)
        upload_coordinates()
        push_notification("Descriptions have changed!")
    else:
        logging.info("No changes in descriptions.")
    logging.info("Finished gettings {0} descriptions in {1}s".format(len(descriptions_all), time.time() - start))

if __name__ == '__main__':
    main()


