#!/usr/bin/env python
"""
    Minimal backend for an mcash powered store with unlimited supplies.
    Our main persona is a friendly pizza shop at the corner.
"""
import functools
import json
import logging
import md5
import os
import random
import time
import urlparse
import uuid

import requests

import tornado.ioloop
import tornado.options
import tornado.web

JSON_CONTENT = 'application/vnd.api+json'
ORDER_EXPIRES_SEC = 600

shops = {}
transactions = {}

def memoize_singleton(func):
    cache = []

    @functools.wraps(func)
    def memoizer(*args, **kwargs):
        if cache:
            return cache[0]
        rtv = func(*args, **kwargs)
        if rtv is not None:
            cache.append(rtv)
        return rtv

    return memoizer

def memoize(func):
    cache = {}

    @functools.wraps(func)
    def memoizer(*args, **kwargs):
        key = '|'.join(map(str, args) + map(str, kwargs))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    return memoizer

@memoize_singleton
def mcash_headers():
    O = tornado.options.options
    headers = {}
    headers['X-Mcash-Merchant'] = O.mcash_merchant
    headers['X-Mcash-User'] = O.mcash_user
    headers['Authorization'] = O.mcash_secret
    headers['X-Testbed-Token'] = O.mcash_token
    return headers

@memoize_singleton
def base_url(request):
    base = urlparse.urlparse(tornado.options.options.mcash_callback_uri or request.full_url())
    return '%s://%s' % (base.scheme, base.netloc)

@memoize_singleton
def register_shortlink(request):
    O = tornado.options.options
    data = {'callback_uri': '%s/api/callback/shortlink/' % base_url(request)}
    if O.mcash_serial_number:
        data['serial_number'] = O.mcash_serial_number

    r = requests.post(O.mcash_endpoint + 'shortlink/', headers=mcash_headers(), data=data)
    if r.ok:
        shortlink_id = r.json()['id']
        logging.info('Shortlink generated: %s %s' % (data['callback_uri'], shortlink_id))
        return shortlink_id
    else:
        logging.error('Error creating a shortlink %s %s %s %s' % (r.status_code, r.url, r.headers, data), exc_info=True)

def generate_inventory(shopid):
    if shopid not in shops:
        selection = ['Roma', 'Milan', 'Bologna', 'Parma', 'Venice', 'Pomodoro',\
                    'Quattro Stagioni', 'Vegan', 'of %s' % shopid.capitalize()]
        shops[shopid] = {'pizzas': {}, 'toppings': {}, 'sizes': {}}

        for (pid, ingred) in enumerate(['garlic', 'extra cheese', 'pepperoni'], 1):
            shops[shopid]['toppings'][pid] = {'id': pid, 'name': ingred, 'price': random.randrange(2, 12)}

        for (pid, size) in enumerate([28, 32, 36], 0):
            shops[shopid]['sizes'][size] = {'id': size, 'name': '%s cm' % size, 'price': pid * 5}

        for (pid, pizza) in enumerate(random.sample(selection, random.randrange(4, len(selection))), 1):
            image = 'images/%s/%s.jpg' % (shopid, pizza.lower().replace(' ', '_'))
            shops[shopid]['pizzas'][pid] = {'id': pid, 'name': 'Pizza %s' % pizza,\
                                            'image': image, 'price': random.randrange(35, 55)}

@memoize
def get_shop_selection(shopid, category, pid=None):
    if shopid not in shops:
        generate_inventory(shopid)

    content = shops[shopid][category]
    # ember-data requires {'pizza': {'id': ...}} or {'pizza': [{'id': 1, ..}, ...]}
    return json.dumps({category[:-1]: content[pid] if pid is not None and pid in content else content.values()})

class MessageBuffer(object):
    def __init__(self):
        self.waiters = {}
        self.cache = []
        self.cache_size = 200

    def register_callback(self, unique_order, callback):
        if unique_order not in self.waiters:
            self.waiters[unique_order] = set([callback])
        else:
            self.waiters[unique_order].add(callback)

    def cancel_wait(self, unique_order, callback):
        if unique_order in self.waiters:
            self.waiters[unique_order].remove(callback)
            if not self.waiters[unique_order]:
                del self.waiters[unique_order]

    def payment_arrived(self, unique_order):
        if unique_order in self.waiters:
            for cb in self.waiters[unique_order]:
                try:
                    cb()
                except Exception:
                    logging.error('Error in waiter callback', exc_info=True)
            del self.waiters[unique_order]

global_message_buffer = MessageBuffer()

