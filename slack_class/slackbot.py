import multiprocessing
import time

from multiprocessing import Process
from pytz import timezone
import requests
import dateutil.parser
import traceback
import logging

from websocket import WebSocketConnectionClosedException

eastern = timezone('US/Eastern')
utc = timezone('UTC')
import random
# from flask import request
# # import flask
# from data.rooms import *
from oauth_app import *
from slackclient import SlackClient
from config import *

import json

multiprocessing.Process()
import time
from datetime import datetime, timedelta

# DAY_1 = 1
DAY_2 = 5
HOUR = 10
FORMAT_STRING = '%a, %b %d, %I:%M%p'


def get_next_reminder(current_time):

    distance_days = 0
    # if current_time.weekday()<DAY_1  or (current_time.weekday()==DAY_1 and current_time.hour<HOUR):
    #     distance_days = DAY_1 - current_time.weekday()
    if current_time.weekday()<DAY_2 or (current_time.weekday()==DAY_2 and current_time.hour<HOUR):
        distance_days = DAY_2 - current_time.weekday()
    elif current_time.weekday()>=DAY_2:
        distance_days = DAY_2 + current_time.weekday()

    target_day = current_time.replace(hour=HOUR, minute=0, second=0) + timedelta(days=distance_days)

    return target_day

# if for some reason this script is still running
# after a year, we'll stop after 365 days
# def sleep_for(hour):
#     t = .datetime.today()
#     futue = datetime.datetime(t.year, t.month, t.day, 2, 0)
#     if t.hour >= 2:
#         future += timedelta(days=1)
#     time.sleep((future-t).total_seconds())


def rtm(token, queue, workspace, workspace_token):
    sc = SlackClient(workspace_token)
    print('rtm start for ', workspace)
    room_parking_channel = None
    #

    # create member dict
    members = list()
    slack_api_members = sc.api_call('users.list')['members']
    current_time = eastern.fromutc(datetime.today())
    for x in slack_api_members:
        if x['is_bot']:
            continue

        if x['id'] not in ('U8ZRT58TX', 'U8W4XS6EM', 'U8W4T2X6D'):
            continue

        name = x['profile']['real_name'] if x['profile']['real_name'] else x['profile']['display_name']
        query_res = Member.get_by_user_workspace(x['id'], workspace)
        if query_res:
            member = query_res
            if not member.remind:
                member.remind = get_next_reminder(current_time)
                member.add()
        else:
            member = Member(name, x['profile']['real_name'], x['id'], workspace)

            member.remind = get_next_reminder(current_time)
            print(eastern.fromutc(member.remind))
            member.add()
        members.append(member)

    for x in members:
        if x.display_name=='betech_bot':
            room_parking_channel = x.user_id
            print(room_parking_channel)
        elif not x.channel_id:
            res = sc.api_call('conversations.open', users=x.user_id)
            if not res.get('error', None):
                x.channel_id = res['channel']['id']
                sc.api_call('chat.postMessage', channel=x.channel_id,
                                    text='Hey! I am the Slackbot for the BEtech class! I will remind you to do your monday readings. :) ! \n Please ask <@U8W4XS6EM|fabian> if you have any questions!')
                sc.api_call('chat.postMessage', channel=x.channel_id, text=message_test['text'],
                            attachments=message_test['attachments'])
                x.update()

    channel_members = dict()
    for x in members:
        if x.channel_id:
            channel_members[x.channel_id] = x

    with APP.test_request_context():

        if sc.rtm_connect():
            while True:

                current_time = eastern.fromutc(datetime.today())


                try:
                    res = sc.rtm_read()
                # processing, etc
                except (WebSocketConnectionClosedException, TimeoutError) as  e:
                    print('Connecitons was closed. Restarting.')
                    print(e.args)
                    sc.rtm_connect()
                    continue

                if len(res)>0:
                    print(res)

                    if res[0].get('channel', False) in list(channel_members.keys()) and res[0].get('text', False)=='abcd_help':
                        print(res[0]['channel'], res[0]['text'])

                        sc.api_call('chat.postMessage', channel=res[0]['channel'], text=message_test['text'],
                                    attachments=message_test['attachments'])

                    elif res[0].get('channel', False) in list(channel_members.keys()) and res[0].get('text',
                                                                                                   False) == 'abcd_remind':
                        member = Member.get_by_user_workspace(res[0]['user'], workspace)
                        sc.api_call('chat.postMessage', channel=res[0]['channel'],
                                    text=eastern.fromutc(member.remind).strftime(FORMAT_STRING))
                        sc.api_call('chat.postMessage', channel=res[0]['channel'],
                                    text=current_time.strftime(FORMAT_STRING))
                        sc.api_call('chat.postMessage', channel=res[0]['channel'],
                                    text='{0}'.format(datetime.today()))

                    # elif res[0].get('channel', False) in list(channel_members.keys()) and res[0].get('text',
                    #                                                                                  False) and res[0].get(''):
                    #     sc.api_call('chat.postMessage', channel=res[0]['channel'],
                    #                 text='Sorry I did not understand what you said. Please ask <@U8W4XS6EM|fabian> for details.')
                elif not queue.empty():

                    msg = queue.get()
                    print(msg)
                    try:
                        loaded_msg = json.loads(msg['payload'])
                        print(loaded_msg)
                        actions = loaded_msg['actions'][0]
                        channel_id = loaded_msg['channel']['id']
                        user_id = loaded_msg['user']['id']
                        user_name = loaded_msg['user']['name']
                        member = Member.get_by_user_workspace(user_id, workspace)
                        if actions['type'] == 'button':
                            status = actions['value']
                            # if actions['value']:
                            #     sc.api_call('chat.postMessage', channel=member.channel_id, text='<#C9HQF457W|readings>')
                            member.remind = get_next_reminder(current_time)
                        else:
                            status = actions['selected_options'][0]['value']
                            if status=='never':
                                # sc.api_call('chat.postMessage', channel=channel_id,
                                #             text='We will not remind you until the next week.')
                                member.remind = get_next_reminder(current_time)
                            elif status=='tomorrow':
                                member.remind = current_time + timedelta(days=1)
                            else:
                                member.remind = current_time + timedelta(minutes=int(status))

                        member.update()
                        sc.api_call('chat.postMessage', channel=channel_id,
                                    text='Thank you, the next reminder will be on: {0}'.format((eastern.fromutc(member.remind)).strftime(FORMAT_STRING)))

                        new_action = Reminder(user_name, status)
                        new_action.add()
                    except ChildProcessError as e:
                        print(e)

                else:

                    print('success')
                    for x in members:
                        # sc.api_call('chat.postMessage', channel=x.channel_id, text=eastern.fromutc(x.remind))
                        # sc.api_call('chat.postMessage', channel=x.channel_id, text=current_time)
                        if not x.remind:
                            x.remind = get_next_reminder(current_time)
                            x.update()
                        elif eastern.fromutc(x.remind)<current_time:
                            sc.api_call('chat.postMessage', channel=x.channel_id, text=message_test['text'],
                                            attachments=message_test['attachments'])

                            x.remind = get_next_reminder(current_time)
                            x.update()

                    time.sleep(1)








if __name__ == '__main__':
    db.create_all()
    for tokens in SLACK_TOKENS:
        p = Process(target=rtm, args=(token, queue, tokens['name'], tokens['token']))
        p.start()

    APP.run(use_reloader=False, host='0.0.0.0', port=8000)
    print(APP.config)