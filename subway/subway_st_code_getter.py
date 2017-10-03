import requests
import codecs
from bs4 import BeautifulSoup
import json

METRO_URL = "https://schedules.sofiatraffic.bg/metro/1#direction/{0}"
METRO_DIRECTIONS = [2666]

all_stops_codes = set()


for direction in METRO_DIRECTIONS:
    print("Direction " + str(direction))
    resp = requests.get(METRO_URL.format(direction))

    d = resp.text
    soup = BeautifulSoup(d, "html.parser")
    # div = soup.find("div", {"class": "schedule_direction_sign_wrapper"})

    uls = soup.findAll("ul", {"class": "schedule_direction_signs"})
    for ul in uls:
        lis = ul.findAll("li")

        for li in lis:
            stop_code = li.find("a", {"class": "stop_link"})
            stop_code = str(stop_code.string).encode("iso-8859-1").decode("utf8")
            stop_name = li.find("a", {"class": "stop_change"})
            stop_name = str(stop_name.string).encode("iso-8859-1").decode("utf8")
            all_stops_codes.add((stop_code, stop_name))

def convert_to_full_name(stop_name):
    if stop_name == "метростанция централна гара":
        return "централна жп гара"
    elif stop_name == "метростанция сердика":
        return "сердика 1"
    elif stop_name == "метростанция к.величков":
        return "константин величков"
    elif stop_name == "метростанция су св. климент охридски":
        return "софийски университет св. климент охридски"
    elif stop_name == "метростанция ст.васил левски":
        return "стадион васил левски"
    elif stop_name =="метростанция младост-3":
        return "младост 3"
    elif stop_name == "метрост. цариградско шосе":
        return "интер експо център - цариградско шосе"
    elif stop_name == "метрост. акад. ал. теодоров-балан":
        return "акад. ал. теодоров-балан"
    else:
        return stop_name
coords = open("metro_stations_coords.json", "r")
d = json.loads(coords.read())

coords_and_codes = []
print(len(all_stops_codes))
all_stops_codes = list(all_stops_codes)
for stop_code in all_stops_codes:
    hasFound = False
    for st in d:
        name = st["name"].lower()
        name_from_st_codes = stop_code[1].lower()
        name_from_st_codes = convert_to_full_name(name_from_st_codes)
        if name in name_from_st_codes:
            hasFound = True
            coordinates = [st["lat"], st["lon"]]
            c_n_c = {'line': st["line"], "stopName": st["name"], "coordinates": coordinates}
            c_n_c["stopCode"] = stop_code[0]
            coords_and_codes.append(c_n_c)
    if not hasFound:
        print(stop_code)

f = open("subway_coords.json", "w", encoding="utf8")

coords_and_codes.sort(key=lambda k: k["stopName"])
print(len(coords_and_codes))
print(len(d))
to_write = json.dumps(coords_and_codes,  ensure_ascii=False)
f.write(to_write)
f.close()
