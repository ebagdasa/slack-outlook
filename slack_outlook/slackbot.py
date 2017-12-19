import multiprocessing
import time
from datetime import datetime, timedelta
from multiprocessing import Process

from classes.Member import Member
from pytz import timezone

eastern = timezone('US/Eastern')

# from flask import request
# import flask
from data.rooms import *
from data.templates import *
from oauth_app import *
from slackclient import SlackClient
from config import *

slack_token = SLACK_TOKEN
sc = SlackClient(slack_token)
multiprocessing.Process()


def is_available_now(room_full, time_start, time_end):

    find_json = find_room_json(room=room_full,
                               time_start=time_start.isoformat(),
                               time_end=time_end.isoformat())
    print(find_json)
    msft_resp = MSGRAPH.post("me/findMeetingTimes", data=find_json, format='json',
                             headers=request_headers()).data
    if msft_resp.get('error', None):
        print(msft_resp)
    if len(msft_resp.get('meetingTimeSuggestions', list())) == 0:
        return False
    else:
        return True

def get_available_by_floor(floor, msg_graph, time_start, time_end):
    rooms = get_rooms_by_floor(floor)
    available_rooms = list()
    rooms_json = check_floor_json(rooms, time_start, time_end)
    msft_resp = MSGRAPH.post("me/findMeetingTimes", data=rooms_json, format='json',
                             headers=request_headers()).data

    if msft_resp.get('error', None):
        print(msft_resp)
    elif len(msft_resp['meetingTimeSuggestions']) > 0:
        for x in msft_resp['meetingTimeSuggestions'][0]["attendeeAvailability"]:
            if x["availability"] == "free":
                available_rooms.append(room_by_email(x["attendee"]['emailAddress']['address']))

    return available_rooms




