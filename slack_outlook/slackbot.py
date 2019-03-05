import multiprocessing
import time
from datetime import datetime, timedelta
from multiprocessing import Process
from pytz import timezone
import requests
import dateutil.parser
import traceback
import logging
logger = logging.getLogger('chatbot')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('/usr/src/app/ancile/slackbot/migrations/out.log')
fh.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)

from websocket import WebSocketConnectionClosedException

eastern = timezone('US/Eastern')
utc = timezone('UTC')
# from flask import request
# import flask
from data.rooms import *
from data.templates import *
from oauth_app import *
from slackclient import SlackClient
from slackclient.server import SlackConnectionError
from config import *

import json

multiprocessing.Process()


def check_token(member):

    data = {'grant_type': 'refresh_token', 'refresh_token': member.refresh_token, 'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET}

    logger.info(data)
    response = requests.post(AUTHORITY_URL+TOKEN_ENDPOINT, data)
    logger.info(response)
    if response.status_code==200:
        js_data = json.loads(response.text)
        member.token = js_data['access_token']
        member.refresh_token = js_data['refresh_token']
        member.expires = datetime.now(eastern) + timedelta(seconds=js_data['expires_in'])
        member.update()
        return True
    else:
        member.token=None
        member.refresh_token = None
        member.expires = None
        member.update()
        return False

def is_available_now(room_full, time_start, time_end):

    find_json = find_room_json(room=room_full,
                               time_start=time_start.isoformat(),
                               time_end=time_end.isoformat())
    logger.info(find_json)
    msft_resp = MSGRAPH.post("me/findMeetingTimes", data=find_json, format='json',
                             headers=request_headers()).data
    if msft_resp.get('error', None):
        logger.info(msft_resp)
        return {'result': 'error', 'data': msft_resp}
    if len(msft_resp.get('meetingTimeSuggestions', list())) == 0:
        return {'result': 'success', 'data': False}
    else:
        return {'result': 'success', 'data': True}

def get_available_by_floor(floor, msg_graph, time_start, time_end):
    rooms = get_rooms_by_floor(floor)
    available_rooms = list()
    rooms_json = check_floor_json(rooms, time_start.isoformat(), time_end.isoformat())
    logger.info('requested rooms: ' + str(rooms_json))
    msft_resp = MSGRAPH.post("me/findMeetingTimes", data=rooms_json, format='json',
                             headers=request_headers()).data

    if msft_resp.get('error', None):
        logger.info(msft_resp)
        return {'result': 'error', 'data': msft_resp}
    elif len(msft_resp['meetingTimeSuggestions']) > 0:
        for x in msft_resp['meetingTimeSuggestions'][0]["attendeeAvailability"]:
            if x["availability"] == "free":
                available_rooms.append(room_by_email(x["attendee"]['emailAddress']['address']))

    return {'result': 'success', 'data': available_rooms}




def rtm(token, queue, workspace, workspace_token):
    db.create_all()
    sc = SlackClient(workspace_token)
    logger.info('rtm start for ' +  str(workspace))
    room_parking_channel = None

    @MSGRAPH.tokengetter
    def get_token():
        """Called by flask_oauthlib.client to retrieve current access token."""
        return (token, '')

    # create member dict
    members = list()
    slack_api_members = sc.api_call('users.list')['members']
    for x in slack_api_members:
        name = x['profile']['display_name'] if x['profile']['display_name'] else x['profile']['real_name']
        query_res = Member.get_by_user_workspace(x['id'], workspace)
        if query_res:
            member = query_res
        else:
            member = Member(name, x['profile']['real_name'], x['id'], workspace)
            member.add()
        members.append(member)

    for x in members:
        if x.display_name=='roomparking':
            room_parking_channel = x.user_id
            logger.info(room_parking_channel)
        elif not x.channel_id:
            res = sc.api_call('conversations.open', users=x.user_id)
            if not res.get('error', None):
                x.channel_id = res['channel']['id']
                x.update()

    channel_members = dict()
    for x in members:
        if x.channel_id:
            channel_members[x.channel_id] = x

    with APP.test_request_context():
        if sc.rtm_connect():
            while True:
                try:
                    res = sc.rtm_read()
                # processing, etc
                except (WebSocketConnectionClosedException, TimeoutError, SlackConnectionError) as  e:
                    logger.info('Connecitons was closed. Restarting.')
                    logger.info(e.args)
                    sc.rtm_connect()
                    continue

                if not queue.empty():
                    server_token = queue.get()
                    logger.info('token' + str(server_token))
                    member = channel_members.get(server_token['channel'], False)
                    if server_token['status']=='error' or (not server_token.get('access_token', False)) or (not server_token.get('refresh_token', False)):
                        sc.rtm_send_message(server_token['channel'], 'Sorry there was a problem please try again.')
                    if member and workspace==server_token['workspace'] :

                        member.token = server_token['access_token']
                        member.refresh_token = server_token['refresh_token']
                        member.expires = server_token['expires']
                        logger.info('expires' + str(member.expires) + ' ' + str(member.display_name))
                        member.update()

                        sc.rtm_send_message(member.channel_id,
                                            'Successful authentication! \n {0}'.format(GREETING_TEXT))
                        logger.info('authorized')
                    else:
                        logger.info('not my token')
                        queue.put(server_token)
                        time.sleep(2)
                if len(res) > 0 and type(res[0].get('channel', None)) is not str:
                    logger.info('res' + str(res))
                    continue
                # if len(res) > 0:
                #     logger.info(res)

                if len(res) > 0 and res[0].get('channel', None) in channel_members.keys() and res[0].get('type', None) == 'message' and res[0].get('user', None) != room_parking_channel:
                    member = channel_members[res[0].get('channel', None)]

                    # sc.rtm_send_message(member.channel_id, '{0}, {1}, {2}, {3}'.format(member.expires, utc.localize(member.expires),(datetime.now(utc)+timedelta(hours=1)), eastern.localize(member.expires)<=(datetime.now(utc)+timedelta(hours=1))))
                    if not res[0].get('text', False) or res[0].get('subtype') and res[0]['subtype'] == 'bot_message':
                        continue

                    usage_log = Usage(member.display_name, res[0]['text'].lower()[:79])
                    usage_log.add()


                    if res[0]['text'].lower()=='delete token':
                        member.token = None
                        member.refresh_token = None
                        member.expires = None
                        member.update()

                    if member.token and member.expires and utc.localize(member.expires)<=datetime.now(utc):
                        logger.info('checking for new token')
                        if not check_token(member):
                            sc.rtm_send_message(member.channel_id, 'Couldn\'t update token. Please login again.')
                        else:
                            logger.info('updated token! for ' + str(member.display_name))
                            # sc.rtm_send_message(member.channel_id, 'updated token succesfully.')
                    if not member.token:
                        sc.rtm_send_message(member.channel_id,
                                            'Hello, {name}! This is the Room Booking app for Bloomberg Center at CornellTech.\n'
                                            'It can help you quickly book any room for the next hour. This app will create new meeting on your calendar and invite the selected room. \n'
                                            'To continue please authorize with your Cornell Office 365 account: \n Click here: {ip}?channel={channel}&workspace={workspace} \n'
                                            'Use your Cornell Email (netid@cornell.edu).'.format(name=member.first_name, ip=SERVER_IP, channel=member.channel_id, workspace=workspace))
                    else:
                        token = member.token
                        logger.info('booking for ' + str(member.display_name))

                        member_state = None
                        if member.state:
                            member_state = json.loads(member.state)

                        if member_state and member_state['state'] == 'ancile':
                            text = res[0]['text'].lower()
                            if '@' in text:
                                member.ancile_email = text.split('|')[1][:-1]
                                member.state = None
                                member.update()
                                sc.rtm_send_message(member.channel_id, "Saved email: " + member.ancile_email)
                            elif text == 'exit':
                                member.state = None
                                member.update()
                            else:
                                sc.rtm_send_message(member.channel_id, "Please specify email you used when registering on Ancile or type `exit` to go back")
                        elif member_state and member_state['state'] == 'cancel':
                            try:
                                words = res[0]['text']
                                if words=='exit':
                                    member.state = None
                                    member.update()
                                    sc.rtm_send_message(member.channel_id, GREETING_TEXT)
                                    continue
                                elif int(words) in range(1,len(member_state['data'])+1):

                                    event = member_state['data'][int(words)-1]
                                    # sc.rtm_send_message(member.channel_id, event['id'])
                                    res = MSGRAPH.delete('me/events/' + event['id'], data=None, format='json', headers=request_headers())
                                    if res.status == 204:
                                        sc.rtm_send_message(member.channel_id, 'Successfully deleted meeting.')
                                        member_state['data'].pop(int(words)-1)
                                        response_res = list()
                                        if len(member_state['data'])>0:
                                            for pos, x in enumerate(member_state['data']):

                                                response_res.append('{4}. Meeting at {0}. Starting at {1} until {2} (timezone: {3})'.format(x['location'], x["start"], x["end"], x['timeZone'], pos+1))

                                            sc.rtm_send_message(member.channel_id,
                                                                'Here are the remaining meetings found for your account: \n {0} \n. Please respond with position of the meeting. Ex: ```1``` If only one meeting is presented, please still type: 1.\nTo exit cancellation submenu type ```exit```'.format(
                                                                    '\n'.join(response_res)))
                                        else:
                                            sc.rtm_send_message(member.channel_id, 'Returning back to the main menu.')
                                            member_state = None

                                            sc.rtm_send_message(member.channel_id, GREETING_TEXT)
                                    else:
                                        sc.rtm_send_message(member.channel_id, 'Error deleting meeting:')
                                        sc.rtm_send_message(member.channel_id, res.data)
                                else:
                                    raise ValueError('Please put number from 1 to {0}.'.format(len(member_state['data'])))

                                member.state = json.dumps(member_state) if member_state else None
                                member.update()
                            except Exception as e:
                                logger.info(e)
                                sc.rtm_send_message(member.channel_id, e.args[0])
                                sc.rtm_send_message(member.channel_id, 'Wrong command. Try: ```exit``` or ```1```')
                        else:
                            try:

                                ### autocomplete time
                                time_start = datetime.now(eastern)
                                if time_start.minute >= 20 and time_start.minute<50:
                                    time_start = time_start.replace(microsecond=0, second=0, minute=30, tzinfo=None)
                                elif time_start.minute>=50:
                                    time_start = time_start.replace(microsecond=0, second=0, minute=0, hour=time_start.hour+1, tzinfo=None)
                                else:
                                    time_start = time_start.replace(microsecond=0, second=0, minute=0, tzinfo=None)

                                time_end = time_start + timedelta(hours=1)
                                ### over

                                words = res[0]['text'].split()



                                if words[0].lower() == 'help':
                                    sc.rtm_send_message(member.channel_id, GREETING_TEXT)

                                elif words[0].lower() == 'bnm':
                                    sc.rtm_send_message(member.channel_id, "Book near me for " + member.display_name)
                                    if member.ancile_email:
                                        sc.rtm_send_message(member.channel_id, "Book near me booking for Ancile account: " + member.ancile_email)
                                        js = {"api_token": ANCILE_TOKEN,
                                                                   "program": "get_location_data(); return;",
                                                                   "user": member.ancile_email, "purpose": "research"}
                                        sc.rtm_send_message(member.channel_id, json.dumps(js))
                                        res = requests.post('https://dev.ancile.smalldata.io:4001/api/run',
                                                            json=js)
                                        sc.rtm_send_message(member.channel_id, res.text)
                                        if res.status_code != 200:
                                            sc.rtm_send_message(member.channel_id, "Error.")
                                            if res.status_code != 400:
                                                sc.rtm_send_message(member.channel_id, res.text)
                                        elif res.json()["output"].get("res", False):
                                            floor = res.json()["output"]["res"]["floor_name"]
                                            sc.rtm_send_message(member.channel_id, "You are on the floor: " + floor)
                                            room_selection = {'Third Floor': ['367', '375', '377', '360'], 'Second Floor': ['267', '260', '268', '275'], 'First Floor': False, 'Fourth Floor': False}

                                            if res.json()["output"]["res"]["building_name"] ==  "2360 - Bloomberg Center" \
                                                    and room_selection.get(floor, False):
                                                for room in room_selection[floor]:
                                                    sc.rtm_send_message(member.channel_id, "Booking room " + room)
                                                    room_full = get_room_by_no(room)
                                                    available = is_available_now(room_full, time_start, time_end)
                                                    if available['result'] == 'success':
                                                        if not available['data']:
                                                            sc.rtm_send_message(member.channel_id, 'Room is already occupied!')
                                                            sc.rtm_send_message(member.channel_id, available)
                                                            continue
                                                        else:
                                                            book_json = create_booking_json(user=member.first_name,
                                                                                            room=room_full,
                                                                                            time_start=time_start.isoformat(),
                                                                                            time_end=time_end.isoformat())
                                                            msft_resp = MSGRAPH.post("me/calendar/events", data=book_json, format='json',
                                                                                     headers=request_headers()).data
                                                            if msft_resp.get('error'):
                                                                raise SystemError(msft_resp)
                                                            logger.info(msft_resp)
                                                            sc.rtm_send_message(member.channel_id,
                                                                                'Success! The room {4} was booked for you from {0}:{1:02d} to {2}:{3:02d}.'.format(time_start.hour,
                                                                                                                                                                   time_start.minute,
                                                                                                                                                                   time_end.hour,
                                                                                                                                                                   time_end.minute,
                                                                                                                                                               room))
                                                            break





                                        else:
                                            sc.rtm_send_message(member.channel_id, "Please ask amdin to add a policy that would allow us to grab your data like: `get_location_data.return`.")



                                    else:
                                        dumped_state = json.dumps({'state': 'ancile', 'data': []})
                                        member.state = dumped_state
                                        member.update()
                                        sc.rtm_send_message(member.channel_id, "Please register on https://dev.ancile.smalldata.io:4001 and tell us your email: ")



                                elif words[0].lower()== 'where':
                                    if len(words)>1 and words[1] in room_no:
                                        sc.rtm_send_message(member.channel_id, 'https://chatbots.ancile.smalldata.io/rooms/{0}.jpg'.format(words[1]))
                                    else:
                                        sc.rtm_send_message(member.channel_id,
                                                            'Wrong input. Try ```where 375```')

                                elif words[0].lower() == 'cancel':

                                    msft_resp = MSGRAPH.get("me/events", headers=request_headers()).data
                                    # logger.info(msft_resp)
                                    meetings_by_bot = list()
                                    if len(msft_resp.get('value', list()))>0:
                                        for x in msft_resp['value']:
                                            end_date_time = eastern.localize(dateutil.parser.parse(x['end']['dateTime']))
                                            if x['bodyPreview'] == "This event is created by RoomParking Slackbot, " \
                                                                   "contact Eugene (eugene@cs.cornell.edu) for help." and end_date_time > datetime.now(eastern):
                                                meetings_by_bot.append(get_meeting_info(x))
                                                sc.rtm_send_message(member.channel_id, get_meeting_info(x))
                                                # logger.info(x)
                                    if len(meetings_by_bot)>0:
                                        dumped_state = json.dumps({'state':'cancel', 'data': meetings_by_bot})
                                        if len(dumped_state)>3000:
                                            raise ValueError('Sorry there are too many meetings created that we can\'t handle at once please delete them manually.' )
                                        member.state = dumped_state
                                        member.update()

                                        response_res = list()
                                        for pos, x in enumerate(meetings_by_bot):
                                            response_res.append('{4}. Meeting at {0}. Starting at {1} until {2} (timezone: {3})'.format(x['location'], x["start"], x["end"], x['timeZone'], pos+1))
                                        sc.rtm_send_message(member.channel_id,
                                                            'Here are the meetings found for your account: \n {0} \nPlease respond with the position of the meeting. Ex: ```1``` If only one meeting present, please still type: 1. To exit the cancelling submenu type exit.'.format('\n'.join(response_res)))
                                        logger.info(meetings_by_bot)
                                        sc.rtm_send_message(member.channel_id, meetings_by_bot)
                                    else:
                                        sc.rtm_send_message(member.channel_id,
                                                            'No meetings created by our bot has been found for your account. Book some now! ' )


                                elif words[0].lower()=='list':
                                    if len(words[1])>1:
                                        floor = int(words[1][0])
                                    else:
                                        floor = int(words[1])
                                    if floor not in [0, 1, 2, 3, 4]:
                                        raise ValueError('Floor is wrong. Use: 0, 1, 2, 3, 4')
                                    sc.rtm_send_message(member.channel_id,
                                                        'Looking for available rooms...')
                                    rooms = get_available_by_floor(floor, MSGRAPH, time_start, time_end)
                                    if rooms['result']=='success':
                                        if rooms['data']:
                                            sc.rtm_send_message(member.channel_id, 'Available rooms on floor #{0}: \n {1}. \n (VC - Video Conferencing, D - Display)'.format(floor, ','.join(rooms['data']))) #  \n\nCheck Michael Wilber\'s nice visualization of available rooms: https://cornell-tech-rooms.herokuapp.com
                                        else:
                                            sc.rtm_send_message(member.channel_id,
                                                                'There are no available rooms on floor #{0}'.format(floor))
                                    else:
                                        if rooms['data']['error']['message']=='Access token has expired.':
                                            member.token = None
                                            member.refresh_token = None
                                            member.update()
                                            sc.rtm_send_message(member.channel_id, 'Token is expired, please login again.')
                                        else:
                                            sc.rtm_send_message(member.channel_id, rooms['data'])
                                    continue

                                elif words[0].lower()=='book':


                                    if len(words)==1:
                                        sc.rtm_send_message(member.channel_id, 'Please specify room number, like: "book 375".')
                                        continue

                                    if len(words)==3:
                                        time_new = words[2]
                                        if 'pm' == time_new[-2:]:
                                            time_hour = int(time_new[:-2]) + 12
                                        elif 'am' == time_new[-2:]:
                                            time_hour = int(time_new[:-2])
                                        else:
                                            raise ValueError('If you want to specify time for booking. Follow this example: ```book 375 11am``` or ```book 375 2pm``` The room will be booked for one hour starting the time you posted.')

                                        # sc.rtm_send_message(member.channel_id, time_start.isoformat())
                                        # sc.rtm_send_message(member.channel_id, time_end.isoformat())

                                        time_start = time_start.replace(microsecond=0, second=0, minute=0, hour=time_hour, tzinfo=None)
                                        time_end = time_start + timedelta(hours=1)
                                        # sc.rtm_send_message(member.channel_id, time_start.isoformat())
                                        # sc.rtm_send_message(member.channel_id, time_end.isoformat())


                                    room = words[1]
                                    logger.info(room)
                                    room_full = get_room_by_no(room)
                                    if not room_full:
                                        sc.rtm_send_message(member.channel_id, 'Room not found. Try "list {floor_id}" to get rooms.')
                                        continue

                                    #if room=='367':
                                     #   sc.rtm_send_message(member.channel_id,
                                      #                      'Somehow room 367 cannot be booked. It is not in the Outlook Calendar. I will raise a ticket to IT about it. \n Eugene')
                                       # continue

                                    available =  is_available_now(room_full, time_start, time_end)
                                    if available['result']=='success':
                                        if not available['data']:
                                            sc.rtm_send_message(member.channel_id, 'Room is already occupied!')
                                            sc.rtm_send_message(member.channel_id, available)
                                            continue
                                        else:
                                            book_json = create_booking_json(user=member.first_name,
                                                                            room=room_full,
                                                                            time_start=time_start.isoformat(),
                                                                            time_end=time_end.isoformat())
                                            msft_resp = MSGRAPH.post("me/calendar/events", data=book_json, format='json',
                                                                    headers=request_headers()).data
                                            if msft_resp.get('error'):
                                                raise SystemError(msft_resp)
                                            logger.info(msft_resp)
                                            sc.rtm_send_message(member.channel_id,
                                                                'Success! The room {4} was booked for you from {0}:{1:02d} to {2}:{3:02d}.'.format(time_start.hour,
                                                                                                                            time_start.minute,
                                                                                                                            time_end.hour,
                                                                                                                            time_end.minute,
                                                                                                                            room))
                                    else:
                                        if available['data']=='Access token has expired.':
                                            member.token = None
                                            member.expires = None
                                            member.refresh_token = None
                                            member.update()
                                            sc.rtm_send_message(member.channel_id, 'Token is expired, please login again.')
                                        else:
                                            sc.rtm_send_message(member.channel_id, available['data'])

                                else:
                                    raise ValueError('No commands were matched.')

                                # find_room_json(words[1], str())
                            except Exception as e:
                                logger.info(e)
                                sc.rtm_send_message(member.channel_id,  e.args[0])
                                sc.rtm_send_message(member.channel_id, 'Try: ```help``` or ```book 397``` or ```list 4``` or ```book 375 2pm```')

        else:
            logger.info("Connection Failed")




if __name__ == '__main__':
    for tokens in SLACK_TOKENS:
        p = Process(target=rtm, args=(token, queue, tokens['name'], tokens['token']))
        p.start()

    APP.run(use_reloader=False, host='0.0.0.0', port=8000)
    logger.info(APP.config)
