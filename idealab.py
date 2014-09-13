#!/usr/bin/env python
# XXX: Target is python3.x, will this be viable? Test 2.7 extensively.

# Quality imports                                                             
# ////////////////////////////////////////////////////////////////////////////
import datetime
import hashlib
import re
import sys
from flask import Flask
from flask import jsonify, redirect, request, session, url_for
from flask.ext.login import LoginManager, UserMixin
from flask.ext.login import current_user, login_required, login_user, logout_user
from flask.ext.sqlalchemy import SQLAlchemy
from flask_oauthlib.client import OAuth, OAuthException
from config import (
    APPLICATION_ROOT,
    SECRET_KEY,
    SQLALCHEMY_DATABASE_URI,
    FACEBOOK_APP_ID,
    FACEBOOK_APP_SECRET,
    GOOGLE_ID,
    GOOGLE_SECRET,
    TWITTER_CONSUMER_KEY,
    TWITTER_CONSUMER_SECRET,
)


# Utilities                                                                   
# ////////////////////////////////////////////////////////////////////////////
def get_next_url(fallback_route=None):
    next_url = request.args.get('next')
    fallback = url_for(fallback_route) if fallback_route else '/#idealab'   #XXX: config var
    return next_url or fallback

def sha1(s):
    return hashlib.sha1(s.encode('utf8')).hexdigest()

# JSON responses to accompany HTTP status codes
def status(n, **kw):
    kw['message'] = kw.get('message') or {
        200: "Everything is OK",
        201: "Object created",
        400: "Bad request",
        401: "User not authorized",
        403: "Verboten",
        404: "No such thing",
        409: "Object exists",
        418: "I'm a teapot",
        420: "Enhance your calm",
        500: "Server error",
    }.get(n, '')
    kw['status'] = n
    kw['success'] = str(n)[:1] not in '45'
    return jsonify(**kw), n


# Flask initialization                                                        
# ////////////////////////////////////////////////////////////////////////////
app = Flask(__name__)
app.config['DEBUG']                     = 'debug' in sys.argv
app.config['APPLICATION_ROOT']          = APPLICATION_ROOT
app.config['SECRET_KEY']                = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI']   = SQLALCHEMY_DATABASE_URI
app.config['SESSION_PROTECTION']        = 'strong'

# Prepend APPLICATION_ROOT to all routes by monkey-patching the route decorator
app._route, app.route = app.route, lambda *a, **kw: app._route(
    APPLICATION_ROOT + '/' + a[0].lstrip('/'), *a[1:], **kw)

@app.errorhandler(404)
def four_oh_four(error):
    return status(404, message="You've reached an unknown corner of this universe")

# OAuth providers                                                             
# ////////////////////////////////////////////////////////////////////////////
oauth = OAuth()
oauth_providers = {}

if FACEBOOK_APP_ID and FACEBOOK_APP_SECRET:
    oauth_providers['facebook'] = facebook = oauth.remote_app('facebook',
        access_token_url    = '/oauth/access_token',
        authorize_url       = 'https://www.facebook.com/dialog/oauth',
        base_url            = 'https://graph.facebook.com',
        consumer_key        = FACEBOOK_APP_ID,
        consumer_secret     = FACEBOOK_APP_SECRET,
        request_token_url   = None,
        request_token_params= {'scope': 'email'},
    )
    facebook.user_info = lambda: map(facebook.get('me').data.get, ['id', 'name', 'email'])

if GOOGLE_ID and GOOGLE_SECRET:
    oauth_providers['google'] = google = oauth.remote_app('google',
        access_token_method = 'POST',
        access_token_url    = 'https://accounts.google.com/o/oauth2/token',
        authorize_url       = 'https://accounts.google.com/o/oauth2/auth',
        base_url            = 'https://www.googleapis.com/oauth2/v1/',
        consumer_key        = GOOGLE_ID,
        consumer_secret     = GOOGLE_SECRET,
        request_token_url   = None,
        request_token_params= {'scope': 'https://www.googleapis.com/auth/userinfo.email'},
    )
    google.user_info = lambda: map(google.get('userinfo').data.get, ['id', 'name', 'email'])

