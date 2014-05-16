Pizzas.PizzasController = Ember.ArrayController.extend({
    actions: {
        payment: function() {
            var s = this.filterProperty('isSelected', true).map(function(pizza) {
                return {id: parseInt(pizza.get('id'), 10), size: 28};
            });
            jQuery.post('/api/products/lagano/pizzas', JSON.stringify(s), function(data) {
                console.log('QR code: ' + data.qrcode_url);
                $('div#qrcode').html('<img src="' + data.qrcode_url + '" height="400" width="400"/>');
                jQuery.post(data.poll_uri, function(data) {
                    var result = JSON.parse(data).result;
                    if (result) {
                        $('div#qrcode').html('<label>Thank you!</label>');
                    } else {
                        $('div#qrcode').html('<label>See you next time!</label>');
                    }
                    console.log('payment success: ' + result);
                });
            });
            return false;
        }
    },

    selected: function() {
        return this.filterProperty('isSelected', true).get('length');
    }.property('@each.isSelected'),

    hasSelected: function() {
        return this.get('selected') === 0;
    }.property('selected'),

    inflection: function() {
        var selected = this.get('selected');
        return selected === 1 ? 'pizza' : 'pizzas';
    }.property('selected')
});
