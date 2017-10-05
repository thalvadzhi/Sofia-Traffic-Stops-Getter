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

linesBaseURL = "https://api.sofiatransport.com/v3/lines/{0}"
linesStopsURL = "https://api.sofiatransport.com/v3/lines/{0}/{1}"
desc_file_name = "descriptions.txt"
log_file_name = "desc_log.txt"
direction_template = "{0} - {1}"
stop_identity = "{0},{1},{2}={3}"
stop_ids = set()
counter = [0]
line_types = [0, 1, 2]
hash_file_name = "hash.txt"
hash_file_name_temp = "new_hash.txt"
logging.basicConfig(format='%(asctime)s %(message)s', filename=log_file_name, level=logging.INFO)

with open('config.json', 'r') as f:
    config = json.load(f)

headers = {'X-Api-Key': config['API_KEY'], 'X-User-Id': config['USER_ID']}

class DownloadJob(workerpool.Job):
    "Job for downloading a given URL."
    def __init__(self, line):
        self.line = line
    def run(self):
        read_line_stops(self.line)

def get_all_lines():
    logging.info("Started getting stops descriptions!")
    pool = workerpool.WorkerPool(multiprocessing.cpu_count() * 2)

    for line_type in line_types:
        resp = requests.get(linesBaseURL.format(line_type), headers=headers)
        d = resp.json()
        for line in d:
            job = DownloadJob(line)
            pool.put(job)
        print("Line type "+str(line_type) )
    pool.shutdown()
    pool.wait()
    logging.info("Finished getting stops descriptions.")


def read_line_stops(line):
    url =linesStopsURL.format(line["type"], line["id"])
    resp = requests.get(url, headers=headers)
    d = resp.json()
    if 'routes' not in d:
        print(d)
    else:
        routes = d['routes']
        for route in routes:
            stops = route['stops']
            direction = direction_template.format(stops[0]["name"], stops[len(stops) - 1]["name"])
            for stop in stops:
                stop_id = stop_identity.format(line["type"], line["name"], stop["code"], direction)
                stop_ids.add(stop_id)
                counter[0] += 1

def generate_stops_desc(stops):
    return ";".join(stops)

def stops_descs_have_changed(stops_desc):
    try:
        with open(desc_file_name, 'r') as f:
            old = f.readline()
            if old == "": # desc file was empty
                return True
            return old != stops_desc
    except FileNotFoundError:
        return True

def write_to_file(stops_desc):
    with open(desc_file_name, 'w') as f:
        f.write(stops_desc)
    logging.info("Wrote to file!")

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

def write_hash_to_file(hash_to_write):
    with open(hash_file_name_temp, "w") as f:
        f.write(hash_to_write)

def stops_descs_have_changed_hash():
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

def main():
    start = time.time()
    print("yay")
    get_all_lines()
    print("finished")
    stop_ids_l = list(stop_ids)
    stop_ids_l.sort()

    stops_desc = generate_stops_desc(stop_ids_l)
    hash_new = calculate_hash(stops_desc)
    write_hash_to_file(hash_new)
    if stops_descs_have_changed_hash():
        logging.info("Stops descriptions have changed!")
        write_to_file(stops_desc)
        upload_coordinates()
        push_notification("Descriptions have changed!")
    else:
        logging.info("No changes in descriptions.")
    logging.info("Finished gettings {0} descriptions in {1}s".format(len(stop_ids_l), time.time() - start))

if __name__ == '__main__':
    main()
