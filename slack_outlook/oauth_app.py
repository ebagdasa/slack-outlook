"""send-email sample for Microsoft Graph"""
# Copyright (c) Microsoft. All rights reserved. Licensed under the MIT license.
# See LICENSE in the project root for license information.
import base64
import pprint
import uuid
from multiprocessing import Queue
from datetime import datetime, timedelta
import pytz
eastern = pytz.timezone('US/Eastern')
import flask
from flask import request
from flask_oauthlib.client import OAuth

import config
from flask_sqlalchemy import SQLAlchemy


APP = flask.Flask(__name__, template_folder='static/templates')
APP.debug = True
APP.host = config.SERVER_IP
APP.secret_key = 'development'
APP.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://{0}:{0}@database:5432/{0}'.format('postgres')
# APP.config['SQLALCHEMY_ECHO'] = True
db = SQLAlchemy(APP)
OAUTH = OAuth(APP)
token = dict()
queue = Queue()
MSGRAPH = OAUTH.remote_app(
    'microsoft',
    consumer_key=config.CLIENT_ID,
    consumer_secret=config.CLIENT_SECRET,
    request_token_params={'scope': config.SCOPES},
    base_url=config.RESOURCE + config.API_VERSION + '/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url=config.AUTHORITY_URL + config.TOKEN_ENDPOINT,
    authorize_url=config.AUTHORITY_URL + config.AUTH_ENDPOINT)


class Base(db.Model):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    modified_at = db.Column(db.DateTime, default=db.func.current_timestamp(),
                            onupdate=db.func.current_timestamp())
    def add(self):
        db.session.add(self)
        return db.session.commit()

    def update(self):
        return db.session.commit()

    def delete(self):
        db.session.delete(self)
        return db.session.commit()

class Member(Base):
    floor = db.Column(db.Integer)
    display_name = db.Column(db.String(80), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    user_id = db.Column(db.String(80), nullable=False)
    channel_id = db.Column(db.String(80), nullable=True)
    token = db.Column(db.String(3000), nullable=True)
    state = db.Column(db.String(3000), nullable=True)
    workspace = db.Column(db.String(80), nullable=False)
    refresh_token = db.Column(db.String(3000), nullable=True)
    expires =


    def __init__(self, dn, fn, uid, workspace):
        self.display_name = dn
        self.first_name = fn
        self.user_id = uid
        self.workspace = workspace

    @staticmethod
    def get_by_user_workspace(user_id, workspace):
        res = Member.query.filter_by(user_id=user_id, workspace=workspace).first()
        return res if res else None



@APP.route('/')
def login():
    """Prompt user to authenticate."""


    flask.session['state'] = request.values['user'] + '________' + request.values['workspace']
    return MSGRAPH.authorize(callback=config.REDIRECT_URI, state=flask.session['state'])

@APP.route('/login/authorized')
def authorized():
    """Handler for the application's Redirect Uri."""
    print(flask.request)
    if str(flask.session['state']) != str(flask.request.args['state']):
        raise Exception('state returned to redirect URL does not match!')
    response = MSGRAPH.authorized_response()
    flask.session['access_token'] = response['access_token']
    print(response['refresh_token'])
    token['access'] = response['access_token']
    state, workspace = flask.session['state'].split('________')
    expires = datetime.now() + timedelta(seconds=int(response['expires_in']))
    queue.put((state, workspace, response['access_token'], response['refresh_token'], expires))
    # room_data = MSGRAPH.get("me/findRooms(RoomList='CT-Bloomberg@groups.cornell.edu')", headers=request_headers()).data

    return flask.render_template('success.html')


def request_headers():
    """Return dictionary of default HTTP headers for Graph API calls."""
    return {'SdkVersion': 'sample-python-flask',
            'x-client-SKU': 'sample-python-flask',
            'client-request-id': str(uuid.uuid4()),
            'Prefer': 'outlook.timezone="Eastern Standard Time"',
            'return-client-request-id': 'true'}
