
import subprocess
import multiprocessing
from multiprocessing import Process, Queue
from classes.Member import Member
import json
import time
from datetime import datetime, timedelta
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
    if len(msft_resp['meetingTimeSuggestions']) == 0:
        return False
    else:
        return True

def get_available_by_floor(floor, msg_graph, time_start, time_end):
    rooms = get_rooms_by_floor(floor)
    available_rooms = list()
    for room_full in rooms:
        if is_available_now(room_full=room_full, time_start=time_start, time_end=time_end):
            available_rooms.append(room_full['name'].split()[3])
    return available_rooms




def rtm(token, queue):
    print('rtm start')

    @MSGRAPH.tokengetter
    def get_token():
        """Called by flask_oauthlib.client to retrieve current access token."""
        return (token, '')

    # create member dict
    members = list()
    for x in sc.api_call('users.list')['members']:
        members.append(Member(x['profile']['display_name'], x['profile']['real_name'], x['id']))

    for x in members:
        if x.display_name == 'ebagdasa':
            res = sc.api_call('conversations.open', users=x.user_id)
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
                                        "Please use following commands: \n  1. ```list #floor```  -- gives the list of rooms \n 2. ```book #room_no```  -- book a room for next hour ")
                    print('authorized')
                # if len(res) > 0:
                    # print('res', res)

                if len(res)> 0  and res[0].get('channel', None) in channel_members.keys() and res[0].get('type', None) == 'message' and res[0].get('user', None) != 'U8D4CNM5K':
                    member = channel_members[res[0].get('channel', None)]
                    if not member.token:

                        sc.rtm_send_message(member.channel_id, 'Hello {0}! To continue authorize with Cornell Office 365 account: \n Click here: http://localhost:5000?user={1}'.format(member.first_name, member.channel_id))



                    else:
                        token = member.token
                        print('booking for ', member.display_name)
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

                            if words[0]=='list':
                                floor = int(words[1])
                                if floor not in [0, 1, 2, 3, 4]:
                                    raise ValueError('Floor is wrong use: 0, 1, 2, 3, 4')
                                rooms = get_available_by_floor(floor, MSGRAPH, time_start, time_end)
                                sc.rtm_send_message(member.channel_id, 'Available rooms on {0} floor: \n {1}'.format(words[1], ','.join(rooms)))
                                continue

                            elif words[0]=='book':

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
                                raise ValueError('wrong text. Try: ```book 397``` or ```floor 4```')

                            # find_room_json(words[1], str())
                        except Exception as e:
                            print(e)
                            sc.rtm_send_message(member.channel_id, e.args[0])

                    time.sleep(2)
        else:
            print("Connection Failed")




if __name__ == '__main__':

    p = Process(target=rtm, args=(token, queue))
    p.start()
    APP.run(use_reloader=False)