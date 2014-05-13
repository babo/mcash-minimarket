# mcash-minimarket

Minimal example to create a function webshop for small stores like a local pizza shop.

## Installation

All dependencies of python are in requirements.txt. The easiest is to add them to a virtualenv

        virtualenv p
        source p/bin/activate
        pip install -r requirements.txt

All security related must be defined in a file or at command line. Please note, to run it behind a firewall [ngrok](http://ngrok.com) or similar is needed. In this example you should change that to your session.

        mcash_secret = '...'
        mcash_token = '...'
        mcash_user = '...'
        mcash_merchant = '...'
        mcash_endpoint = 'https://mcashtestbed.appspot.com/merchant/v1/'
        mcash_callback_uri = 'https://438e7e13.ngrok.com'

To run the code all you need is to specify the config

        ./src/webapp.py --config=local.config

## Try it out

I used curl to test. The first step is to get the product list. In this example lagano is our pizzeria.

        curl -D - http://localhost:8888/api/products/lagano/

To place an order select a pizza and a size and add toppings if you like. POST it to get the order.

        cat order
            [{"id": 1, "size": 28}, {"id": 2, "size": 36, "toppings": [{"id": 1}, {"id": 2}]}]

        curl -d @order -H 'Content-Type: application/vnd.api+json' -H 'Accept: application/vnd.api+json' http://localhost:8888/api/products/lagano/