if TWITTER_CONSUMER_KEY and TWITTER_CONSUMER_SECRET:
    oauth_providers['twitter'] = twitter = oauth.remote_app('twitter',
        access_token_url    = 'https://api.twitter.com/oauth/access_token',
        authorize_url       = 'https://api.twitter.com/oauth/authenticate',
        base_url            = 'https://api.twitter.com/1.1/',
        consumer_key        = TWITTER_CONSUMER_KEY,
        consumer_secret     = TWITTER_CONSUMER_SECRET,
        request_token_url   = 'https://api.twitter.com/oauth/request_token',
    )
    twitter.user_info = lambda: (session['oauth']['user_id'], '', '@' + session['oauth']['screen_name'])

for provider in oauth_providers.values():
    setattr(provider, '_tokengetter', lambda: session.get('oauth'))


# Login Manager                                                               
# ////////////////////////////////////////////////////////////////////////////
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.unauthorized_handler
def unauthorized_handler():
    return status(401)

@login_manager.user_loader
def user_loader(user_id):
    return User.query.get(user_id)


# Models                                                                      
# ////////////////////////////////////////////////////////////////////////////
db = SQLAlchemy(app)

class ValidMixin(object):
    '''
    This model mixin provides an __init__ method which aids in the creation
    of new records. When an object representing a database row is created,
    its "user" relationship is set to current_user, and all columns whose
    names are in the model's "initialize" attribute (a sequence of strings)
    are set from incoming user data. If any data was missing, the object's
    is_valid attribute will be set to False.
    '''
    is_valid = False
    initialize = ()

    def __init__(self, dct):
        self.user = current_user
        self.update(dct)

    def update(self, dct):
        for column_name in self.initialize:
            if column_name not in dct:
                self.is_valid = False
                return
            length = getattr(self.__class__, column_name).type.length
            setattr(self, column_name, dct[column_name][:length])
        self.is_valid = True

class User(UserMixin, db.Model):
    id = db.Column(db.Unicode(40), primary_key=True)
    name = db.Column(db.Unicode(500))
    contact = db.Column(db.Unicode(500))
    provider = db.Column(db.Unicode(50))

    def __init__(self, id, name, contact, provider):
        [setattr(self, k, v) for k,v in locals().items() if k != 'self']

    @property
    def public_name(self):
        if not self.name:
            if self.provider == 'twitter' and self.contact[:1] == '@':
                return self.contact
            # Anonymous people here ~~---v 
        return self.name

    def update_from_request(self):
        if current_user.is_authenticated():
            j = request.json
            if 'name' in j or 'contact' in j:
                if 'name' in j:
                    current_user.name = j['name']
                if 'contact' in j:
                    current_user.contact = j['contact']
                db.session.add(current_user)
                db.session.commit()

