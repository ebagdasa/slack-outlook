import multiprocessing
import time
from datetime import datetime, timedelta
from multiprocessing import Process
from pytz import timezone
import requests
import dateutil.parser
import traceback
eastern = timezone('US/Eastern')

# from flask import request
# import flask
from data.rooms import *
from data.templates import *
from oauth_app import *
from slackclient import SlackClient
from config import *

import json

multiprocessing.Process()


def check_token(member):

    data = {'grant_type': 'refresh_token', 'refresh_token': member.token, 'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET}
    response = requests.post(AUTHORITY_URL+TOKEN_ENDPOINT, data)
    print(response)
    member.token = response['access_token']
    member.refresh_token = response['refresh_token']
    member.expires = datetime.now(eastern) + timedelta(seconds=response['expires_in'])
    member.update()

def is_available_now(room_full, time_start, time_end):

    find_json = find_room_json(room=room_full,
                               time_start=time_start.isoformat(),
                               time_end=time_end.isoformat())
    print(find_json)
    msft_resp = MSGRAPH.post("me/findMeetingTimes", data=find_json, format='json',
                             headers=request_headers()).data
    if msft_resp.get('error', None):
        print(msft_resp)
        return {'result': 'error', 'data': msft_resp}
    if len(msft_resp.get('meetingTimeSuggestions', list())) == 0:
        return {'result': 'success', 'data': False}
    else:
        return {'result': 'success', 'data': True}

def get_available_by_floor(floor, msg_graph, time_start, time_end):
    rooms = get_rooms_by_floor(floor)
    available_rooms = list()
    rooms_json = check_floor_json(rooms, time_start, time_end)
    msft_resp = MSGRAPH.post("me/findMeetingTimes", data=rooms_json, format='json',
                             headers=request_headers()).data

    if msft_resp.get('error', None):
        print(msft_resp)
        return {'result': 'error', 'data': msft_resp}
    elif len(msft_resp['meetingTimeSuggestions']) > 0:
        for x in msft_resp['meetingTimeSuggestions'][0]["attendeeAvailability"]:
            if x["availability"] == "free":
                available_rooms.append(room_by_email(x["attendee"]['emailAddress']['address']))

    return {'result': 'success', 'data': available_rooms}




def rtm(token, queue, workspace, workspace_token):
    sc = SlackClient(workspace_token)
    print('rtm start for ', workspace)
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
            print(room_parking_channel)
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
                res = sc.rtm_read()
                if not queue.empty():
                    server_token = queue.get()
                    print('token', server_token)
                    member = channel_members.get(server_token['channel'], False)
                    if member and workspace==server_token['workspace']:

                        member.token = server_token['access_token']
                        member.refresh_token = server_token['refresh_token']
                        member.expires = server_token['expires']
                        print('expires', member.expires, ' ', member.display_name)
                        member.update()

                        sc.rtm_send_message(member.channel_id,
                                            'Successful authentication! \n {0}'.format(GREETING_TEXT))
                        print('authorized')
                    else:
                        print('not my token')
                        queue.put(server_token)
                        time.sleep(2)
                # if len(res) > 0:
                #     print('res', res)

                if len(res)> 0  and res[0].get('channel', None) in channel_members.keys() and res[0].get('type', None) == 'message' and res[0].get('user', None) != room_parking_channel:
                    member = channel_members[res[0].get('channel', None)]
                    if not member.token:
                        sc.rtm_send_message(member.channel_id,
                                            'Hello, {name}! This is the Room Booking app for Bloomberg Center at CornellTech.\n'
                                            'It can help you quickly book any room for the next hour. This app will create new meeting on your calendar and invite the selected room. \n'
                                            'To continue please authorize with your Cornell Office 365 account: \n Click here: {ip}?channel={channel}&workspace={workspace} \n'
                                            'Use your Cornell Email (netid@cornell.edu).'.format(name=member.first_name, ip=SERVER_IP, channel=member.channel_id, workspace=workspace))
                    elif member.token and member.expires and eastern.localize(member.expires)<=datetime.now(eastern)+timedelta(minutes=30):
                        print('checking for new token')
                        check_token(member)
                    else:
                        token = member.token
                        print('booking for ', member.display_name)

                        member_state = None
                        if member.state:
                            member_state = json.loads(member.state)
                        if member_state and member_state['state'] == 'cancel':
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
                                print(e)
                                sc.rtm_send_message(member.channel_id, e.args[0])
                                sc.rtm_send_message(member.channel_id, 'Wrong command. Try: ```exit``` or ```1```')
                        else:
                            try:

                                ### autocomplete time
                                time_start = datetime.now(eastern)
                                if time_start.minute >= 30:
                                    time_start = time_start.replace(microsecond=0, second=0, minute=30, tzinfo=None)
                                else:
                                    time_start = time_start.replace(microsecond=0, second=0, minute=0, tzinfo=None)

                                time_end = time_start + timedelta(hours=1)
                                ### over

                                words = res[0]['text'].split()



                                if words[0].lower() == 'help':
                                    sc.rtm_send_message(member.channel_id, GREETING_TEXT)


                                elif words[0].lower() == 'cancel':

                                    msft_resp = MSGRAPH.get("me/events", headers=request_headers()).data
                                    print(msft_resp)
                                    meetings_by_bot = list()
                                    if len(msft_resp.get('value', list()))>0:
                                        for x in msft_resp['value']:
                                            end_date_time = eastern.localize(dateutil.parser.parse(x['end']['dateTime']))
                                            if x['bodyPreview'] == "This event is created by RoomParking Slackbot, " \
                                                                   "contact Eugene (eugene@cs.cornell.edu) for help." and end_date_time > datetime.now(eastern):
                                                meetings_by_bot.append(get_meeting_info(x))
                                                sc.rtm_send_message(member.channel_id, get_meeting_info(x))
                                                print(x)
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
                                        print(meetings_by_bot)
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
                                        raise ValueError('Floor is wrong use: 0, 1, 2, 3, 4')
                                    rooms = get_available_by_floor(floor, MSGRAPH, time_start, time_end)
                                    if rooms['result']=='success':
                                        if rooms['data']:
                                            sc.rtm_send_message(member.channel_id, 'Available rooms on floor #{0}: \n {1}'.format(words[1], ','.join(rooms['data']))) #  \n\nCheck Michael Wilber\'s nice visualization of available rooms: https://cornell-tech-rooms.herokuapp.com
                                        else:
                                            sc.rtm_send_message(member.channel_id,
                                                                'There are no available rooms on floor #{0}'.format(floor))
                                    else:
                                        if rooms['data']['error']['message']=='Access token has expired.':
                                            member.token = None
                                            member.update()
                                            sc.rtm_send_message(member.channel_id, 'Token is expired, please login again.')
                                        else:
                                            sc.rtm_send_message(member.channel_id, rooms['data'])
                                    continue

                                elif words[0].lower()=='book':

                                    room = words[1]
                                    print(room)
                                    room_full = get_room_by_no(room)
                                    available =  is_available_now(room_full, time_start, time_end)
                                    if available['result']=='success':
                                        if not available['data']:
                                            sc.rtm_send_message(member.channel_id, 'Room is already occupied.')
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
                                            print(msft_resp)
                                            sc.rtm_send_message(member.channel_id,
                                                                'The room {4} is booked from {0}:{1:02d} to {2}:{3:02d}.'.format(time_start.hour,
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
                                print(e)
                                sc.rtm_send_message(member.channel_id,  e.args[0])
                                sc.rtm_send_message(member.channel_id, 'Try: ```book 397``` or ```list 4```')

        else:
            print("Connection Failed")




if __name__ == '__main__':
    db.create_all()
    for tokens in SLACK_TOKENS:
        p = Process(target=rtm, args=(token, queue, tokens['name'], tokens['token']))
        p.start()

    APP.run(use_reloader=False, host='0.0.0.0', port=8000)
    print(APP.config)