Pizzas.Router.map(function () {
    this.resource('pizzas', {path: '/'}, function () {
        this.route('selected');
    });
});

Pizzas.PizzasRoute = Ember.Route.extend({
    model: function() {
        return this.store.find('pizza');
    }
});

Pizzas.PizzasIndexRoute = Ember.Route.extend({
    model: function() {
        return this.modelFor('pizzas');
    }
});

Pizzas.PizzasSelectedRoute = Ember.Route.extend({
    model: function() {
        return this.store.filter('pizza', function(pizza) {
            return pizza.get('isSelected');
        });
    },
    renderTemplate: function(controller) {
        this.render('pizzas/index', {controller: controller});
    }
});
