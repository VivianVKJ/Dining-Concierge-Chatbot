import json
import boto3

def lambda_handler(event, context):
    # TODO implement
    msg = event['messages'][0]['unstructured']['text']
    client = boto3.client('lex-runtime')
    response = client.post_text(
        botName='OrderFlowers',
        botAlias='VivianWang',
        userId='casper_botv2',
        inputText = msg)
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*'
        },
        'messages': [
                {
                  "type":"unstructured",
                  "unstructured":{
                       "text": response['message'],
                    }
                 }
            ]
            
    }