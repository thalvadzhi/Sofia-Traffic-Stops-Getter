import json
import requests
import workerpool
import time
import logging
from git_client import *
from push_notification import *
import multiprocessing


linesBaseURL = "https://api.sofiatransport.com/v3/lines/{0}"
linesStopsURL = "https://api.sofiatransport.com/v3/lines/{0}/{1}"
desc_file_name = "descriptions.txt"
log_file_name = "desc_log.txt"
direction_template = "{0} - {1}"
stop_identity = "{0},{1},{2}={3}"
stop_ids = set()
counter = [0]
line_types = [0, 1, 2]

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
    pool = workerpool.WorkerPool(multiprocessing.cpu_count())
    for line_type in line_types:
        resp = requests.get(linesBaseURL.format(line_type), headers=headers)
        d = resp.json()
        for line in d:
            job = DownloadJob(line)
            pool.put(job)
    pool.shutdown()
    pool.wait()
    logging.info("Finished getting stops descriptions.")


def read_line_stops(line):
    url =linesStopsURL.format(line["type"], line["id"])
    resp = requests.get(url, headers=headers)
    d = resp.json()
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

def main():
    start = time.time()
    get_all_lines()
    stop_ids_l = list(stop_ids)
    stop_ids_l.sort()

    stops_desc = generate_stops_desc(stop_ids_l)
    if stops_descs_have_changed(stops_desc):
        logging.info("Stops descriptions have changed!")
        write_to_file(stops_desc)
        add_file('descriptions_getter/' + desc_file_name)
        commit("Descriptions update")
        push()
        push_notification("Descriptions have changed!")
    else:
        logging.info("No changes in descriptions.")
    logging.info("Finished gettings {0} descriptions in {1}s".format(len(stop_ids_l), time.time() - start))

main()
