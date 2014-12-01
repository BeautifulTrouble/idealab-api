#!/usr/bin/env python2

# Quality imports                                                             
# ////////////////////////////////////////////////////////////////////////////
import datetime
import hashlib
import re
import sys
import time
from flask import Flask
from flask import g, jsonify, redirect, request, session, url_for
from flask.ext.login import LoginManager, AnonymousUserMixin, UserMixin
from flask.ext.login import current_user, login_required, login_user, logout_user
from flask.ext.sqlalchemy import SQLAlchemy
from flask_oauthlib.client import OAuth, OAuthException
from werkzeug.contrib.cache import SimpleCache
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
    OAUTH_REDIRECT,
)


# Utilities                                                                   
# ////////////////////////////////////////////////////////////////////////////
def get_next_url():
    return request.args.get('next') or OAUTH_REDIRECT

def oauth_redirect():
    return redirect(session.get('oauth_redirect') or get_next_url())

def sha1(s):
    return hashlib.sha1(s.encode('utf8')).hexdigest()

def public_name(obj):
    if not obj.name and obj.contact.startswith('@'):
        return obj.contact
        # Anonymous people here ~~---v
    return obj.name

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
app = application = Flask(__name__)
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


# Caches
# ////////////////////////////////////////////////////////////////////////////
vote_cache = SimpleCache()


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
    #TODO: Look at the content-type of the request and be smart about
    #      returning a redirect or a status code + json
    return status(401)

@login_manager.user_loader
def user_loader(id):
    return User.query.get(id)

# Patch anonymous user object so we can perform basic
# checks without ensuring a user is logged in
AnonymousUserMixin.admin = False
AnonymousUserMixin.id = -1


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
            setattr(self, column_name, dct[column_name].strip()[:length])
        self.is_valid = True

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    local_id = db.Column(db.Unicode(40))
    provider = db.Column(db.Unicode(50))
    provider_id = db.Column(db.Unicode(50))
    name = db.Column(db.Unicode(500))
    contact = db.Column(db.Unicode(500))
    admin = db.Column(db.Boolean, default=False)

    def __init__(self, local_id, provider, provider_id, name, contact):
        [setattr(self, k, v) for k,v in locals().items() if k != 'self']

    @property
    def serialized(self):
        return {
            'name': public_name(self),
            'contact': self.contact,
            'provider': self.provider,
            'admin': self.admin,
        }

