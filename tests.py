import pytest
from app import AveragingInterval, app, count_poor_pm25_intervals, create_url, filter_active_stations, get_stat_number_of_stations
from datetime import timedelta


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_index(client):
    response = client.get("/")
    assert response.status_code


def test_create_url():
    '''
    The result URL ignores None param values
    '''
    actual = create_url("http://base.url", **{"param1": 1, "param2": 2, "param3": None})
    expected = "http://base.url?param1=1&param2=2"
    assert expected == actual


def test_create_url_value_with_spaces():
    '''
    Handle white spaces in values nicely
    '''
    actual = create_url(
        "http://base.url", **{"param1": 1, "param2": 2, "param3": "string with spaces"}
    )
    expected = "http://base.url?param1=1&param2=2&param3=string+with+spaces"
    assert expected == actual

def test_filter_active_stations():
    # partial response for locations
    example_stations_list = [
        {
            "location": "Alpha",
            "firstUpdated": "2017-09-13T21:00:00.000Z",
            "lastUpdated": "2020-09-22T18:00:00.000Z",
        },
        {
            "location": "Beta",
            "firstUpdated": "2017-09-13T21:00:00.000Z",
            "lastUpdated": "2017-09-22T18:00:00.000Z",
        },
        {
            "location": "Gamma",
            "firstUpdated": "2017-09-14T00:00:00.000Z",
            "lastUpdated": "2020-09-22T18:00:00.000Z",
        }
    ]
    oldness_threshold = timedelta(days=365)
    active_stations = filter_active_stations(example_stations_list, oldness_threshold)
    filter_active_stations([], 'test')
    assert [s["location"] for s in active_stations] == ["Alpha", "Gamma"]

def test_get_stat_number_of_stations_one_or_less():
    assert get_stat_number_of_stations(0) == "There is <b>0</b> government air quality monitoring station in this area"
    assert get_stat_number_of_stations(1) == "There is <b>1</b> government air quality monitoring station in this area"

def test_get_stat_number_of_stations_more_than_one():
    assert get_stat_number_of_stations(2) == "There are <b>2</b> government air quality monitoring stations in this area"

def test_count_poor_pm25_intervals():
    averages = [
        {'average': 1},
        {'average': 5},
        {'average': 15},
        {'average': 20},
        {'average': 30},
        {'average': 100},
    ]
    assert count_poor_pm25_intervals(averages, AveragingInterval.day) == 2
    assert count_poor_pm25_intervals(averages, AveragingInterval.month) == 2
    assert count_poor_pm25_intervals(averages, AveragingInterval.year) == 4
    assert count_poor_pm25_intervals([], AveragingInterval.day) == 0