class PollHandler(tornado.web.RequestHandler):
    def __init__(self, *args, **kwargs):
        self.unique_order = None
        super(PollHandler, self).__init__(*args, **kwargs)

    def get(self, unique_order):
        raise tornado.web.HTTPError(405)

    @tornado.web.asynchronous
    def post(self, unique_order):
        if unique_order not in transactions:
            logging.info('Unknown unique_order polled')
            raise tornado.web.HTTPError(404)
        self.unique_order = unique_order
        if transactions[unique_order]['status'] > 2:
            self.callback()
        else:
            global_message_buffer.register_callback(unique_order, self.callback)

    def callback(self):
        # client connection is still open
        logging.info('Poll callback for %s' % self.unique_order)
        if not self.request.connection.stream.closed():
            result = {'result': transactions[self.unique_order]['status'] == 4}
            self.finish(json.dumps(result))

    def on_connection_close(self):
        if hasattr(self, 'unique_order'):
            global_message_buffer.cancel_wait(self.unique_order, self.callback)

class PaymentHandler(tornado.web.RequestHandler):
    def post(self, unique_order):
        logging.info('Payment callback arrived: %s' % self.request.body)
        try:
            body = json.loads(self.request.body)
        except ValueError as error:
            logging.error('Unexpected JSON in callback %s %s' % (error, self.request.body))
            raise tornado.web.HTTPError(400)

        if 'object' in body:
            transaction_id = body['object']['tid']
            status = body['object']['status']

            if unique_order in transactions:
                if status != 'fail':
                    uri = '%spayment_request/%s/' % (tornado.options.options.mcash_endpoint, transaction_id)
                    response = requests.put(uri, data={'action': 'capture'}, headers=mcash_headers())
                    if not response.ok:
                        # TODO check if the error is recoverable
                        logging.error('payment capture failed: %s %s %s %s' % (response.status_code, response.content, unique_order, transaction_id))
                        raise tornado.web.HTTPError(500)
                    transactions[unique_order]['status'] = 4
                    logging.info('payment capture succeded: %s %s' % (unique_order, transaction_id))
                else:
                    transactions[unique_order]['status'] = 3
                    logging.info('payment rejected %s %s' % (unique_order, transaction_id))
                global_message_buffer.payment_arrived(unique_order)
                self.clear_cookie('uuid')
        else:
            logging.info('Event %s %s' % (body['event'], body['id']))
        self.write('OK')

class ShortlinkHandler(tornado.web.RequestHandler):
    def post(self):
        logging.info('Shortlink callback arrived: %s' % self.request.body)
        try:
            customer = json.loads(self.request.body)['object']['id']
            unique_order = json.loads(self.request.body)['object']['argstring']
        except ValueError:
            logging.error('Unexpected JSON in callback %s' % self.request.body)
            raise tornado.web.HTTPError(400)

        if unique_order in transactions:
            amount = transactions[unique_order]['amount']
            O = tornado.options.options
            data = {}
            data['amount'] = amount
            data['currency'] = O.mcash_currency
            data['callback_uri'] = '%s/api/callback/payment/%s/' % (base_url(self.request), unique_order)
            data['allow_credit'] = O.allow_credit
            data['customer'] = customer
            data['pos_id'] = transactions[unique_order]['shopid']
            data['pos_tid'] = unique_order
            data['action'] = 'auth'
            data['text'] = transactions[unique_order]['shopid']

            uri = '%spayment_request/' % O.mcash_endpoint
            response = requests.post(uri, headers=mcash_headers(), data=data)
            if not response.ok:
                logging.error('payment authorization request failed: %s %s %s %s %s' % (response.status_code, response.content, response.url, mcash_headers(), data))
                raise tornado.web.HTTPError(500)
            transaction_id = response.json()['id']
            transactions[unique_order]['transaction_id'] = transaction_id
            transactions[unique_order]['status'] = 1
            logging.info('payment authorization request succeded: %s %s %s' % (unique_order, transaction_id, data['callback_uri']))
        self.write('OK')

