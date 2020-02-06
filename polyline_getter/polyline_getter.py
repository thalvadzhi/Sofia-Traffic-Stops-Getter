import sys         
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
url_routes = "https://routes.sofiatraffic.bg/resources/routes.json"

polyline_file = os.path.join(ROOT_DIR, "polyline_getter","polyline.txt")
log_file_name = os.path.join(ROOT_DIR, "stops_log.txt")
logging.basicConfig(format='[%(asctime)s : %(filename)s] %(message)s', filename=log_file_name, level=logging.INFO)
hash_file_name = os.path.join(ROOT_DIR, "polyline_getter", "hash.txt")
hash_file_name_temp = os.path.join(ROOT_DIR,"polyline_getter" ,"new_hash.txt")
symbol_to_type = {"bus" : 1, "trolley" : 2, "tram" : 0}


def get_routes():
    routes = None
    try:
        routes = requests.get(url_routes,verify=False).json()
    except Exception:
        logging.info("Couldn't get routes from url '{0}'".format(url_routes))
        sys.exit(0)
    return routes

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
    add_file(+ polyline_file)
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

def get_all_polys():
    routes = get_routes()
    line_polys = []
    for tr_type in routes:
        route_type = symbol_to_type[tr_type["type"]]
        lines = tr_type["lines"]
        for line in lines:
            name = line["name"]
            line_routes = line["routes"]
            for line_route in line_routes:
                codes = line_route["codes"]
                first = codes[0].lstrip("0")
                last = codes[len(codes) - 1].lstrip("0")
                geo = line_route["geo"]
                line_poly = {"type" : route_type, "name": name, "first_stop": first, "last_stop": last, "geo": geo}
                line_polys.append(line_poly)
    return line_polys

def run_polyline_getter(should_upload=False):
    start = time.time()
    polys = get_all_polys()
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
