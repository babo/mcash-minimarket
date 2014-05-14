#!/usr/bin/env python
"""
    Minimal backend for an mcash powered store with unlimited supplies.
    Our main persona is a friendly pizza shop at the corner.
"""
import functools
import os
import json
import uuid
import time
import md5
import urlparse
import logging

import requests

import tornado.ioloop
import tornado.web
import tornado.options

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
    data = {'callback_uri': '%s/api/callback/shortlink' % base_url(request)}
    if O.mcash_serial_number:
        data['serial_number'] = O.mcash_serial_number

    r = requests.post(O.mcash_endpoint + 'shortlink/', headers=mcash_headers(), data=data)
    if r.ok:
        shortlink_id = r.json()['id']
        logging.info('Shortlink generated: %s' % shortlink_id)
        return shortlink_id
    else:
        logging.error('Error creating a shortlink', exc_info=True)

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

    def payment_arrived(self, order_id):
        if order_id in self.waiters:
            for cb in self.waiters[order_id]:
                try:
                    cb()
                except Exception:
                    logging.error('Error in waiter callback', exc_info=True)
            del self.waiters[order_id]

global_message_buffer = MessageBuffer()

class PollHandler(tornado.web.RequestHandler):
    def __init__(self, *args, **kwargs):
        self.unique_order = None
        super(PollHandler, self).__init__(*args, **kwargs)

    @tornado.web.asynchronous
    def post(self, unique_order):
        self.unique_order = unique_order
        global_message_buffer.register_callback(unique_order, self.callback)

    def callback(self, result):
        # client connection is still open
        if not self.request.connection.stream.closed():
            self.finish(result)

    def on_connection_close(self):
        if hasattr(self, 'unique_order'):
            global_message_buffer.cancel_wait(self.unique_order, self.callback)

class CallbackHandler(tornado.web.RequestHandler):
    def post(self, from_mcash, unique_order):
        logging.info('Callback arrived: %s %s' % (from_mcash, unique_order))
        if unique_order in transactions:
            if from_mcash == 'shortlink':
                amount = transactions[unique_order]['amount']
                O = tornado.options.options
                data = {}
                data['amount'] = amount
                data['currency'] = O.mcash_currency
                data['callback_uri'] = '%sapi/callback/payment/%s' % (base_url(self.request), unique_order)
                data['allow_credit'] = O.allow_credit
                data['customer'] = transactions[unique_order]['user']
                data['pos_id'] = transactions[unique_order]['shopid']
                data['pos_tid'] = unique_order
                data['action'] = 'auth'
                data['text'] = transactions[unique_order]['shopid']

                uri = '%spayment_request/' % O.mcash_endpoint
                r1 = requests.post(uri, headers=mcash_headers(), data=data)
                if r1.ok:
                    transaction_id = r1.json()['id']
                    transactions[unique_order]['transaction_id'] = transaction_id
                    transactions[unique_order]['status'] = 1
                    logging.info('payment request succeded: %s %s' % (unique_order, transaction_id))

                    r2 = requests.put('%s%s/' % transaction_id, data={'action': 'capture'}, headers=mcash_headers())
                    if r2.ok:
                        transactions[unique_order]['status'] = 4
                        logging.info('payment capture succeded: %s %s' % (unique_order, transaction_id))
                        global_message_buffer.payment_arrived(transaction_id)
                        self.write('OK')
                    else:
                        transactions[unique_order]['status'] = 3
                        logging.error('payment capture failed: %s %s %s %s' % (r2.status_code, r2.reason, unique_order, transaction_id))
                        raise tornado.web.HTTPError(500)
                else:
                    logging.error('payment request failed: %s %s %s' % (r1.status_code, r1.reason, data))
                    raise tornado.web.HTTPError(500)
            elif from_mcash == 'status':
                logging.info('Payment status %s %s %s' % (from_mcash, unique_order, self.request.body))
                self.write('OK')
            else:
                logging.error('Unkown callback %s %s' % (from_mcash, unique_order))
                raise tornado.web.HTTPError(404)

