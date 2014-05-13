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

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")

    def post(self):
        pass

cache = {}

class ProductHandler(tornado.web.RequestHandler):
    def get(self, shopid):
        if shopid not in cache:
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
            cache[shopid] = json.dumps(inventory)
        self.set_header('Content-Type', 'application/vnd.api+json')
        if not self.get_cookie('user'):
            self.set_cookie('user', str(uuid.uuid1()))
        self.write(cache[shopid])

    def post(self, shopid):
        if shopid not in cache:
            raise tornado.web.HTTPError(404)
        self.set_header('Content-Type', 'application/vnd.api+json')
        self.write(shopid)

def main():
    tornado.options.parse_command_line()
    options = tornado.options.options
    if os.path.exists(options.config):
        tornado.options.parse_config_file(options.config)

    handlers = [
        (r'/api/products/([^/]+)/', ProductHandler),
        (r'/', MainHandler),
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
