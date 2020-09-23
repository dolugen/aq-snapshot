import os
import urllib.parse
from flask import Flask
from flask import render_template
from flask import request
import requests
import markdown
import aqi


app = Flask(__name__)

# https://cfpub.epa.gov/airnow/index.cfm?action=aqibasics.aqi
# Use moderate as threshold for OK AQI levels
AQI_OK_THRESHOLD = 100

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
    "day": "daily",
    "month": "monthly",
    "year": "annual"
}

def create_url(base_url: str, params: dict) -> str:
    # skip None values
    params = dict([(k, v) for (k, v) in params.items() if v is not None])
    url_params = urllib.parse.urlencode(params)
    return f'{base_url}?{url_params}'


def get_averages(
    temporal='day',
    spatial='location',
    location=None,
    city=None,
    country=None,
    date_from=None,
    date_to=None):
    '''makes an API call to OpenAQ averages endpoint, and returns the results'''
    params = {
        'temporal': temporal,
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

def get_locations(country=None, city=None, location=None):
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

def count_poor_aqi_intervals(averages):
    poor_aqi_intervals = 0
    for avg in averages:
        try:
            local_aqi = aqi.to_iaqi(aqi.POLLUTANT_PM25, avg['average'], algo=aqi.ALGO_EPA)
        except IndexError:
            # happens when the value is too high
            # can count towards poor AQ
            pass
        if local_aqi > AQI_OK_THRESHOLD:
            poor_aqi_intervals += 1
    return poor_aqi_intervals

def prepare_stats(averages, averaging_interval, locations):
    # some places might not have averages ready
    if not averages:
        return []

    # number of intervals below threshold
    poor_aqi_intervals = count_poor_aqi_intervals(averages)
    
    percentage_of_poor_aqi_intervals = poor_aqi_intervals / len(averages) * 100

    ceiling = max(averages, key=lambda a: a['average'])

    total_data_points = sum([a['measurement_count'] for a in averages])

    stats_lines = [
        f"<span class='w3-large'>"
        f"<b>{percentage_of_poor_aqi_intervals:.1f}%</b>"
        f"</span> of {averaging_interval}s had poor air quality "
        f"(according to EPA standards)",
        f"The {averaging_interval} of <b>{ceiling['date']}</b> "
        f"had the worst air with average PM 2.5 concentrations "
        f"at <b>{ceiling['average']:.2f} µg/m³</b>",
        f"There are <b>{len(locations)}</b> air quality sensor stations in this area",
        f"Total of <b>{total_data_points}</b> measurements were collected during this time"
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
    averaging_time = request.args.get('temporal')
    assert averaging_time in ["year", "month", "day"]

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
        temporal=averaging_time, 
        spatial=place_type, 
        date_from=date_from,
        date_to=date_to,
        **place_filter)

    if place_type == "country":
        locations = get_locations(country=place_id)
    # TODO: city name not unique?
    elif place_type == "city":
        locations = get_locations(city=place_name)
    elif place_type == "location":
        locations = get_locations(location=place_name)

    # TODO: other parameters will be available too
    # TODO: suffix place name with context (e.g. city_name, country_name)
    chart_title = f'{possessive_lookup.get(averaging_time).capitalize()} average PM2.5 for {place_name}'

    stats_lines = prepare_stats(averages, averaging_time, locations)

    return render_template('report.html',
                            averages=averages,
                            locations=locations,
                            stats_lines=stats_lines,
                            chart_title=chart_title,
                            place_name=place_name,
                            averaging_time=averaging_time,
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
