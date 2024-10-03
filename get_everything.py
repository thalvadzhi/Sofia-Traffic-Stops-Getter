from stops_getter.stops_getter_newer_api import run_stop_getter
from polyline_getter.polyline_getter_new import run_polyline_getter
from descriptions_getter.directions_getter_new import run_directions_getter

def main():
    print("Running stop getter")
    run_stop_getter(should_upload=True)
    print("Running polyline getter")
    run_polyline_getter(should_upload=True)
    print("Running directions getter")
    run_directions_getter(should_upload=True)

main()
