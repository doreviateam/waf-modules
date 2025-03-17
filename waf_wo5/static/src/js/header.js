$(document).ready(function () {
    $(window).scroll(function () {
        if ($(this).scrollTop() > 50) {
            $('.o_header_standard').addClass('scrolled');
        } else {
            $('.o_header_standard').removeClass('scrolled');
        }
    });
});