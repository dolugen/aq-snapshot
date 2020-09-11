import os
from flask import Flask
from flask import render_template
from flask import request
import requests

app = Flask(__name__)

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


def get_averages(temporal='day', spatial='location', location=None, city=None, country=None):
    '''makes an API call to OpenAQ averages endpoint, and returns the results'''
    params = {
        'temporal': temporal,
        'spatial': spatial,
        'country': country,
        'city': city,
        'location': location,
        'order_by': 'date',
        'sort': 'asc'
    }
    params = '&'.join([f'{k}={v}' for (k, v) in params.items() if v is not None])
    print(params)

    resp = requests.get(f'{AVERAGES_URL}?{params}')
    averages = resp.json()["results"]
    return averages

def get_locations(country=None, city=None):
    '''
    makes an API call to OpenAQ locations endpoint
    and returns the results
    '''
    params = {
        'country': country,
        'city': city
    }
    params = '&'.join([f'{k}={v}' for (k, v) in params.items() if v is not None])
    url = f'{LOCATIONS_URL}?{params}&has_geo=true&limit=10000'
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
    
    date_from = request.args.get('dateFrom')
    date_to = request.args.get('dateTo')

    # TODO: use date range here
    averages = get_averages(
        temporal=averaging_time, 
        spatial=place_type, 
        **{place_type: place_id or place_name})
    print(averages)

    if place_type == "country":
        locations = get_locations(country=place_id)
    # TODO: city name not unique?
    elif place_type == "city":
        locations = get_locations(city=place_name)
    print(f'Got {len(locations)} locations')

    # TODO: other parameters will be available too
    # TODO: suffix place name with context (e.g. city_name, country_name)
    chart_title = f'{averaging_time.capitalize()}ly average PM2.5 for {place_name}'

    return render_template('report.html',
                            averages=averages,
                            locations=locations,
                            chart_title=chart_title,
                            place_name=place_name,
                            averaging_time=averaging_time,
                            pollutants=pollutants,
                            date_from=date_from,
                            date_to=date_to,
                            mapbox_access_token=MAPBOX_ACCESS_TOKEN)

@app.route('/resources')
def resources():
    return render_template('resources.html')
