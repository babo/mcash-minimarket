Pizzas.PizzaController = Ember.ObjectController.extend({
    actions: {
        isSelected: function (key, value) {
            var model = this.get('model');

            if (value === undefined) {
                return model.get('isSelected');
            } else {
                model.set('isSelected', value);
                model.save();
                return value;
            }
        }.property('model.isSelected')
    }
});
