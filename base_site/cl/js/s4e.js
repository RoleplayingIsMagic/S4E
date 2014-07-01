/* Roleplaying is Magic S4E Web Edition JS
** Written by the RiM team in 2014, what a wonderful new year!
** Licensed under the BSD 2-clause license
*/

$(document).ready(function() {

    // arrow key nacigation
    // shamelessly stolen from:  https://stackoverflow.com/a/7301862
    $(document).keydown(function(e){
            if (e.keyCode == 37) {  // left
                prev_page();
                return false;
            } else if (e.keyCode == 39) {  // right
                next_page();
                return false;
            }
        });

    // make back button work again
    $(window).on('popstate', function(event) {
        if (!event.originalEvent.state.mlprims4e){
            return
        }
        load_page(location.href, false);
    });

    // toc
    $(document).on('click', '.show-toc', function(event) {
        event.preventDefault();
        $('.toc-popup').addClass('show');
    });

    $(document).on('click', '.toc-popup', function(event) {
        $('.toc-popup').removeClass('show');
    });

    // overrides nav to give nice ajax
    $(document).on('click', '.nav-container a', function(event) {
        event.preventDefault();

        if ($(this).hasClass('prev')) {
            prev_page();
        } else if ($(this).hasClass('next')) {
            next_page();
        }
    });
    $(document).on('click', '.toc a.single-page', function(event) {
        event.preventDefault();

        url = $("link[rel='single-page']").prop('href');
        load_page(url, true);
    });

    // functions
    function prev_page() {
        if ($("link[rel='prev']").length) {
            // window.location.href = 
            url = $("link[rel='prev']").prop('href');
            load_page(url, true);
        }
    }

    function next_page() {
        if ($("link[rel='next']").length) {
            // window.location.href = ;
            url = $("link[rel='next']").prop('href')
            load_page(url, true);
        }
    }

    // ajax
    $.ajaxSetup({
        cache: true,
    });

    function load_page(url, push_state) {
        // console.log(url);
        $(window).scrollTop(0);  // scroll to top

        if (push_state == true) {
            success_func = ajax_success_pushstate
        } else {
            success_func = ajax_success
        }

        // actually load the junk
        // shamelessly stolen from https://stackoverflow.com/a/7407285
        $.ajax({
            url: url,
            dataType: 'html',
            success: success_func,
            error: ajax_fail,
        });
    }

    function ajax_success_pushstate(data) {
        ajax_success(data);

        // Change URL
        history.pushState({ mlprims4e: true, page: url }, '', url);
    }

    function ajax_success(data) {
        // Elements
        var resp = $("<div></div>").html(data);
        $('#content').html(resp.find('#content').html());

        // Title
        var regexp = /<title>(.*)<\/title>/i;
        page_title = data.match(regexp)[1]
        document.title = page_title;
    }

    function ajax_fail(jqXHR, textStatus, errorThrown) {
        message_box('Failed to load new page: ' + errorThrown)
    }

    // messages
    function message_box(message) {
        $('#messages').prepend($('<div class="message"></div>').html(message).hide());
        $('#messages .message:first-of-type').slideDown().delay(2000).slideUp().remove();
    }

})
