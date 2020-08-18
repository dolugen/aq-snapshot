from flask import Flask
from flask import render_template
from flask import request
app = Flask(__name__)

POLLUTANTS = [
    ('pm25', 'Particulate matter less than 2.5 micrometers in diameter'),
    ('pm10', 'Particulate matter less than 10 micrometers in diameter'),
    ('co', 'Carbon Monoxide'),
    ('o3', 'Ozone'),
    ('no2', 'Nitrogen Dioxide'),
    ('so2', 'Sulfur Dioxide'),
    ('bc', 'Black Carbon')
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/report')
def report():
    place_name = request.args.get('placeName')
    averaging_time = request.args.get('time')
    pollutants = {}
    for pollutant, _ in POLLUTANTS: 
        pollutants[pollutant] = bool(request.args.get(pollutant))
    date_from = request.args.get('dateFrom')
    date_to = request.args.get('dateTo')
    
    return render_template('report.html',
                            place_name=place_name,
                            averaging_time=averaging_time,
                            pollutants=pollutants,
                            date_from=date_from,
                            date_to=date_to)

@app.route('/resources')
def resources():
    return render_template('resources.html')
