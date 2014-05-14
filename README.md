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
            {"pizzas": [{"price": 45, "id": 1, "name": "Pizza lagano"}, {"price": 50, "id": 2, "name": "Pizza vegan"}, {"price": 55, "id": 3, "name": "Pizza of the house"}], "toppings": [{"price": 1, "id": 1, "name": "garlic"}, {"price": 5, "id": 2, "name": "extra cheese"}, {"price": 2, "id": 3, "name": "pepperoni"}], "sizes": [{"price": -5, "id": 28, "name": "28 cm"}, {"price": 0, "id": 32, "name": "32 cm"}, {"price": 5, "id": 36, "name": "36 cm"}]}

To place an order select a pizza and a size and add toppings if you like. POST it to get the order.

        echo '[{"id": 1, "size": 28}, {"id": 2, "size": 36, "toppings": [{"id": 1}, {"id": 2}]}]' > order

        curl -d @order -H 'Content-Type: application/vnd.api+json' -H 'Accept: application/vnd.api+json' http://localhost:8888/api/products/lagano/
            {"poll_uri": "https://18b290ee.ngrok.com/api/poll/7596db1185191baa87a983951ee5e764/", "qrcode_url": "https://api.mca.sh/shortlink/v1/qr_image/---0/7596db1185191baa87a983951ee5e764", "amount": 101, "id": "7596db1185191baa87a983951ee5e764"}

When placing an order the server returns the long poll URI to call, a QR code to display, final amount and an id. Use that to scan the code and authorize the payment.

Long poll returns to a POST with a JSON:

        {"result": true}
