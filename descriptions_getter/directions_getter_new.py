import sys
from collections import defaultdict
from functools import partial
from multiprocessing.pool import ThreadPool
from urllib.parse import unquote

from bs4 import UnicodeDammit
import json
import requests
import workerpool
import time
import logging
from utils.git_client import *
import multiprocessing
import hashlib
import os
import codecs
from definitions import ROOT_DIR

desc_file_name = os.path.join(ROOT_DIR, "descriptions_getter", "descriptions_v2.txt")
log_file_name = os.path.join(ROOT_DIR, "stops_log.txt")
direction_template = "{0} - {1}"
stop_identity = "{0},{1},{2}={3}"
hash_file_name = os.path.join(ROOT_DIR, "descriptions_getter", "hash_v2.txt")
hash_file_name_temp = os.path.join(ROOT_DIR, "descriptions_getter", "new_hash_v2.txt")
logging.basicConfig(format='[%(asctime)s : %(filename)s] %(message)s', filename=log_file_name, level=logging.INFO)
symbol_to_type = {"bus" : 1, "trolley" : 2, "tram" : 0}
new_type_to_old_type = {1: 1, 2: 0, 4: 2, 3: 3, 5: 5}
stop_identity = "{0},{1},{2}={3}"

url_routes = "https://www.sofiatraffic.bg/bg/trip/getSchedule"
url_lines = "https://www.sofiatraffic.bg/bg/trip/getLines"
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
    payload = {"line_id": line_id}
    try:
        routes = session.post(url_routes, headers=headers, json=payload).json()
    except Exception:
        logging.info("Couldn't get routes from url '{0}'".format(url_routes))
        sys.exit(0)
    return routes

def get_all_routes():
    xsrf_token, session = get_xsrf_token_and_session()
    lines = get_lines(xsrf_token, session)
    line_ids = list(map(lambda line: line["line_id"], lines))
    get_route_partial = partial(get_route, xsrf_token=xsrf_token, session_token=session)
    with ThreadPool(10) as pool:
        routes = pool.map(get_route_partial, line_ids)
    return routes

def get_descriptions():

    all_routes = get_all_routes()
    stop_ids = set()

    for line_route in all_routes:
        route = line_route['routes']
        line = line_route["line"]
        for r in route:
            for segment in r["segments"]:
                stop = segment["stop"]
                stop_id = stop_identity.format(new_type_to_old_type[line["type"]], line["name"], int(stop["code"]), r["name"])
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
    add_file(desc_file_name)
    add_file(hash_file_name)
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

def run_directions_getter(should_upload=False):
    start = time.time()

    logging.info("Generating descriptions...")
    descriptions_all = get_descriptions()
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
        if should_upload:
            upload_coordinates()
    else:
        logging.info("No changes in descriptions.")
    logging.info("Finished gettings {0} descriptions in {1}s".format(len(descriptions_all), time.time() - start))


if __name__ == '__main__':
    run_directions_getter()


