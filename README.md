# Dining Concierge Chatbot
A serverless, microservice-driven Dining Concierge Chatbot that sends you restaurant suggestions given a set of preferences that you provide the chatbot through conversation.

**Cloud Computing Fall20 Assignment 1**

Ziwei Wang(zw2337), Haodong Huang(hh2322)


### Front End

Build and deploy the frontend application in AWS S3 bucket

![image-20201013114044499](/Users/vivian/Library/Application Support/typora-user-images/image-20201013114044499.png)

### API Gateway

Use `aics-swagger.yaml` to set up API

Enable CORS on API methods

- OPTIONS: Return default response.
- POST: Frontend makes API calls `/chatbot - POST` to API Gateway

![image-20201013114404664](/Users/vivian/Library/Application Support/typora-user-images/image-20201013114404664.png)

### Lambda (LF0)

From the request/reponse model,  user input `text` is returned in this `json` format:

```json
{
  "messages": [{
      "type": "string",
      "unstructured": {
        "id": "string",
        "text": "hello",
        "timestamp": "string"
      }
    }]
}
```

LF0 parses the message and call Lex using `boto3.client.post_text()`

```python
msg = event['messages'][0]['unstructured']['text']
client = boto3.client('lex-runtime')
response = client.post_text(
    botName='OrderFlowers',
	... ...
    inputText = msg)
```

### LEX

Set up Lex with three intents:

* Food Suggestion: 

  Collects `Location`, `Cuisine`, `Dining Time`, `Number of people` and `Phone number` from user through conversation. We enable Lambda initialization & validation on every slot and trigger another lambda to call SQS service once the user intents are fulfilled.

  * **Lambda initialization and validation**: Lambda Function  `ValidateInput`
  * **Fulfillment**: Lambda Function `foodSuggestion`

  ![image-20201013122842358](/Users/vivian/Library/Application Support/typora-user-images/image-20201013122842358.png)

* Greeting 

* Thank you

### Lambda (LF1)

##### 1) ValidateInput

Lambda function `ValidateInput` is used for  in slot validation and re-prompting. The `dispatch` function inside is called when the user specifies an intent for this bot and raise exception if the intent is not supported. 

It also return proper suggestions when user's request is beyond our suggestion system. For example: 

```  python
if cuisine is not None and cuisine.title() not in cuisine_types:
    return build_validation_result(False,
                                   'Cuisine',
                                   'We do not have {}, would you like a different cuisine?  '
                                   'Our most popular cuisine is American'.format(cuisine))       
```

##### 2) foodSuggestion

Based on the parameters collected from the user, **push** the information collected from the user (location, cuisine, etc.) to an SQS queue using `boto3.client.send_message()`

```python
def send_sqs_message(QueueName, msg_body):
    """
    :param sqs_queue_url: String URL of existing SQS queue
    :param msg_body: String message body
    """
    # Send the SQS message
    sqs_client = boto3.client('sqs')
    sqs_queue_url = sqs_client.get_queue_url(QueueName=QueueName)['QueueUrl']

    msg = sqs_client.send_message(QueueUrl=sqs_queue_url, MessageBody=json.dumps(msg_body)) 
    return msg
```

### SQS

We create a standard queue `FoodSuggestionQ` and add add permission to lambda function `foodSuggestion` to manage messages in this SQS queue.

### Dynamo DB & Elastic Search

Collect hundreds of restaurants in NYC using Yelp API. At the same time we store every restaurant info into Dynamo DB and ES service.

##### - Yelp

```python
SEARCH_PATH = 'https://api.yelp.com/v3/businesses/search'
term_list = ['Japanese', 'Chinese', ...']
param = {
    'term': term, #term in term_list
    'location': DEFAULT_LOCATION
}
```

##### - Dynamo DB

Parse the response boby from YelpAPI and store `id`,  `rating`, `location`, etc. Attach `insertedAtTimestamp` to each item. Items are intersted into Dynamo DB table using `table.batch_writer()` and `table.put_item`

The format of items in the table is:

```json
{
  "id": "2UxAkvKkkWNwqZi9H0OzWw",
  "coordinates": {...},
  "cuisine": "Asian",
  "insertedAtTimestamp": "10/10/2020-20:23:33",
  "location": {
	...,
    "state": "NY",
    "zip_code": "10009"
  },
  "name": "Dian Kitchen",
  "rating": "5.0",
  "review_count": 225
}
```

##### - Elastic Sercah

Create an ElasticSearch index called “restaurants” and store `id` and `cuisine` for each restaurant.

After connecting to es in the program, use `es.bulk(bulk_file)` to store multiple result at the same time.

### Suggestion Module

##### - CloudWatch

Poll from SQS every 1 min using CloudWatch by creating a new rule to set up a event trigger in CloudWatch that runs **every minute** and invokes lambda funtion `sendSuggestion` (**LF2**)

![image-20201013160059950](/Users/vivian/Library/Application Support/typora-user-images/image-20201013160059950.png)

##### - Lambda (LF2)

Lambda function `sendSuggestion` is triggered by the CloudWatch Event above. 

* Poll message:

  Poll at most 5 messges from SQS `FoodSuggestionQ`

  ```python
  queue_url = 'https://sqs.us-east-1.amazonaws.com/854120724775/FoodSuggestionQ'
  sqs_response = poll_sqs_msg(queue_url, 5)
  ```

* Get restaurant id from ES:

  Parse the information in each message and search ES with `cuisine`.  Use **DSL** query with `function_score` to get three random resturant ids with certain cuisine type.

  ```python
  query = {
      "size": 3,
      "query": {
          "function_score": {
              "query": { "bool": { "must": [{"match": {"cuisine": cuisine}}] }},
              "functions": [ {"random_score": {} }]
          }
      }
  }
  ```

* Fetch restaurant details from Dynamo DB:

  ```python
  table = dynamodb.Table('yelp-restaurants')
  response = table.query( KeyConditionExpression=Key('id').eq(id) )
  item = next(filter(lambda x: x['cuisine'] == cuisine, response['Items']), None)
  rest_name = item['name']
  street = item['location']['display_address']
  rest_address = ",".join(street)
  ```

* SNS

  Send suggestion results bt text message to the phone number included in the SQS message, using SNS

  ```python
  def send_sns_msg(phone_number, message):
      client = boto3.client('sns')
      response = client.publish(
          PhoneNumber=phone_number,
          Message=message,
      )
      return response
  ```

### Demo [[Video](https://youtu.be/2g2yUCrzQ2g)]

* Dining Suggestion:

![image-20201013173512358](/Users/vivian/Library/Application Support/typora-user-images/image-20201013173512358.png)

* Greeting, Thank you, and SNS

