#!/usr/bin/env python
import os
import tornado.ioloop
import tornado.web
import tornado.options

tornado.options.define('cookie_secret', default='sssecccc', help='Change this to a real secret')
tornado.options.define('favicon', default='static/favicon.ico', help='Path to favicon.ico')
tornado.options.define('static_path', default='static/', help='Path static items')
tornado.options.define('port', default=8888, help='Port to run webservice')

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")

    def post(self):
        pass

class ProductHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('[]')

def main():
    options = tornado.options.options
    abs_dir = lambda fn: os.path.join(os.getcwd(), fn)
    handlers =[
        (r'/api/products/(.*)', ProductHandler),
        (r'/', MainHandler),
    ]
    settings = {
        'static_path': os.path.join(os.path.dirname(__file__), '../static'),
        'cookie_secret': options.cookie_secret,
        'login_url': '/login',
        'xsrf_cookies': True,
    }
    application = tornado.web.Application(handlers, **settings)
    application.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()
