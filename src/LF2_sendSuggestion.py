import json
import boto3
import requests
from requests_aws4auth import AWS4Auth
from boto3.dynamodb.conditions import Key


def send_sns_msg(phone_number, message):
    client = boto3.client('sns')
    response = client.publish(
        PhoneNumber=phone_number,
        Message=message,
    )
    return response


def poll_sqs_msg(queue_url, max_msg):
    client = boto3.client('sqs')
    response = client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_msg
    )
    return response


def delete_sqs_msg(queue_url, handler):
    client = boto3.client('sqs')
    response = client.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=handler
    )
    return response


def get_restaurants_id(cuisine):
    region = 'us-east-1'  # For example, us-west-1
    service = 'es'
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                       region, service, session_token=credentials.token)

    host = 'search-restaurants-hcpbhnqlbo4x36mcr4f7prxde4.us-east-1.es.amazonaws.com'
    index = 'restaurant'
    url = 'https://' + host + '/' + index + '/_search'
    query = {
        "size": 3,
        "query": {
            "function_score": {
                "query": {
                    "bool": {
                        "must": [{"match": {"cuisine": cuisine}}]
                    },
                },
                "functions": [
                    {
                        "random_score": {}
                    }
                ]
            }
        }
    }

    # ES 6.x requires an explicit Content-Type header
    headers = {"Content-Type": "application/json"}

    # Make the signed HTTP request
    r = requests.get(url, auth=awsauth, headers=headers,
                     data=json.dumps(query))

    # Create the response and add some extra content to support CORS
    response = {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": '*'
        },
        "isBase64Encoded": False
    }
    es_response = json.loads(r.text)
    response['body'] = es_response
    rests_id = [h['_id'] for h in es_response['hits']['hits']]
    return rests_id


def get_restaurant_by(cuisine, id, dynamodb=None):
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('yelp-restaurants')
    response = table.query(
        KeyConditionExpression=Key('id').eq(id)
    )
    item = next(filter(lambda x: x['cuisine'] ==
                       cuisine, response['Items']), None)
    rest_name = item['name']
    street = item['location']['display_address']
    rest_address = ",".join(street)
    return [rest_name, rest_address]


def get_restaurants(cuisine):
    rests_id = get_restaurants_id(cuisine)
    rests = [get_restaurant_by(cuisine, id) for id in rests_id]
    return rests


region = 'us-east-1'  # For example, us-west-1
service = 'es'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                   region, service, session_token=credentials.token)

host = 'search-restaurants-hcpbhnqlbo4x36mcr4f7prxde4.us-east-1.es.amazonaws.com'
index = 'restaurant'
url = 'https://' + host + '/' + index + '/_search'


def lambda_handler(event, context):
    queue_url = 'https://sqs.us-east-1.amazonaws.com/854120724775/FoodSuggestionQ'
    sqs_response = poll_sqs_msg(queue_url, 5)
    if "Messages" not in sqs_response:
        return sqs_response
    msgs = sqs_response['Messages']

    accu_response = []
    for sqs_msg in msgs:
        msg = json.loads(sqs_msg['Body'])
        cuisine = msg['Cuisine']
        phone = "+1" + msg['Phone']
        people = msg['People']
        time = msg['Time']
        date = msg['Date']
        #location = msg['Location']

        restaurants = get_restaurants(cuisine)
        rest_addr = ""
        for i, restaurant in enumerate(restaurants):
            rest_addr += (str(i + 1) + ". " +
                          restaurant[0] + ", located at " + restaurant[1] + " ")

        sns_message = "Hello! Here are my {} restaurant sugestions for {} people, for {} at {}: {}".format(
            cuisine, people, date, time, rest_addr)

        accu_response.append(send_sns_msg(phone, sns_message))
        del_response = delete_sqs_msg(queue_url, sqs_msg['ReceiptHandle'])

    response = {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": '*'
        },
        "isBase64Encoded": False
    }
    response['body'] = accu_response
    return response