class ProductHandler(tornado.web.RequestHandler):
    def get(self, shopid, category, pid=None):
        self.set_header('Content-Type', JSON_CONTENT)
        self.write(get_shop_selection(shopid, category, pid))

    def post(self, shopid, category):
        if shopid not in shops:
            raise tornado.web.HTTPError(404)
        self.set_header('Content-Type', JSON_CONTENT)
        order = None
        try:
            amount = self._validate_content(shopid)
            if amount > 0:
                shortlink_id = register_shortlink(self.request)
                order = self._generate_order(shopid, shortlink_id, amount)
        except ValueError:
            logging.error('Error in shortlink generation', exc_info=True)

        if not order:
            raise tornado.web.HTTPError(400)

        self.write(order)

    def _validate_content(self, shopid):
        content = json.loads(self.request.body)
        try:
            inventory = shops[shopid]
            toppings = dict([(x['id'], x) for x in inventory['toppings']])

            if not isinstance(content, list):
                return -1
            amount = 0
            for piece in content:
                if not isinstance(piece, dict):
                    return -1
                if piece['id'] not in inventory['pizzas']:
                    logging.info('Invalid pizza id: %s %s' % (piece['id'], shopid))
                    return -1
                if 'size' in piece:
                    if piece['size'] in inventory['sizes']:
                        amount += inventory['sizes'][piece['size']]['price']
                    else:
                        logging.info('Invalid size: %s %s' % (piece['size'], shopid))
                if 'toppings' in piece:
                    for t in piece['toppings']:
                        if t in inventory['toppings']:
                            amount += inventory['toppings'][t['id']]['price']
                        else:
                            logging.info('Invalid topping: %s %s' % (t, shopid))
            return amount
        except Exception:
            logging.error('Error in content validation', exc_info=True)
            return -1

    def _generate_order(self, shopid, shortlink_id, amount):
        now = int(time.time())
        user = self.get_cookie('uuid', None)
        if not user:        # set token only when needed
            user = str(uuid.uuid1())
            self.set_cookie('uuid', user, expires=now + 30)
        h = md5.new(user)
        h.update(shopid)
        h.update(self.request.body)
        unique_order = h.hexdigest()

        logging.info('User uuid for order: %s %s' % (unique_order, user))

        payment_cookie = self.get_cookie(unique_order, '')
        if not payment_cookie:
            transactions[unique_order] = {'shopid': shopid, 'amount': amount, 'issued': now, 'user': user, 'status': 1}
            self.set_cookie(unique_order, str(now), expires=now + ORDER_EXPIRES_SEC)

        order = {'id': unique_order, \
                'amount': amount, \
                'poll_uri': '%s/api/poll/%s/' % (base_url(self.request), unique_order), \
                'qrcode_url': tornado.options.options.mcash_qrcode % (shortlink_id, unique_order)}
        return json.dumps(order)

    def _check_header(self, key, value=None):
        return key in self.request.headers and self.request.headers.get(key).lower() == (value or JSON_CONTENT).lower()

class NCStaticFileHandler(tornado.web.StaticFileHandler):
    def set_extra_headers(self, path):
        # Disable cache
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')

def describe_config():
    tornado.options.define('cookie_secret', default='sssecccc', help='Change this to a real secret')
    tornado.options.define('favicon', default='static/favicon.ico', help='Path to favicon.ico')
    tornado.options.define('static_path', default='static/', help='Path static items')
    tornado.options.define('port', default=8888, help='Port to run webservice')
    tornado.options.define('config', default='server.conf', help='Config file location')
    tornado.options.define('mcash_callback_uri', default=None, help='Callback URI for mcash')
    tornado.options.define('mcash_endpoint', default='https://mcashtestbed.appspot.com/merchant/v1/', help='API to call')
    # probably better to set in at once like mcash headers as a string
    tornado.options.define('mcash_merchant', help='X-Mcash-Merchant')
    tornado.options.define('mcash_user', help='X-Mcash-User')
    tornado.options.define('mcash_secret', help='Authorization header')
    tornado.options.define('mcash_token', help='X-Testbed-Token')
    tornado.options.define('mcash_serial_number', help='Optional serial number for shortlink generation')
    tornado.options.define('mcash_qrcode', default='https://api.mca.sh/shortlink/v1/qr_image/%s/%s', help='Should have %s marks for shortlink id and argument')
    tornado.options.define('mcash_currency', default='NOK', help='Currency for transactions')
    tornado.options.define('allow_credit', default=False, help='Credit allowed for payment request')

def main():
    describe_config()
    tornado.options.parse_command_line()
    options = tornado.options.options
    if os.path.exists(options.config):
        tornado.options.parse_config_file(options.config)

    settings = {
        'static_path': os.path.join(os.path.dirname(__file__), '..', options.static_path),
        'cookie_secret': options.cookie_secret,
        'login_url': '/login',
        'xsrf_cookies': False,
        'autoreload': True
    }
    handlers = [
        (r'/api/products/([^/]+)/(pizzas|sizes|toppings)/?', ProductHandler),
        (r'/api/products/([^/]+)/(pizzas|sizes|toppings)/(\w+)/?', ProductHandler),
        (r'/api/poll/([^/]{16,32})/', PollHandler),
        (r'/api/callback/shortlink/', ShortlinkHandler),
        (r'/api/callback/payment/([^/]{16,32})/', PaymentHandler),
        (r'/(.*)', NCStaticFileHandler, {'path': settings['static_path']})
    ]
    application = tornado.web.Application(handlers, **settings)
    application.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()