class Idea(ValidMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.relationship('User', backref=db.backref('ideas', lazy='dynamic'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    published = db.Column(db.Boolean, default=False)

    title = db.Column(db.Unicode(500))
    short_write_up = db.Column(db.Unicode(5000))
    name = db.Column(db.Unicode(500))
    contact = db.Column(db.Unicode(500))

    initialize = 'title', 'short_write_up', 'name', 'contact'

    @property
    def serialized(self):
        return {
            'id': self.id,
            'user_id': self.user.id,
            'contributors': [public_name(self)],
            
            'date': int(self.date.strftime('%s')) * 1000,
            'short_date': '{d.month}.{d.day}.{d.year}'.format(d=self.date),
            'long_date': '{} {d.day}, {d.year}'.format(self.date.strftime('%B'), d=self.date),

            'slug': re.sub(r'\W+', '-', self.title.lower(), flags=re.U).strip('-'),
            'published': self.published,
            'votes': IdeaVote.cache().get(self.id, 0),
            'loved': bool(IdeaVote.query.get((current_user.id, self.id))),

            'title': self.title,
            'short_write_up': self.short_write_up,
            'name': self.name,
            'contact': self.contact,
        }

class IdeaVote(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    idea_id = db.Column(db.Integer, db.ForeignKey('idea.id'), primary_key=True)

    def __init__(self, user_id, idea_id):
        self.user_id = user_id
        self.idea_id = idea_id

    @staticmethod
    def cache(update_id=None):
        counts = vote_cache.get('ideas')
        if counts is None:
            counts = {obj.id: IdeaVote.query.filter(IdeaVote.idea_id==obj.id).count()
                     for obj in Idea.query.all()}
            vote_cache.set('ideas', counts, timeout=60 * 5)
        elif update_id is not None:
            counts[update_id] = IdeaVote.query.filter(IdeaVote.idea_id==update_id).count()
            vote_cache.set('ideas', counts, timeout=60 * 5)
        return counts

class Improvement(ValidMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.relationship('User', backref=db.backref('improvements', lazy='dynamic'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    published = db.Column(db.Boolean, default=False)

    module = db.Column(db.Unicode(500))
    link = db.Column(db.Unicode(5000))
    type = db.Column(db.Unicode(50))
    content = db.Column(db.Unicode(5000))
    contact = db.Column(db.Unicode(500))

    initialize = 'module', 'link', 'type', 'content', 'contact'

    @property
    def serialized(self):
        return {
            'id': self.id,
            'user_id': self.user.id,
            'published': self.published,

            'module': self.module,
            'link': self.link,
            'type': self.type,
            'content': self.content,
            'contact': self.contact,
        }

db.create_all()


# OAuth Views                                                                       
# ////////////////////////////////////////////////////////////////////////////
@app.route('/logout')
def logout():
    if current_user.is_authenticated():
        logout_user()
    return oauth_redirect()

@app.route('/login/<provider>')
def login(provider):
    session['oauth_redirect'] = get_next_url()
    if current_user.is_authenticated():
        return oauth_redirect()
    p = oauth_providers.get(provider)
    if not p:
        # The provider doesn't exist
        return oauth_redirect()
    callback_url = url_for('authorize', provider=provider, _external=True)
    return p.authorize(callback=callback_url)

# OAuth providers may require you to register this callback url
@app.route('/login/<provider>/authorize')
def authorize(provider):
    p = oauth_providers.get(provider)
    if not p:
        # The provider doesn't exist
        return oauth_redirect()
    resp = p.authorized_response()
    if resp is None or isinstance(resp, OAuthException):
        # Authorization denied
        return oauth_redirect()
    session['oauth'] = resp
    # Retrieve id as well as name and email if possible
    provider_id, name, contact = p.user_info()
    # Generate a unique id from the provider's user id
    local_id = sha1(provider_id + provider)
    # Look up the user or create a new one and log them in
    user = User.query.filter(User.local_id==local_id).first()
    if not user:
        user = User(local_id, provider, provider_id, name, contact)
        db.session.add(user)
        db.session.commit()
    elif not user.provider_id:
        # Post-launch schema changes left this empty for early users
        user.provider_id = provider_id
        db.session.add(user)
        db.session.commit()
    login_user(user, remember=True)
    return oauth_redirect()


# /ideas 
# /////////////////////////////////////////////////////////
@app.route('/ideas', methods=['GET'])
@app.route('/ideas/<int:id>', methods=['GET'])
def get_ideas(id=None):
    clause = "(published = '1' OR user_id = '%s')" % current_user.id
    if current_user.admin:
        clause = ''
    return get_objects(Idea, id, where=clause)

@app.route('/ideas', methods=['POST'])
def post_idea():
    return post_object(Idea)

@app.route('/ideas/<int:id>', methods=['PUT', 'DELETE'])
def update_idea(id):
    return update_object(Idea, id)


# /improvements 
# /////////////////////////////////////////////////////////
@app.route('/improvements', methods=['GET'])
@app.route('/improvements/<int:id>', methods=['GET'])
def get_improvements(id=None):
    clause = "(user_id = '%s')" % current_user.id
    if current_user.admin:
        clause = ''
    return get_objects(Improvement, id, where=clause)

@app.route('/improvements', methods=['POST'])
def post_improvement():
    return post_object(Improvement)

@app.route('/improvements/<int:id>', methods=['PUT', 'DELETE'])
def update_improvement(id):
    return update_object(Improvement, id)


# /me
# /////////////////////////////////////////////////////////
@app.route('/me', methods=['GET'])
@login_required
def get_me():
    return status(200, data=current_user.serialized)


# /love
# /////////////////////////////////////////////////////////
@app.route('/love/idea/<int:idea_id>', methods=['PUT'])
@login_required
def toggle_love(idea_id):
    #TODO: Simplify these queries
    vote = IdeaVote.query.get((current_user.id, idea_id))
    if vote:
        db.session.delete(vote)
        db.session.commit()
        IdeaVote.cache(idea_id)
    elif Idea.query.get(idea_id):
        idea = IdeaVote(current_user.id, idea_id)
        db.session.add(idea)
        db.session.commit()
        IdeaVote.cache(idea_id)
    else:
        return status(404)
    return status(200)


# Generic RESTfulness
# /////////////////////////////////////////////////////////
def get_objects(Model, id=None, where=''):
    '''
    GET the collection or single objects
    '''
    if id:
        obj = Model.query.filter(Model.id==id, where).first()
        if not obj:
            return status(404)
        return status(200, data=obj.serialized)
    objs = Model.query.filter(where).all()
    return status(200, data=[obj.serialized for obj in objs])

def post_object(Model):
    '''
    The user-writable object is POSTed here
    '''
    if not current_user.is_authenticated():
        return unauthorized_handler()

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
    if not current_user.is_authenticated():
        return unauthorized_handler()

    obj = Model.query.get(id)
    if not obj:
        return status(404)
    if obj.user != current_user and not current_user.admin:
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

