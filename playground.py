from slackclient import SlackClient
from slack_outlook.secret import *
slack_token = SLACK_TOKEN
sc = SlackClient(slack_token)

if sc.rtm_connect():
    while True:
        res = sc.rtm_read()

        if len(res) > 0:
            print(res)