Pizzas.Pizza = DS.Model.extend({
    name: DS.attr('string'),
    image: DS.attr('string'),
    size: DS.attr('number'),
    price: DS.attr('number'),
    isSelected: DS.attr('boolean')
});
