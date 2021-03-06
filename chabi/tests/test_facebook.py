"""Basic tests."""
import json

from flask import Flask, Blueprint
from pony import orm
import pytest

from chabi import ChatbotBase
from chabi.vendor.facebook import Facebook, EventHandlerBase, blueprint as fbbp
from chabi.models import db


blueprint = Blueprint('dummy', __name__)


class DummyChatbot(ChatbotBase):
    def __init__(self, app, access_token):
        super(DummyChatbot, self).__init__(app, blueprint)

    def request_analyze(self, sender, msg):
        return None

    def handle_unknown(self, data):
        return False, None

    def handle_incomplete(self, data):
        return False, None


class EventHandler(EventHandlerBase):

    def handle_postback(self, msg):
        payload = msg['payload']
        if payload == 'START_BUTTON':
            res = "start button pressed"
        else:
            res = "Unknown postback payload '{}'".format(payload)
        return dict(message=dict(text=res))


@pytest.fixture()
def app():
    ap = Flask(__name__)
    Facebook(ap, 'access_token', 'verify_token')
    DummyChatbot(ap, 'cb_access_token')
    EventHandler(ap)
    ap.config['TESTING'] = True
    return ap


def test_facebook_basic(app):
    with app.test_client():
        sender_id = "1265395423496458"
        msg = app.msgn.ask_enter_text_msg(sender_id)
        assert msg['message']['text'] == 'Please enter text message.'


def test_facebook_webhook(app):
    """Facebook webhook test."""
    # default GET
    with app.test_client() as c:
        r = c.get('/facebook')
        assert 'OK' == r.data.decode('utf8')
        assert '200 OK' == r.status

    # GET with bad verify token
    with app.test_client() as c:
        r = c.get('/facebook?hub.mode=subscribe&hub.challenge=access_token'
                  '&hub.verify_token=BAD')
        assert 'Verification token mismatch' == r.data.decode('utf8')
        assert '403 FORBIDDEN' == r.status

    # GET with good verify token
    with app.test_client() as c:
        r = c.get('/facebook?hub.mode=subscribe&hub.challenge=access_token'
                  '&hub.verify_token=verify_token')
        assert 'access_token' == r.data.decode('utf8')
        assert '200 OK' == r.status

    # POST to facebook webhook
    with app.test_client() as c:
        data = {
            'object': 'page',
            'entry': [
                {
                    'messaging': [
                        {
                            'sender': {
                                'id': 'sender_id'
                            },
                            'recipient': {
                                'id': 'recipient_id'
                            },
                            'message': {
                                'text': 'message_text'
                            }
                        }
                    ]
                }
            ]
        }
        r = c.post('/facebook', headers={'Content-Type': 'application/json'},
                   data=json.dumps(data))
        assert '200 OK' == r.status


def test_facebook_unsupport(app):
    with app.test_client() as c:
        data = {
            "object": "page",
            "entry": [
                {
                    "id": "enteryid",
                    "time": 1488160039739,
                    "messaging": [
                        {
                            "sender": {
                                "id": "senderid"
                            },
                            "recipient": {
                                "id": "recipientid"
                            },
                            "timestamp": 1488160039657,
                            "message": {
                                "mid": "mid.1488160039657:1d4b8ac609",
                                "seq": 58863,
                                "attachments": [{
                                        "type": "image",
                                        "payload": {
                                            "url": "https://scontent.xx.fbcdn.net/v/t34.0-12/16997218_1543730039000857_2025028651_n.gif?_nc_ad=z-m&oh=f1a2953fb8c25dfd56661e62ffc72435&oe=58B5BCE2"  # NOQA
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        r = c.post('/facebook', headers={'Content-Type': 'application/json'},
                   data=json.dumps(data))
        assert '200 OK' == r.status
        data = r.data.decode('utf8')
        assert "Please enter text message" in data


def test_facebook_static():
    with fbbp.open_resource('static/style.css') as f:
        code = f.read()
        assert code


def test_facebook_start(app):
    with app.test_client() as c:
        data = {
            "object": "page",
            "entry": [
                {
                    "id": "100420220488340",
                    "time": 1488519518811,
                    "messaging": [
                        {
                            "recipient": {
                                "id": "100420220488340"
                            },
                            "timestamp": 1488519518811,
                            "sender": {
                                "id": "1522187434460061"
                            },
                            "postback": {
                                "payload": "START_BUTTON"
                            }
                        }
                    ]
                }
            ]
        }
        r = c.post('/facebook', headers={'Content-Type': 'application/json'},
                   data=json.dumps(data))
        assert '200 OK' == r.status
        data = r.data.decode('utf8')
        assert 'start button' in data


def do_login(c):
    # account link request payload
    data = {
        "object": "page",
        "entry": [
            {
                "id": "entryid",
                "time": 1488432412391,
                "messaging": [
                    {
                        "recipient": {
                            "id": "recipientid"
                        },
                        "timestamp": 1488432412391,
                        "sender": {
                            "id": "senderid"
                        },
                        "account_linking": {
                            "authorization_code": "34567",
                            "status": "linked"
                        }
                    }
                ]
            }
        ]
    }
    r = c.post('/facebook', headers={'Content-Type': 'application/json'},
               data=json.dumps(data))
    return r


def do_logout(c):
    # account unlink request payload
    data = {
        "object": "page",
        "entry": [
            {
                "id": "entryid",
                "time": 1488432412391,
                "messaging": [
                    {
                        "recipient": {
                            "id": "recipientid"
                        },
                        "timestamp": 1488432412391,
                        "sender": {
                            "id": "senderid"
                        },
                        "account_linking": {
                            "status": "unlinked"
                        }
                    }
                ]
            }
        ]
    }
    r = c.post('/facebook', headers={'Content-Type': 'application/json'},
               data=json.dumps(data))
    return r


def test_facebook_loginout(app):
    db.bind('sqlite', 'muorigin.sqlite', create_db=True)
    db.generate_mapping(create_tables=True)
    app.wsgi_app = orm.db_session(app.wsgi_app)

    with app.test_client() as c:
        r = do_login(c)
        assert '200 OK' == r.status
        data = r.data.decode('utf8')
        assert 'successfully logged in' in data

        r = do_login(c)
        assert '200 OK' == r.status
        data = r.data.decode('utf8')
        assert 'already logged in' in data

        r = do_logout(c)
        assert '200 OK' == r.status
        data = r.data.decode('utf8')
        assert 'successfully logged out' in data

        r = do_logout(c)
        assert '200 OK' == r.status
        data = r.data.decode('utf8')
        assert 'not logged in' in data


def test_facebook_template(app):
    from flask import render_template

    with app.app_context():
        data = render_template('facebook/account_link.json', image_url="image",
                               login_url='url')
        assert '"url": "url"' in data

        buttons = []
        for i in range(3):
            btn = {
                "type": "postback",
                "title": i,
                "payload": i
            }
        buttons.append(btn)

        data = render_template('facebook/buttons.json', text="test",
                               buttons=[('t1', 'p1'), ('t2', 'p2')])
        json.loads(data)
