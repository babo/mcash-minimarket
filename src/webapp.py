#!/usr/bin/env python
import os
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

class ProductHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('[]')

def main():
    tornado.options.parse_command_line()
    options = tornado.options.options
    if os.path.exists(options.config):
        tornado.options.parse_config_file(options.config)

    handlers = [
        (r'/api/products/(.*)', ProductHandler),
        (r'/', MainHandler),
    ]
    settings = {
        'static_path': os.path.join(os.path.dirname(__file__), '..', options.static_path),
        'cookie_secret': options.cookie_secret,
        'login_url': '/login',
        'xsrf_cookies': True,
    }
    application = tornado.web.Application(handlers, **settings)
    application.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()