class Idea(ValidMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.relationship('User', backref=db.backref('ideas', lazy='dynamic'))
    user_id = db.Column(db.Unicode, db.ForeignKey('user.id'))
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    title = db.Column(db.Unicode(500))
    short_write_up = db.Column(db.Unicode(5000))
    published = db.Column(db.Boolean, default=False)

    initialize = 'title', 'short_write_up'

    @property
    def serialized(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'contributors': [self.user.public_name],
            # Don't bother doing dates in js... they're awkward enough in python
            'short_date': '{d.month}.{d.day}.{d.year}'.format(d=self.date),
            'long_date': '{} {d.day}, {d.year}'.format(self.date.strftime('%B'), d=self.date),
            'title': self.title,
            'slug': re.sub(r'\W+', '-', self.title.lower()),
            'short_write_up': self.short_write_up,
        }

class Improvement(ValidMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.relationship('User', backref=db.backref('improvements', lazy='dynamic'))
    user_id = db.Column(db.Unicode, db.ForeignKey('user.id'))
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # Don't overcomplicate this database with foreign keys
    module = db.Column(db.Unicode(500))
    link = db.Column(db.Unicode(5000))
    type = db.Column(db.Unicode(50))
    content = db.Column(db.Unicode(5000))

    initialize = 'module', 'link', 'type', 'content'

    @property
    def serialized(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'module': self.module,
            'link': self.link,
            'type': self.type,
            'content': self.content,
        }

db.create_all()


# OAuth Views                                                                       
# ////////////////////////////////////////////////////////////////////////////
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return status(200, message="Goodbye")

@app.route('/login/<provider>')
def login(provider):
    if current_user.is_authenticated():
        return status(200, message="User already logged in with " + current_user.provider)
    p = oauth_providers.get(provider)
    if not p:
        # The provider doesn't exist
        return status(500, message="I don't know how to authenticate with " + provider)
    # XXX: The "next" here needn't be here. Google don't need it nor do it like it.
    callback_url = url_for('authorize', provider=provider, next=request.args.get('next'), _external=True)
    return p.authorize(callback=callback_url) # or request.referrer or None)

# OAuth providers may require you to register this callback url
@app.route('/login/<provider>/authorize')
def authorize(provider):
    p = oauth_providers.get(provider)
    if not p:
        # The provider doesn't exist
        return status(500, message="I don't know how to authenticate with " + provider)
    resp = p.authorized_response()
    if resp is None or isinstance(resp, OAuthException):
        # Authorization denied
        return status(401)
    session['oauth'] = resp
    # Retrieve id as well as name and email if possible
    user_id, name, contact = p.user_info()
    # Generate a unique id from the provider's user id
    user_id = sha1(user_id + p.name)
    # Look up the user or create a new one and log them in
    user = User.query.get(user_id)
    if not user:
        user = User(user_id, name, contact, provider)
        db.session.add(user)
        db.session.commit()
    login_user(user, remember=True)
    return status(200)


# /ideas 
# /////////////////////////////////////////////////////////
@app.route('/ideas', methods=['GET'])
@app.route('/ideas/<int:id>', methods=['GET'])
def get_ideas(id=None):
    return get_objects(Idea, id)

@app.route('/ideas', methods=['POST'])
@login_required
def post_idea():
    return post_object(Idea)

@app.route('/ideas/<int:id>', methods=['PUT', 'DELETE'])
@login_required
def update_idea(id):
    return update_object(Idea, id)


# /improvements 
# /////////////////////////////////////////////////////////
@app.route('/improvements', methods=['GET'])
@app.route('/improvements/<int:id>', methods=['GET'])
def get_improvements(id=None):
    return get_objects(Improvement, id)

@app.route('/improvements', methods=['POST'])
@login_required
def post_improvement():
    return post_object(Improvement)

@app.route('/improvements/<int:id>', methods=['PUT', 'DELETE'])
@login_required
def update_improvement(id):
    return update_object(Improvement, id)


# Generic RESTfulness
# /////////////////////////////////////////////////////////
def get_objects(Model, id=None):
    '''
    GET the collection or single objects
    '''
    if id:
        obj = Model.query.get(id)
        if not obj:
            return status(404)
        return status(200, data=obj.serialized)
    return status(200, data=[obj.serialized for obj in Model.query.all()])


def post_object(Model):
    '''
    The user-writable object is POSTed here
    '''
    # We'll accept name and contact from any source
    current_user.update_from_request()

    obj = Model(request.json)
    if obj.is_valid:
        db.session.add(obj)
        db.session.commit()
        return status(201)
    return status(400)

def update_object(Model, id):
    '''
    The user-writable object is uPUTdated or DELETEed here
    '''
    # We'll accept name and contact from any source
    current_user.update_from_request()

    obj = Model.query.get(id)
    if not obj:
        return status(404)
    if obj.user != current_user:
        return status(401)
    if request.method == 'PUT':
        obj.update(request.json)
        if obj.is_valid:
            db.session.add(obj)
            db.session.commit()
            return status(201)
    elif request.method == 'DELETE':
        db.session.delete(obj)
        db.session.commit()
        return status(200)
    return status(500)


# Run local server when executed as a script                                                                 
# ////////////////////////////////////////////////////////////////////////////
if __name__ == '__main__':
    app.run(port=9000)

