import io
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from urllib.parse import unquote
import requests
import multiprocessing
from stops_getter.stops_getter_newer_api import run_stop_getter
from polyline_getter.polyline_getter_new import run_polyline_getter
from descriptions_getter.directions_getter_new import run_directions_getter


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
    payload = {"ext_id": line_id}
    try:
        routes = session.post(url_routes, headers=headers, json=payload).json()
        time.sleep(0.5)
    except Exception:
        logging.exception("Couldn't get routes from url '{0}', payload: {1}".format(url_routes, payload))
        sys.exit(0)
    return routes

def get_all_routes():
    xsrf_token, session = get_xsrf_token_and_session()
    lines = get_lines(xsrf_token, session)
    line_ids = list(map(lambda line: line["ext_id"], lines))
    get_route_partial = partial(get_route, xsrf_token=xsrf_token, session_token=session)
    with ThreadPoolExecutor(2) as pool:
        routes = pool.map(get_route_partial, line_ids)
    return routes



def main():
    print("inside process")
    sys.stdout.flush()
    all_routes = list(get_all_routes())
    sys.stdout.flush()

    logging.info("Running stop getter")
    sys.stdout.flush()
    run_stop_getter(all_routes=all_routes, should_upload=True)
    sys.stdout.flush()

    print("Running polyline getter")
    sys.stdout.flush()

    run_polyline_getter(all_routes=all_routes, should_upload=True)
    sys.stdout.flush()

    print("Running directions getter")
    sys.stdout.flush()

    run_directions_getter(all_routes=all_routes, should_upload=True)
    sys.stdout.flush()


if __name__ == "__main__":
    p = multiprocessing.Process(target=main)
    p.start()
    p.join(timeout=10 * 60)  # wait up to 10 minutes

    if p.is_alive():
        p.terminate()  # forcibly stop the whole process and its threads
        print("Function timed out and was terminated")
