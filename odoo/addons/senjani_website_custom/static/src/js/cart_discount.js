/**
 * Cart Discount Display Module
 * 
 * Handles dynamic discount row insertion and updates in the shopping cart.
 * Automatically collects all applied discounts and displays them in a single row.
 * 
 * Features:
 * - Dynamically inserts discount row after taxes
 * - Collects ALL discount line items (promos, gift cards, manual discounts)
 * - Real-time discount value calculation from applied discounts
 * - Automatic updates on cart changes via MutationObserver
 * - Supports multiple simultaneous discounts
 * - Robust DOM element selection with fallback strategies
 * 
 * How it works:
 * 1. Scans all cart products for items with data-reward-type="discount"
 * 2. Extracts and sums all discount amounts
 * 3. Displays total in dedicated discount row
 * 4. Updates automatically when new discounts are applied
 */

(function () {
    'use strict';

    /**
     * Main initialization function
     * Adds discount row and sets up observers for real-time updates
     */
    function initializeCartDiscount() {
        console.log('[Discount] Initializing cart discount module...');
        if (addDiscountRow()) {
            setupMutationObserver();
            console.log('[Discount] Module initialized successfully');
        } else {
            console.log('[Discount] Failed to add discount row');
        }
    }

    /**
     * Adds the discount row to the cart total section
     * @returns {boolean} True if discount row was added/found, false otherwise
     */
    function addDiscountRow() {
        console.log('[Discount] addDiscountRow() called');

        // Check if discount row already exists in DOM
        if (document.getElementById('order_total_discount')) {
            console.log('[Discount] Discount row already exists in DOM');
            updateDiscountValue();
            return true;
        }

        // Find taxes row - primary method using ID
        var taxesRow = document.getElementById('order_total_taxes');

        // Fallback: search by text content if ID not found
        if (!taxesRow) {
            taxesRow = findTaxesRowByContent();
        }

        // If still not found, retry after delay
        if (!taxesRow) {
            console.log('[Discount] Taxes row not found, retrying...');
            setTimeout(initializeCartDiscount, 500);
            return false;
        }

        // Create and insert discount row
        console.log('[Discount] Creating and inserting discount row');
        var discountRow = createDiscountRow();
        taxesRow.parentNode.insertBefore(discountRow, taxesRow.nextSibling);

        updateDiscountValue();
        return true;
    }

    /**
     * Finds taxes row by searching content (fallback method)
     * @returns {Element|null}
     */
    function findTaxesRowByContent() {
        var cartTable = document.querySelector('#cart_total table tbody');
        if (!cartTable) return null;

        var rows = cartTable.querySelectorAll('tr');
        for (var i = 0; i < rows.length; i++) {
            var text = rows[i].textContent.toLowerCase();
            if (text.includes('taxes') || text.includes('tax')) {
                return rows[i];
            }
        }
        return null;
    }

    /**
     * Creates the discount row DOM element
     * @returns {HTMLElement}
     */
    function createDiscountRow() {
        var row = document.createElement('tr');
        row.id = 'order_total_discount';
        row.className = 'd-none'; // Hidden by default until discount > 0
        row.innerHTML =
            '<td colspan="2" class="text-muted border-0 ps-0 pt-0 pb-3">Discount</td>' +
            '<td class="text-end border-0 pe-0 pt-0 pb-3">' +
            '  <span class="monetary_field" style="white-space: nowrap;">' +
            '    Rp&#160;<span class="oe_currency_value discount_value">0.00</span>' +
            '  </span>' +
            '</td>';
        return row;
    }

    /**
     * Updates the discount value based on applied discount lines
     * Collects all discount items (data-reward-type="discount") and sums their values
     * Supports multiple discounts/promos applied simultaneously
     */
    function updateDiscountValue() {
        var discountRow = document.getElementById('order_total_discount');
        if (!discountRow) {
            console.log('[Discount] Row not found');
            return;
        }

        // Calculate total discount from all discount line items
        var totalDiscount = calculateTotalDiscount();
        console.log('[Discount] Total discount calculated:', totalDiscount);

        // Update display - we format it as it appeared in your expected HTML (- 75.00)
        var discountValueSpan = discountRow.querySelector('.discount_value');
        if (discountValueSpan) {
            // Using absolute value here as you expected the minus to be outside the span: "Rp - 75.00"
            discountValueSpan.textContent = '- ' + Math.abs(totalDiscount).toFixed(2);
            console.log('[Discount] Updated span value to:', discountValueSpan.textContent);
        }

        // Show/hide row based on discount value
        if (totalDiscount < -0.01) { // Negative = discount
            console.log('[Discount] Showing discount row (discount > 0.01)');
            discountRow.classList.remove('d-none');
        } else {
            console.log('[Discount] Hiding discount row (discount <= 0.01)');
            discountRow.classList.add('d-none');
        }
    }

    /**
     * Calculates total discount from all applied discount lines
     * Searches for items with data-reward-type="discount" attribute
     * @returns {number} Total discount value (negative number)
     */
    function calculateTotalDiscount() {
        var cartProducts = document.querySelectorAll('#cart_products .o_cart_product');
        console.log('[Discount] Found', cartProducts.length, 'cart products');

        var totalDiscount = 0;

        cartProducts.forEach(function (product, index) {
            // Check if this is a discount/reward line 
            // In Odoo, data-reward-type="discount" is often on a span inside the product
            var discountSpan = product.querySelector('[data-reward-type="discount"]');

            if (discountSpan) {
                console.log('[Discount] Product', index, 'contains a discount span');
                // Extract price from this discount line
                var priceContainer = product.querySelector('[name="website_sale_cart_line_price"]');
                if (priceContainer) {
                    var price = extractPrice(priceContainer);
                    console.log('[Discount] Found discount line - extracted price:', price);

                    // Jika price terbaca positif tapi ini adalah baris diskon, kita jadikan negatif
                    if (price > 0 && String(priceContainer.textContent).indexOf('-') !== -1) {
                        price = -price;
                    }

                    totalDiscount += price;
                }
            } else {
                // Fallback: check if the product has a negative price (sometimes Odoo doesn't use data-reward-type)
                var priceContainerFallback = product.querySelector('[name="website_sale_cart_line_price"]');
                if (priceContainerFallback) {
                    var textContent = priceContainerFallback.textContent.trim();
                    // Just an extra check in case it's missed
                    if (textContent.indexOf('-') !== -1) {
                        var fallbackPrice = extractPrice(priceContainerFallback);
                        if (fallbackPrice < 0) {
                            console.log('[Discount] Found implicit discount line (negative price):', fallbackPrice);
                            totalDiscount += fallbackPrice;
                        }
                    }
                }
            }
        });

        console.log('[Discount] Final total discount:', totalDiscount);
        return totalDiscount;
    }

    /**
     * Extracts and parses monetary value from various DOM structures
     * Handles both US format (1,234.56) and Indonesian format (1.234,56)
     * @param {Element} row - Row/span containing monetary value
     * @returns {number} Parsed price value
     */
    function extractPrice(row) {
        if (!row) {
            console.log('[Discount] extractPrice: row is null');
            return 0;
        }

        // Try to find monetary_field span first (for cart total rows)
        var span = row.querySelector('.monetary_field');

        // If not found, try to use the element itself if it contains the value
        if (!span) {
            span = row;
        }

        if (!span) {
            console.log('[Discount] extractPrice: span is null');
            return 0;
        }

        // Look for .oe_currency_value within the span
        var currencySpan = span.querySelector('.oe_currency_value');
        if (!currencySpan) {
            // If not found, try to extract from span's text directly
            currencySpan = span;
        }

        var text = currencySpan.textContent;
        if (!text) {
            console.log('[Discount] extractPrice: text is empty');
            return 0;
        }

        // Extract only numeric characters, dots, commas, and minus sign
        var cleaned = text.replace(/[^\d,.\-]/g, '').trim();
        console.log('[Discount] extractPrice: raw text="' + text + '" → cleaned="' + cleaned + '"');

        // Parse the number, handling both US (1,234.56) and Indonesian (1.234,56) formats
        var num = parseMonetaryValue(cleaned);
        console.log('[Discount] extractPrice: result=' + num);
        return num;
    }

    /**
     * Parse monetary value in US or Indonesian format
     * US: 1,234.56 (comma as thousands, dot as decimal)
     * Indonesian: 1.234,56 (dot as thousands, comma as decimal)
     * @param {string} str - Formatted number string
     * @returns {number} Parsed number
     */
    function parseMonetaryValue(str) {
        if (!str) return 0;

        // Handle minus sign (termasuk character Unicode minus yang spesifik dari Odoo)
        var isNegative = str.indexOf('-') !== -1 || str.indexOf('−') !== -1 || str.indexOf('—') !== -1;

        // Remove minus signs and invisible characters for processing
        var numStr = str.replace(/[-−—\u200B\uFEFF\s]/g, '');

        // Count dots and commas
        var dotCount = (numStr.match(/\./g) || []).length;
        var commaCount = (numStr.match(/,/g) || []).length;

        var result = 0;

        if (dotCount === 0 && commaCount === 0) {
            // No separators: "75" or "7500"
            result = parseFloat(numStr);
        } else if (dotCount === 1 && commaCount === 0) {
            // Only dots: could be US format decimal "75.00" or thousands "1.000"
            // Assume dot before last 3 digits is decimal (US format)
            var lastDotIndex = numStr.lastIndexOf('.');
            var afterDot = numStr.substring(lastDotIndex + 1);
            if (afterDot.length <= 2) {
                // Likely decimal separator (US format: 75.00 or 1234.56)
                result = parseFloat(numStr);
            } else {
                // Likely thousands separator (shouldn't happen with only 1 dot)
                result = parseFloat(numStr.replace('.', ''));
            }
        } else if (dotCount === 0 && commaCount === 1) {
            // Only commas: likely decimal separator (Indonesian 75,00 or 1234,56)
            result = parseFloat(numStr.replace(',', '.'));
        } else if (dotCount > 0 && commaCount > 0) {
            // Both dots and commas: last one is decimal separator
            var lastDotIndex = numStr.lastIndexOf('.');
            var lastCommaIndex = numStr.lastIndexOf(',');

            if (lastCommaIndex > lastDotIndex) {
                // Comma is last: Indonesian format (1.234,56)
                result = parseFloat(numStr.replace(/\./g, '').replace(',', '.'));
            } else {
                // Dot is last: US format (1,234.56)
                result = parseFloat(numStr.replace(/,/g, ''));
            }
        }

        return isNegative ? -result : result;
    }

    /**
     * Sets up MutationObserver to watch for cart changes
     * Automatically updates discount when cart is modified
     */
    var isUpdating = false;
    function setupMutationObserver() {
        var cartDiv = document.getElementById('cart_total');
        if (!cartDiv) {
            console.log('[Discount] cart_total element not found');
            return;
        }

        console.log('[Discount] Setting up MutationObserver on cart_total');
        var observer = new MutationObserver(function () {
            if (isUpdating) return;
            isUpdating = true;
            console.log('[Discount] Cart mutation detected, updating discount value...');
            updateDiscountValue();
            // Allow DOM to settle before releasing flag
            setTimeout(function() {
                isUpdating = false;
            }, 0);
        });

        var config = {
            subtree: true,
            characterData: true,
            childList: true
        };

        observer.observe(cartDiv, config);
        console.log('[Discount] MutationObserver setup complete');
    }

    /**
     * Initialize when DOM is ready
     */
    console.log('[Discount] Script loaded');
    if (document.readyState === 'loading') {
        console.log('[Discount] DOM still loading, waiting for DOMContentLoaded...');
        document.addEventListener('DOMContentLoaded', function () {
            console.log('[Discount] DOMContentLoaded event fired');
            initializeCartDiscount();
        });
    } else {
        console.log('[Discount] DOM already loaded, initializing immediately...');
        initializeCartDiscount();
    }
})();