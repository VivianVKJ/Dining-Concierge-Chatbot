import math
import dateutil.parser
import datetime
import time
import os
import logging
import boto3
import json

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


""" --- Helpers to build responses which match the structure of the necessary dialog actions --- """


def get_slots(intent_request):
    return intent_request['currentIntent']['slots']


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }


""" --- Helper Functions --- """


def parse_int(n):
    try:
        return int(n)
    except ValueError:
        return float('nan')


def build_validation_result(is_valid, violated_slot, message_content):
    if message_content is None:
        return {
            "isValid": is_valid,
            "violatedSlot": violated_slot,
        }

    return {
        'isValid': is_valid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


def isvalid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False


def validate_food_suggestions(city, cuisine, people, date, time, phone):

    if city is not None:
        if city not in ["New York"]:
            return build_validation_result(False,
                                           'Location',
                                           'We do not support {} currently, would you like to see suggestions for New York? '.format(city))

    cuisine_types = ['Italian', 'French', 'American', 'Chinese',
                     'Korean', 'Indian', 'Spanish', 'Thai', 'Japanese', 'Asian']
    if cuisine is not None and cuisine.title() not in cuisine_types:
        return build_validation_result(False,
                                       'Cuisine',
                                       'We do not have {}, would you like a different cuisine?  '
                                       'Our most popular cuisine is American'.format(cuisine))

    if people is not None and int(people) > 20:
        return build_validation_result(False,
                                       'People',
                                       'Most restaurant could not accomodate {} people, could you have a party less than 20 people?  '.format(people))
    if date is not None:
        if not isvalid_date(date):
            return build_validation_result(False, 'Date', 'I did not understand that, what date would you like to go to restaurant?')
        elif datetime.datetime.strptime(date, '%Y-%m-%d').date() <= datetime.date.today():
            return build_validation_result(False, 'Date', 'You can go to restaurant from tomorrow onwards.  What day would you like to go?')

    if time is not None:
        if len(time) != 5:
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'Time', None)

        hour, minute = time.split(':')
        hour = parse_int(hour)
        minute = parse_int(minute)
        if math.isnan(hour) or math.isnan(minute):
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'Time', None)

        if hour < 10 or hour > 22:
            # Outside of business hours
            return build_validation_result(False, 'Time', 'Our business hours are from ten a m. to five p m. Can you specify a time during this range?')

    if phone is not None and len(phone) > 11:
        return build_validation_result(False,
                                       'Phone',
                                       'Phone number invalid. Please only type you phone number.')

    return build_validation_result(True, None, None)


""" --- Functions that control the bot's behavior --- """


def food_suggestion(intent_request):
    """
    Performs dialog management and fulfillment for food suggestion.
    Beyond fulfillment, the implementation of this intent demonstrates the use of the elicitSlot dialog action
    in slot validation and re-prompting.
    """
    city = get_slots(intent_request)["Location"]
    cuisine = get_slots(intent_request)["Cuisine"]
    people = get_slots(intent_request)["People"]
    date = get_slots(intent_request)["Date"]
    time = get_slots(intent_request)["Time"]
    phone = get_slots(intent_request)["Phone"]

    source = intent_request['invocationSource']

    if source == 'DialogCodeHook':
        # Perform basic validation on the supplied input slots.
        # Use the elicitSlot dialog action to re-prompt for the first violation detected.
        slots = get_slots(intent_request)

        validation_result = validate_food_suggestions(
            city, cuisine, people, date, time, phone)
        if not validation_result['isValid']:
            slots[validation_result['violatedSlot']] = None
            return elicit_slot(intent_request['sessionAttributes'],
                               intent_request['currentIntent']['name'],
                               slots,
                               validation_result['violatedSlot'],
                               validation_result['message'])

        output_session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {
        }

        return delegate(output_session_attributes, get_slots(intent_request))
    return close(intent_request['sessionAttributes'],
                 'Fulfilled',
                 {'contentType': 'PlainText',
                     'content': 'You’re all set. Expect my suggestions shortly! Have a good day.'})


""" --- Intents --- """


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug('dispatch userId={}, intentName={}'.format(
        intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    if intent_name == 'FoodSuggestion':
        return food_suggestion(intent_request)
    raise Exception('Intent with name ' + intent_name + ' not supported')


""" --- Main handler --- """


def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))

    return dispatch(event)
