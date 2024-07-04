import sys
from functools import partial

import polyline
from bs4 import UnicodeDammit
import shapely
import json
import requests
import workerpool
import time
import logging

from shapely import geometry, ops

from utils.git_client import *
import multiprocessing
import hashlib
import os
import codecs
from definitions import ROOT_DIR
from urllib.parse import unquote
from multiprocessing.pool import ThreadPool
url_routes = "https://www.sofiatraffic.bg/bg/trip/getSchedule"
url_lines = "https://www.sofiatraffic.bg/bg/trip/getLines"
polyline_file = os.path.join(ROOT_DIR, "polyline_getter", "polyline_v2.txt")
log_file_name = os.path.join(ROOT_DIR, "stops_log.txt")
logging.basicConfig(format='[%(asctime)s : %(filename)s] %(message)s', filename=log_file_name, level=logging.INFO)
hash_file_name = os.path.join(ROOT_DIR, "polyline_getter", "hash_v2.txt")
hash_file_name_temp = os.path.join(ROOT_DIR,"polyline_getter" ,"new_hash_v2.txt")
symbol_to_type = {"bus" : 1, "trolley" : 2, "tram" : 0}
new_type_to_old_type = {1: 1, 2: 0, 4: 2, 3: 3, 5: 5}

def get_xsrf_token_and_session():
    resp = requests.get("https://www.sofiatraffic.bg/")
    return resp.cookies["XSRF-TOKEN"], resp.cookies["sofia_traffic_session"]

def get_lines(xsrf_token, session_token):
    lines = None
    url_lines = "https://www.sofiatraffic.bg/bg/trip/getLines"
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
        routes = requests.post(url_routes, headers=headers, json=payload).json()
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


def transform_new_route_to_old_route_format(new_route_format):
    line = new_route_format["line"]
    name = line["name"]
    type = new_type_to_old_type[line["type"]]
    routes = new_route_format["routes"]
    old_routes = []
    for route in routes:
        details = route["details"]
        poly = details["polyline"]
        if not poly.endswith(")"):
            poly = poly.rsplit(",", 1)[0] + ")"

        segments = route["segments"]
        if not segments:
            continue

        decoded_poly = shapely.get_coordinates(shapely.from_wkt(poly, on_invalid="raise")).tolist()
        inverted_decoded = []
        for coord_tuple in decoded_poly:
            inverted_decoded.append((coord_tuple[1], coord_tuple[0]))

        poly_str = polyline.encode(inverted_decoded)

        first_stop = segments[0]["stop"]["code"]
        last_stop = segments[-1]["end_stop"]["code"]
        old_route = {
            "first_stop": int(first_stop),
            "last_stop": int(last_stop),
            "geo": poly_str,
            "name": name,
            "type": type
        }
        old_routes.append(old_route)
    return old_routes

def get_polys():
    routes = get_all_routes()
    all_old_routes = []
    for route in routes:
        old_routes = transform_new_route_to_old_route_format(route)
        all_old_routes += old_routes
    return all_old_routes

def write_to_file(polyline):
    with codecs.open(polyline_file, mode='w', encoding="utf-8") as f:
        f.write(UnicodeDammit(polyline).unicode_markup)
    logging.info("Wrote polys to file!")

def write_hash_to_file(hash_to_write):
    with open(hash_file_name_temp, "w") as f:
        f.write(hash_to_write)
    logging.info("Wrote hash to file!")

def calculate_hash(line_polys):
    sha256 = hashlib.sha256()
    sha256.update(line_polys.encode())
    new_hash = sha256.hexdigest()
    return new_hash

def upload_polyline():
    logging.info("Uploading changes...")
    add_file(polyline_file)
    add_file(hash_file_name)
    commit("Polyline update")
    push()
    logging.info("Done uploading!")

def polys_have_changed_hash():
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



def run_polyline_getter(should_upload=False):
    start = time.time()
    polys = get_polys()
    polys.sort(key=lambda s: s["name"])
    polys.sort(key=lambda s: s["type"])
    polys_string = json.dumps(polys, ensure_ascii=False, indent=4, sort_keys=True)
    polys_hash = calculate_hash(polys_string)
    write_hash_to_file(polys_hash)

    if polys_have_changed_hash():
        logging.info("Polys have changed!")
        write_to_file(polys_string)
        if should_upload:
            upload_polyline()
    else:
        logging.info("No changes in polylines")
    end = time.time()
    logging.info("Finished execution in {0}s, downloaded {1} lines".format((end - start), len(polys)))

if __name__ == '__main__':
    run_polyline_getter()

