from stops_getter.stops_getter import run_stop_getter
from polyline_getter.polyline_getter import run_polyline_getter
from descriptions_getter.directions_getter import run_directions_getter

if __name__ == "__main__":
    run_stop_getter(should_upload=False)
    run_polyline_getter(should_upload=False)
    run_directions_getter(should_upload=False)