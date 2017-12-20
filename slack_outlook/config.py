"""Configuration settings for running the Python auth samples locally.

In a production deployment, this information should be saved in a database or
other secure storage mechanism.
"""
from secret import *

REDIRECT_URI = '{ip}/login/authorized'.format(ip=SERVER_IP)
AUTHORITY_URL = 'https://login.microsoftonline.com/common'
AUTH_ENDPOINT = '/oauth2/v2.0/authorize'
TOKEN_ENDPOINT = '/oauth2/v2.0/token'

RESOURCE = 'https://graph.microsoft.com/'
API_VERSION = 'beta'
GREETING_TEXT =  "Please use following commands: ```list floor_no  -- show the list of available rooms on floor_no. (Ex: list 3)```\n```book room_no  -- book room_no for the next hour. (Ex:  book 375) ```\n```help  -- repeat the menu ``` \n ```cancel -- to cancel created by the bot meetings```"


# This code can be removed after configuring CLIENT_ID and CLIENT_SECRET above.
if 'ENTER_YOUR' in CLIENT_ID or 'ENTER_YOUR' in CLIENT_SECRET:
    print('ERROR: config.py does not contain valid CLIENT_ID and CLIENT_SECRET')
    import sys
    sys.exit(1)
