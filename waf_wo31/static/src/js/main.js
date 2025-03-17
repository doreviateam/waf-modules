// Initialize AOS
document.addEventListener('DOMContentLoaded', function () {
    AOS.init({
        duration: 1000,
        easing: 'ease-in-out',
        once: true,
        mirror: false
    });
});

// Initialize Swiper for hero section
var heroSwiper = new Swiper('.hero-swiper', {
    speed: 600,
    parallax: true,
    pagination: {
        el: '.swiper-pagination',
        clickable: true
    },
    navigation: {
        nextEl: '.swiper-button-next',
        prevEl: '.swiper-button-prev'
    }
});

// Sticky header on scroll
window.addEventListener('scroll', function () {
    const header = document.querySelector('#header');
    if (window.scrollY > 100) {
        header.classList.add('header-scrolled');
    } else {
        header.classList.remove('header-scrolled');
    }
});

// Mobile nav toggle
document.querySelector('.mobile-nav-toggle').addEventListener('click', function (e) {
    document.querySelector('#navbar').classList.toggle('navbar-mobile');
    this.classList.toggle('bi-list');
    this.classList.toggle('bi-x');
});

odoo.define('waf_wo31.main', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    publicWidget.registry.WafMain = publicWidget.Widget.extend({
        selector: '#wrapwrap',

        start: function () {
            this._super.apply(this, arguments);
            this._initMobileNav();
            this._initScrolling();
            return this;
        },

        _initMobileNav: function () {
            const mobileNavToggle = document.querySelector('.mobile-nav-toggle');
            const navbar = document.querySelector('#navbar');

            if (mobileNavToggle && navbar) {
                mobileNavToggle.addEventListener('click', function (e) {
                    navbar.classList.toggle('navbar-mobile');
                    this.classList.toggle('bi-list');
                    this.classList.toggle('bi-x');
                });
            }
        },

        _initScrolling: function () {
            const selectHeader = document.querySelector('#header');
            if (selectHeader) {
                const headerScrolled = () => {
                    if (window.scrollY > 100) {
                        selectHeader.classList.add('header-scrolled');
                    } else {
                        selectHeader.classList.remove('header-scrolled');
                    }
                };
                window.addEventListener('load', headerScrolled);
                document.addEventListener('scroll', headerScrolled);
            }
        }
    });

    publicWidget.registry.AosInit = publicWidget.Widget.extend({
        selector: '.o_contact_page, #hero',  // Sélecteurs où AOS sera actif

        start: function () {
            var def = this._super.apply(this, arguments);

            // Initialisation de AOS
            AOS.init({
                duration: 1000,
                easing: 'ease-in-out',
                once: true,
                mirror: false
            });

            return def;
        },
    });

    return publicWidget.registry.WafMain;
}); 