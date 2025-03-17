odoo.define('waf_wo5.moderna', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    publicWidget.registry.ModernaEffects = publicWidget.Widget.extend({
        selector: '.o_website_sale',

        start: function () {
            this._super.apply(this, arguments);
            this._initAOS();
            return this;
        },

        _initAOS: function () {
            // Animation on scroll
            if (typeof AOS !== 'undefined') {
                AOS.init({
                    duration: 1000,
                    easing: 'ease-in-out',
                    once: true,
                    mirror: false
                });
            }
        }
    });
}); 