window.Pizzas = Ember.Application.create();

Pizzas.ApplicationAdapter = DS.RESTAdapter.extend({namespace: 'api/products/lagano'});
