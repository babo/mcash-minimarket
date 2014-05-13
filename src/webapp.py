#!/usr/bin/env python
import os
import json
import uuid

import tornado.ioloop
import tornado.web
import tornado.options

tornado.options.define('cookie_secret', default='sssecccc', help='Change this to a real secret')
tornado.options.define('favicon', default='static/favicon.ico', help='Path to favicon.ico')
tornado.options.define('static_path', default='static/', help='Path static items')
tornado.options.define('port', default=8888, help='Port to run webservice')
tornado.options.define('config', default='server.conf', help='Config file location')

JSON_CONTENT = 'application/vnd.api+json'

shops = {}

class ProductHandler(tornado.web.RequestHandler):
    def get(self, shopid):
        if shopid not in shops:
            inventory = {'pizzas':
                    [   {'id': 1, 'name': 'Pizza lagano', 'price': 45},
                        {'id': 2, 'name': 'Pizza vegan', 'price': 50},
                        {'id': 3, 'name': 'Pizza %s' % shopid, 'price': 55},
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
        if not self.get_cookie('user'):
            self.set_cookie('user', str(uuid.uuid1()))
        self.write(shops[shopid])

    def post(self, shopid):
        if shopid not in shops:
            raise tornado.web.HTTPError(404)
        if self._check_header('Content-Type') and self._check_header('Accept'):
            self.set_header('Content-Type', JSON_CONTENT)
            try:
                price = self._validate_content(shopid)
                if price > 0:
                    self.write(str(price))
                else:
                    raise tornado.web.HTTPError(400)
            except ValueError:
                raise tornado.web.HTTPError(400)
        else:
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
            price = 0
            for piece in content:
                if not isinstance(piece, dict):
                    return -1
                if piece['id'] not in pizzas or piece['size'] not in sizes:
                    return -1
                price += pizzas[piece['id']]['price']
                price += sizes[piece['size']]['price']
                if 'toppings' in piece:
                    for t in piece['toppings']:
                        price += toppings[t['id']]['price']
            return price
        except Exception:
            return -1

    def _check_header(self, key, value=None):
        return key in self.request.headers and self.request.headers.get(key).lower() == (value or JSON_CONTENT).lower()

def main():
    tornado.options.parse_command_line()
    options = tornado.options.options
    if os.path.exists(options.config):
        tornado.options.parse_config_file(options.config)

    handlers = [
        (r'/api/products/([^/]+)/', ProductHandler)
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

if __name__ == "__main__":
    main()