def rtm(token, queue):
    print('rtm start')
    room_parking_channel = None

    @MSGRAPH.tokengetter
    def get_token():
        """Called by flask_oauthlib.client to retrieve current access token."""
        return (token, '')

    # create member dict
    members = list()
    for x in sc.api_call('users.list')['members']:
        members.append(Member(x['profile']['display_name'], x['profile']['real_name'], x['id']))

    for x in members:
        if x.display_name=='roomparking':
            room_parking_channel = x.user_id
            print(room_parking_channel)
        if x.display_name=='ebagdasa':
            res = sc.api_call('conversations.open', users=x.user_id)
            if not res.get('error', None):
                x.channel_id = res['channel']['id']

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
                    channel_members[server_token[0]].token = server_token[1]
                    sc.rtm_send_message(server_token[0],
                                        'Successful authentication! \n '
                                        "Please use following commands: \n  ```list #floor  - gives the list of rooms for selected command (Ex: list 3)``` \n  ```book #room_no  -- book a room for next hour. (Ex: book 375)``` \n ```help  -- repeat the menu ``` \n ```cancel``` to cancel created by the bot meetings.")
                    print('authorized')
                # if len(res) > 0:
                #     print('res', res)

                if len(res)> 0  and res[0].get('channel', None) in channel_members.keys() and res[0].get('type', None) == 'message' and res[0].get('user', None) != room_parking_channel:
                    member = channel_members[res[0].get('channel', None)]
                    if not member.token:
                        sc.rtm_send_message(member.channel_id, 'Hello {name}! To continue authorize with Cornell Office 365 account: \n Click here: {ip}?user={channel} \n Use your Cornell Email (netid@cornell.edu).'.format(name=member.first_name, ip=SERVER_IP, channel=member.channel_id))

                    else:
                        token = member.token
                        print('booking for ', member.display_name)

                        if member.state and member.state['state'] == 'cancel':
                            try:
                                words = res[0]['text']
                                if words=='exit':
                                    member.state = None
                                    continue
                                elif int(words) in range(1,len(member.state['data'])+1):
                                    event = member.state['data'][int(words)-1]
                                    sc.rtm_send_message(member.channel_id, event['id'])
                                    res = MSGRAPH.delete('me/events/' + event['id'], data=None, format='json', headers=request_headers())
                                    if res.status == 204:
                                        sc.rtm_send_message(member.channel_id, 'Successfully deleted meeting.')
                                        member.state['data'].pop(int(words)-1)
                                        if len(member.state['data'])>0:
                                            for pos, x in enumerate(member.state['data']):
                                                res.append(
                                                    '{4}. Meeting at {0}. Starting at {1} until {2} (timezone: {3})'.format(
                                                        x['location']['displayName'], x["start"]['dateTime'],
                                                        x["end"]['dateTime'], x['end']['timeZone'], pos + 1))
                                            sc.rtm_send_message(member.channel_id,
                                                                'Here are the remaining meetings found for your account: \n {0} \n. Please respond with position of the meeting. Ex: ```1``` If only one meeting, please still type: 1. To exit the cancelling submenu type exit.'.format(
                                                                    '\n'.join(res)))
                                        else:
                                            sc.rtm_send_message(member.channel_id, 'Returning back to the main menu.')
                                            member.state=None

                                    else:
                                        sc.rtm_send_message(member.channel_id, 'Error deleted meeting:')
                                        sc.rtm_send_message(member.channel_id, res.data)
                                else:
                                    raise ValueError('Please put number from 1 to {0}.'.format(len(member.state['data'])))

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
                                    sc.rtm_send_message(member.channel_id, "Please use following commands: \n  ```list #floor  - gives the list of rooms``` \n  ```book #room_no  -- book a room for next hour``` \n ```help  -- repeat the menu ```")


                                elif words[0].lower() == 'cancel':

                                    msft_resp = MSGRAPH.get("me/events", headers=request_headers()).data
                                    print(msft_resp)
                                    meetings_by_bot = list()
                                    if len(msft_resp.get('value', list()))>0:
                                        for x in msft_resp['value']:
                                            if x['bodyPreview'] == "This event is created by RoomParking Slackbot, contact Eugene (eugene@cs.cornell.edu) for help.":
                                                meetings_by_bot.append(x)
                                                sc.rtm_send_message(member.channel_id, x)
                                                print(x)
                                    if len(meetings_by_bot)>0:
                                        member.state = {'state':'cancel', 'data': meetings_by_bot}

                                        res = list()
                                        for pos, x in enumerate(meetings_by_bot):
                                            res.append('{4}. Meeting at {0}. Starting at {1} until {2} (timezone: {3})'.format(x['location']['displayName'], x["start"]['dateTime'], x["end"]['dateTime'], x['end']['timeZone'], pos+1))
                                        sc.rtm_send_message(member.channel_id,
                                                            'Here are the meetings found for your account: \n {0} \n. Please respond with position of the meeting. Ex: ```1``` If only one meeting, please still type: 1. To exit the cancelling submenu type exit.'.format('\n'.join(res)))
                                        print(meetings_by_bot)
                                        sc.rtm_send_message(member.channel_id, meetings_by_bot)
                                    else:
                                        sc.rtm_send_message(member.channel_id,
                                                            'No meetings found for your account' )


                                elif words[0].lower()=='list':
                                    if len(words[1])>1:
                                        floor = int(words[1][0])
                                    else:
                                        floor = int(words[1])
                                    if floor not in [0, 1, 2, 3, 4]:
                                        raise ValueError('Floor is wrong use: 0, 1, 2, 3, 4')
                                    rooms = get_available_by_floor(floor, MSGRAPH, time_start, time_end)
                                    if rooms:
                                        sc.rtm_send_message(member.channel_id, 'Available rooms on {0} floor: \n {1}'.format(words[1], ','.join(rooms)))
                                    else:
                                        sc.rtm_send_message(member.channel_id,
                                                            'There are no available rooms on floor # {0}'.format(floor))
                                    continue

                                elif words[0].lower()=='book':

                                    room = words[1]
                                    print(room)
                                    room_full = get_room_by_no(room)

                                    if not is_available_now(room_full, time_start, time_end):
                                        sc.rtm_send_message(member.channel_id, 'Room is already occupied.')
                                        continue

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
                                    raise ValueError('No commands were matched.')

                                # find_room_json(words[1], str())
                            except Exception as e:
                                print(e)
                                sc.rtm_send_message(member.channel_id,  e.args[0])
                                sc.rtm_send_message(member.channel_id, 'Try: ```book 397``` or ```list 4```')

        else:
            print("Connection Failed")




if __name__ == '__main__':

    p = Process(target=rtm, args=(token, queue))
    p.start()
    APP.run(use_reloader=False, host='0.0.0.0', port=8000)
    print(APP.config)