import multiprocessing
import time
from datetime import datetime, timedelta
from multiprocessing import Process
from pytz import timezone
import requests
import dateutil.parser
import traceback
import logging

from websocket import WebSocketConnectionClosedException

eastern = timezone('US/Eastern')
utc = timezone('UTC')
# from flask import request
# # import flask
# from data.rooms import *
from oauth_app import *
from slackclient import SlackClient
from config import *

import json

multiprocessing.Process()


import time
import datetime

# if for some reason this script is still running
# after a year, we'll stop after 365 days
def sleep_for(hour):
    t = datetime.datetime.today()
    future = datetime.datetime(t.year, t.month, t.day, 2, 0)
    if t.hour >= 2:
        future += datetime.timedelta(days=1)
    time.sleep((future-t).total_seconds())


def rtm(token, queue, workspace, workspace_token):
    sc = SlackClient(workspace_token)
    print('rtm start for ', workspace)
    room_parking_channel = None
    #

    # create member dict
    members = list()
    slack_api_members = sc.api_call('users.list')['members']
    for x in slack_api_members:
        # if x['is_bot']:
        #     continue

        if x['id'] not in ('U3G50LK24',):
            continue

        name = x['profile']['display_name'] if x['profile']['display_name'] else x['profile']['real_name']
        query_res = Member.get_by_user_workspace(x['id'], workspace)
        if query_res:
            member = query_res
        else:
            member = Member(name, x['profile']['real_name'], x['id'], workspace)
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
                except (WebSocketConnectionClosedException, TimeoutError) as  e:
                    print('Connecitons was closed. Restarting.')
                    print(e.args)
                    sc.rtm_connect()
                    continue




                if len(res)>0:
                    print(res)
                    if res[0].get('channel', False) == 'D9J7J4GJG' and res[0].get('text', False)=='help':
                        print(res[0]['channel'], res[0]['text'])

                        sc.api_call('chat.postMessage', channel='D9J7J4GJG', text=message_test['text'],
                                    attachments=message_test['attachments'])

                elif not queue.empty():
                    msg = queue.get()
                    print(msg)
                    try:
                        loaded_msg = json.loads(msg['payload'])
                        print(loaded_msg)
                        actions = loaded_msg['actions'][0]
                        if actions['type'] == 'button':
                            status = actions['value']
                            sc.api_call('chat.postMessage', channel='D9J7J4GJG', text=actions['value'])
                        else:
                            status = actions['selected_options'][0]['value']
                            sc.api_call('chat.postMessage', channel='D9J7J4GJG', text=actions['selected_options'][0]['value'])

                    except KeyError or IndexError:
                        print('error')

                else:
                    time.sleep(10)
                    print('sleeping')
                    current_time = datetime.datetime.today()
                    if current_time.weekday() in (0,6) and current_time.hour == 22:
                        for x in members:
                            sc.api_call('chat.postMessage', channel=x.channel_id, text=message_test['text'],
                                        attachments=message_test['attachments'])







if __name__ == '__main__':
    # db.create_all()
    for tokens in SLACK_TOKENS:
        p = Process(target=rtm, args=(token, queue, tokens['name'], tokens['token']))
        p.start()

    APP.run(use_reloader=False, host='0.0.0.0', port=8000)
    print(APP.config)