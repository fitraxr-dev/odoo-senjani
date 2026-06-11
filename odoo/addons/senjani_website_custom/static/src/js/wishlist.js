(function () {
    'use strict';

    function initWishlistToggle() {
        // Bind click event handler to the document to support dynamically loaded cards
        document.addEventListener('click', function (event) {
            var btn = event.target.closest('.senjani-wishlist-btn');
            if (btn) {
                // Prevent navigation if inside an <a> tag
                event.preventDefault();
                event.stopPropagation();

                // Toggle class
                btn.classList.toggle('active');
                console.log('[Wishlist] Toggled active state for product button');
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWishlistToggle);
    } else {
        initWishlistToggle();
    }
})();