class ProductHandler(tornado.web.RequestHandler):
    def get(self, shopid):
        if shopid not in shops:
            inventory = {'pizzas':
                    [   {'id': 1, 'name': 'Pizza lagano', 'price': 45},
                        {'id': 2, 'name': 'Pizza vegan', 'price': 50},
                        {'id': 3, 'name': 'Pizza of the house', 'price': 55},
                    ],
                    'toppings': [
                        {'id': 1, 'name': 'garlic', 'price': 1},
                        {'id': 2, 'name': 'extra cheese', 'price': 5},
                        {'id': 3, 'name': 'pepperoni', 'price': 2}
                     ],
                    'sizes': [
                        {'id': 28, 'name': '28 cm', 'price': -5},
                        {'id': 32, 'name': '32 cm', 'price': 0},
                        {'id': 36, 'name': '36 cm', 'price': 5}
                    ]
                }
            shops[shopid] = json.dumps(inventory)
        self.set_header('Content-Type', JSON_CONTENT)
        if not self.get_cookie('uuid'):
            self.set_cookie('uuid', str(uuid.uuid1()))
        self.write(shops[shopid])

    def post(self, shopid):
        if shopid not in shops:
            raise tornado.web.HTTPError(404)
        if self._check_header('Content-Type') and self._check_header('Accept'):
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
        else:
            logging.info('POST with invalid content')
            raise tornado.web.HTTPError(406)

    def _validate_content(self, shopid):
        content = json.loads(self.request.body)
        try:
            inventory = json.loads(shops[shopid])
            pizzas = dict([(x['id'], x) for x in inventory['pizzas']])
            sizes = dict([(x['id'], x) for x in inventory['sizes']])
            toppings = dict([(x['id'], x) for x in inventory['toppings']])

            if not isinstance(content, list):
                return -1
            amount = 0
            for piece in content:
                if not isinstance(piece, dict):
                    return -1
                if piece['id'] not in pizzas or piece['size'] not in sizes:
                    return -1
                amount += pizzas[piece['id']]['price']
                amount += sizes[piece['size']]['price']
                if 'toppings' in piece:
                    for t in piece['toppings']:
                        amount += toppings[t['id']]['price']
            return amount
        except Exception:
            logging.error('Error in content validation', exc_info=True)
            return -1

    def _generate_order(self, shopid, shortlink_id, amount):
        user = self.get_cookie('uuid', None)
        if user is None:        # set token only when needed
            user = str(uuid.uuid1())
            self.set_cookie('uuid', user)
        unique_order = md5.new(user).update(shopid).update(self.request.body).hexdigest()

        payment_cookie = self.get_cookie(unique_order, '')
        if not payment_cookie:
            now = int(time.time())
            transactions[unique_order] = {'shopid': shopid, 'amount': amount, 'issued': now, 'user': user, 'status': 1}
            self.set_cookie(unique_order, str(now), expires=now + ORDER_EXPIRES_SEC)

        order = {'id': unique_order,
                'amount': amount,
                'poll_uri': '%s/api/poll/%s/' % (base_url(self.request), unique_order),
                'qrcode_url': tornado.options.options.mcash_qrcode % (shortlink_id, unique_order)}
        return json.dumps(order)

    def _check_header(self, key, value=None):
        return key in self.request.headers and self.request.headers.get(key).lower() == (value or JSON_CONTENT).lower()

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

    handlers = [
        (r'/api/products/([^/]+)/', ProductHandler),
        (r'/api/poll/([^/]{16,32})/', PollHandler),
        (r'/api/callback/(shortlink|status)/([^/]{16,32})/', CallbackHandler)
    ]
    settings = {
        'static_path': os.path.join(os.path.dirname(__file__), '..', options.static_path),
        'cookie_secret': options.cookie_secret,
        'login_url': '/login',
        'xsrf_cookies': False,
        'autoreload': True
    }
    application = tornado.web.Application(handlers, **settings)
    application.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()
