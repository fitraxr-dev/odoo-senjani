from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.osv import expression
from odoo.addons.portal.controllers.portal import CustomerPortal

class SenjaniWebsiteSale(WebsiteSale):
    def _get_shop_domain(self, search, category, attrib_values, search_in_description=True):
        domain = super()._get_shop_domain(search, category, attrib_values, search_in_description)
        
        # Get selected internal categories from request parameters
        category_ids = request.httprequest.args.getlist('category_id') if request else []
        category_ids = [int(cid) for cid in category_ids if cid.isdigit()]
        
        if category_ids:
            # We want to match products that belong to any of the selected internal categories (categ_id)
            category_domain = [('categ_id', 'child_of', category_ids)]
            domain = expression.AND([domain, category_domain])
            
        return domain

    def _shop_lookup_products(self, attrib_set, options, post, search, website):
        fuzzy_search_term, product_count, search_result = super()._shop_lookup_products(attrib_set, options, post, search, website)
        
        # Get selected internal categories from request parameters
        category_ids = request.httprequest.args.getlist('category_id') if request else []
        category_ids = [int(cid) for cid in category_ids if cid.isdigit()]
        
        if category_ids:
            # Filter in-memory using filtered_domain to preserve search order
            search_result = search_result.filtered_domain([('categ_id', 'child_of', category_ids)])
            product_count = len(search_result)
            
        return fuzzy_search_term, product_count, search_result

    def _get_additional_shop_values(self, values):
        res = super()._get_additional_shop_values(values)
        
        # Get internal categories under 'Saleable' (using sudo to bypass ACLs for public users)
        saleable_category = request.env['product.category'].sudo().search([('name', '=', 'Saleable')], limit=1)
        if saleable_category:
            filter_categories = saleable_category.child_id
        else:
            # Fallback to 'All'
            all_category = request.env['product.category'].sudo().search([('name', '=', 'All')], limit=1)
            if all_category:
                filter_categories = all_category.child_id
            else:
                # Fallback to all top-level categories
                filter_categories = request.env['product.category'].sudo().search([('parent_id', '=', False)])
        
        # Get selected categories from request parameters
        category_ids = request.httprequest.args.getlist('category_id') if request else []
        selected_category_ids = [int(cid) for cid in category_ids if cid.isdigit()]
        
        res.update({
            'filter_categories': filter_categories,
            'selected_category_ids': selected_category_ids,
        })
        return res

    def _shop_get_query_url_kwargs(self, category, search, min_price, max_price, order=None, tags=None, attribute_value=None, **post):
        res = super()._shop_get_query_url_kwargs(category, search, min_price, max_price, order, tags, attribute_value, **post)
        res.update({
            'category_id': request.httprequest.args.getlist('category_id'),
        })
        return res


class SenjaniPortal(CustomerPortal):

    @http.route(['/my/orders/<int:order_id>/mark-received'], type='http',
                auth='user', methods=['POST'], website=True, csrf=True)
    def portal_mark_order_received(self, order_id, **kw):
        """Endpoint untuk pelanggan menandai pesanan sudah diterima."""
        order = request.env['sale.order'].sudo().search([
            ('id', '=', order_id),
            ('partner_id', '=', request.env.user.partner_id.id),
        ], limit=1)

        if not order:
            return request.redirect('/my/orders')

        if order.senjani_order_status == 'IN_DELIVERY':
            order.sudo().write({'senjani_order_status': 'DONE'})

        return request.redirect(order.get_portal_url())
