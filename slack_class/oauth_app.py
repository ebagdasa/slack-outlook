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
from flask import request, Response
import pprint
from flask_oauthlib.client import OAuth
from flask import jsonify
import config
from flask_sqlalchemy import SQLAlchemy


APP = flask.Flask(__name__, template_folder='static/templates')
APP.debug = True
APP.host = config.SERVER_IP
APP.secret_key = 'development'
APP.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://{0}:{0}@database_class:5432/{0}'.format('postgres')
APP.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(APP)
OAUTH = OAuth(APP)
token = dict()
queue = Queue()


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
    display_name = db.Column(db.String(250), nullable=False)
    first_name = db.Column(db.String(250), nullable=False)
    user_id = db.Column(db.String(80), nullable=False)
    channel_id = db.Column(db.String(80), nullable=True)
    token = db.Column(db.String(3000), nullable=True)
    state = db.Column(db.String(3000), nullable=True)
    workspace = db.Column(db.String(120), nullable=False)
    refresh_token = db.Column(db.String(3000), nullable=True)
    expires = db.Column(db.DateTime, nullable=True)
    remind = db.Column(db.Integer, nullable=True)


    def __init__(self, dn, fn, uid, workspace):
        self.display_name = dn
        self.first_name = fn
        self.user_id = uid
        self.workspace = workspace

    @staticmethod
    def get_by_user_workspace(user_id, workspace):
        res = Member.query.filter_by(user_id=user_id, workspace=workspace).first()
        return res if res else None


class Reminder(Base):
    user_id = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(80), nullable=False)


@APP.route('/request_proc', methods = ['GET', 'POST'])
def request_proc():
    print(request.form)
    queue.put(request.form)
    return jsonify(config.message_respond)



@APP.route('/data_load', methods = ['GET', 'POST'])
def data_load():
    print('request')
    queue.put('successfully received')
    print(request.form)
    queue.put(request.form)

    return


