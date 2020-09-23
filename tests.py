import pytest
from app import app, create_url


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
    actual = create_url("http://base.url", {"param1": 1, "param2": 2, "param3": None})
    expected = "http://base.url?param1=1&param2=2"
    assert expected == actual


def test_create_url_value_with_spaces():
    '''
    Handle white spaces in values nicely
    '''
    actual = create_url(
        "http://base.url", {"param1": 1, "param2": 2, "param3": "string with spaces"}
    )
    expected = "http://base.url?param1=1&param2=2&param3=string+with+spaces"
    assert expected == actual
