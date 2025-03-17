odoo.define('waf_wo5.header', function (require) {
    "use strict";

    const publicWidget = require('web.public.widget');
    const { throttle } = require('web.utils');

    publicWidget.registry.HeaderEffect = publicWidget.Widget.extend({
        selector: '.o_header_standard',

        start: function () {
            this._onScroll = throttle(this._onScroll.bind(this), 10);
            window.addEventListener('scroll', this._onScroll);
            this._onScroll();
            return this._super.apply(this, arguments);
        },

        destroy: function () {
            window.removeEventListener('scroll', this._onScroll);
            this._super.apply(this, arguments);
        },

        _onScroll: function () {
            if (window.scrollY > 50) {
                this.$el.addClass('o_header_is_scrolled');
            } else {
                this.$el.removeClass('o_header_is_scrolled');
            }
        },
    });
}); 