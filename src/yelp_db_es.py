import boto3
import requests
from yelpapi import YelpAPI
import time
import json
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Get dynamodb table
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('yelp-restaurants')
print(table.creation_date_time)

# Get data from Yelp
API_KEY = 'ATUWq79ivl-WmCgAxfetlPlVgtCi_0C4OMAyDjThCQBIhFBYvlwoEM5tyfr4WUSq8GNHzh8s8dTPX-g9-Zml1nNW4D4zW8mp2Xsuq9R5CEpWDf0UGp78ZvoZCjV_X3Yx'

# Defaults for our simple example.
DEFAULT_TERM = 'restaurant'
termList = ['Japanese', 'Chinese', 'French', 'Italian',
            'American', 'Korean', 'Indian', 'Spanish', 'Thai', 'Asian']
DEFAULT_LOCATION = 'new york'
SEARCH_LIMIT = 50

# API constants,
SEARCH_PATH = 'https://api.yelp.com/v3/businesses/search'

# Elastic Search Service
host = 'search-restaurants-hcpbhnqlbo4x36mcr4f7prxde4.us-east-1.es.amazonaws.com'
region = 'us-east-1'

service = 'es'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                   region, service, session_token=credentials.token)

es = Elasticsearch(
    hosts=[{'host': host, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

for term in termList:
    param = {
        'term': term,
        'limit': SEARCH_LIMIT,
        'location': DEFAULT_LOCATION
    }
    header = {'Authorization': 'bearer %s' % API_KEY}

    response = requests.get(url=SEARCH_PATH, params=param, headers=header)
    business_data = response.json()
    bulk_file = ''
    index = {}
    with table.batch_writer() as batch:
        for business in business_data['businesses']:
            print(business['id'])
            table.put_item(
                Item={
                    'id': business['id'],
                    'name': business['name'],
                    'rating': str(business['rating']),
                    'coordinates': {
                        'latitude': str(business['coordinates']['latitude']),
                        'longitude': str(business['coordinates']['longitude']),
                    },
                    'location': business['location'],
                    'cuisine': term,
                    'review_count': business['review_count'],
                    'insertedAtTimestamp': time.strftime("%d/%m/%Y-%H:%M:%S", time.localtime())
                })
            # ES
            payload = {
                "id": business['id'],
                "cuisine": term
            }
            bulk_file += '{ "index" : { "_index" : "restaurant", "_type" : "_doc", "_id" : "' + \
                str(business['id']) + '" } }\n'
            bulk_file += json.dumps(payload) + '\n'
    es.bulk(bulk_file)
