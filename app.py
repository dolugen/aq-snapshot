import enum
import os
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List, Sequence

import markdown
import requests
from flask import Flask, render_template, request

app = Flask(__name__)

class AveragingInterval(enum.Enum):
    day = "day"
    month = "month"
    year = "year"

WHO_GUIDELINES_URL = "https://www.who.int/en/news-room/fact-sheets/detail/ambient-(outdoor)-air-quality-and-health"
# see above URL for thresholds
PM25_OK_THRESHOLDS = {
    AveragingInterval.day: 25, # μg/m3
    AveragingInterval.month: 25, # μg/m3
    AveragingInterval.year: 10, # μg/m3
}

# used to filter out inactive stations
STATION_INACTIVITY_THRESHOLD_IN_DAYS = 365

MAPBOX_ACCESS_TOKEN = os.environ.get('MAPBOX_ACCESS_TOKEN')
if not MAPBOX_ACCESS_TOKEN:
    print('Mapbox access token is missing.')

POLLUTANTS = [
    ('pm25', 'Particulate matter less than 2.5 micrometers in diameter'),
    ('pm10', 'Particulate matter less than 10 micrometers in diameter'),
    ('co', 'Carbon Monoxide'),
    ('o3', 'Ozone'),
    ('no2', 'Nitrogen Dioxide'),
    ('so2', 'Sulfur Dioxide'),
    ('bc', 'Black Carbon')
]

AVERAGES_URL = "https://api.openaq.org/beta/averages"
LOCATIONS_URL = "https://api.openaq.org/v1/locations"

possessive_lookup = {
    AveragingInterval.day: "daily",
    AveragingInterval.month: "monthly",
    AveragingInterval.year: "annual"
}

def create_url(base_url: str, params: dict) -> str:
    # skip None values
    params = dict([(k, v) for (k, v) in params.items() if v is not None])
    url_params = urllib.parse.urlencode(params)
    return f'{base_url}?{url_params}'

def filter_active_stations(stations_list: List[Dict], oldness_threshold: timedelta) -> List[Dict]:
    def is_recent(station: Dict) -> bool:
        last_updated = datetime.strptime(station["lastUpdated"], "%Y-%m-%dT%H:%M:%S.%fZ")
        return datetime.now() - last_updated < oldness_threshold
    return filter(is_recent, stations_list)


def get_averages(
    temporal=AveragingInterval.day,
    spatial='location',
    location=None,
    city=None,
    country=None,
    date_from=None,
    date_to=None):
    '''makes an API call to OpenAQ averages endpoint, and returns the results'''
    params = {
        'temporal': temporal.value,
        'spatial': spatial,
        'country': country,
        'city': city,
        'location': location,
        'date_from': date_from,
        'date_to': date_to,
        'order_by': 'date',
        'sort': 'asc',
        'limit': 10000,
    }
    url = create_url(AVERAGES_URL, params)
    print(url)
    resp = requests.get(url)
    averages = resp.json()["results"]
    return averages

def get_locations(country: str=None, city: str=None, location: str=None) -> List[dict]:
    '''
    makes an API call to OpenAQ locations endpoint
    and returns the results
    '''
    params = {
        'country': country,
        'city': city,
        'location': location,
        'has_geo': 'true',
        'limit': 10000,
    }
    url = create_url(LOCATIONS_URL, params)
    print(url)
    resp = requests.get(url)

    locations = resp.json()["results"]
    return locations


def find_place_coordinates(name, place_type):
    '''
    Ask Mapbox for the center coordinates for a city or a country.
    Used to center the map on the report page.
    '''
    pass

def count_poor_pm25_intervals(averages: Sequence[dict], interval: AveragingInterval, thresholds=PM25_OK_THRESHOLDS) -> int:
    threshold = thresholds[interval]
    above_threshold_averages = filter(lambda average: average['average'] > threshold, averages)
    return len(list(above_threshold_averages))

def get_stat_number_of_stations(stations_count: int) -> str:
    return (
        f'There {"is" if stations_count <=1 else "are"} '
        f'<b>{stations_count}</b> '
        'government air quality monitoring '
        f'{"station" if stations_count <= 1 else "stations"} '
        'in this area'
    )

def prepare_stats(averages: Sequence[dict], averaging_interval: AveragingInterval, locations):
    # some places might not have averages ready
    if not averages:
        return []

    # number of intervals above threshold
    poor_aq_intervals = count_poor_pm25_intervals(averages, averaging_interval)
    
    ceiling = max(averages, key=lambda a: a['average'])

    total_data_points = sum([a['measurement_count'] for a in averages])

    stats_lines = [
        f"<span class='w3-large'><b>{poor_aq_intervals}</b></span> "
        f"{averaging_interval.value}{'s' if poor_aq_intervals != 1 else ''} had poor air quality "
        f"(according to <a target='_blank' href='{WHO_GUIDELINES_URL}'>WHO guidelines</a>)",
        f"The {averaging_interval.value} of <b>{ceiling['date']}</b> "
        f"had the worst air with average PM 2.5 concentrations "
        f"at <b>{ceiling['average']:.2f} µg/m³</b>",
        get_stat_number_of_stations(len(locations)),
        f"<b>{total_data_points}</b> measurements were collected during this time"
    ]
    return stats_lines

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/report')
def report():
    place_name = request.args.get('placeName')
    place_type = request.args.get('placeType')
    place_id = request.args.get('placeID')
    assert place_type in ["country", "city", "location"]
    averaging_interval = AveragingInterval(request.args.get('temporal'))

    pollutants = {}
    for pollutant, _ in POLLUTANTS: 
        pollutants[pollutant] = bool(request.args.get(pollutant))
    
    zoom_level = 9
    if place_type == "country":
        zoom_level = 4
    
    date_from = request.args.get('dateFrom') or None
    date_to = request.args.get('dateTo') or None

    # location and city uses names, country uses ISO code
    place_filter = {place_type: place_name}
    if place_type == "country":
        place_filter[place_type] = place_id

    averages = get_averages(
        temporal=averaging_interval, 
        spatial=place_type, 
        date_from=date_from,
        date_to=date_to,
        **place_filter)
    
    # set actual date range based on found results
    # the results are sorted by date in ascending order already
    if len(averages) > 1:
        date_from, date_to = averages[0]['date'], averages[-1]['date']
    
    # TODO: if there are no averages found, show a message on the result page?

    if place_type == "country":
        locations = get_locations(country=place_id)
    # TODO: city name not unique?
    elif place_type == "city":
        locations = get_locations(city=place_name)
    elif place_type == "location":
        locations = get_locations(location=place_name)
    
    locations = list(filter_active_stations(locations, timedelta(days=STATION_INACTIVITY_THRESHOLD_IN_DAYS)))

    # TODO: other parameters will be available too
    # TODO: suffix place name with context (e.g. city_name, country_name)
    chart_title = f'{possessive_lookup[averaging_interval].capitalize()} average PM2.5 for {place_name}'

    stats_lines = prepare_stats(averages, averaging_interval, locations)

    return render_template('report.html',
                            averages=averages,
                            locations=locations,
                            stats_lines=stats_lines,
                            chart_title=chart_title,
                            place_name=place_name,
                            averaging_time=averaging_interval.value,
                            pollutants=pollutants,
                            date_from=date_from,
                            date_to=date_to,
                            map_zoom_level=zoom_level,
                            mapbox_access_token=MAPBOX_ACCESS_TOKEN)

@app.route('/resources')
def resources():
    with open('content/resources.md') as md:
        html = markdown.markdown(md.read(), extensions=['md_in_html'])
        return render_template('resources.html', safe_content=html)
