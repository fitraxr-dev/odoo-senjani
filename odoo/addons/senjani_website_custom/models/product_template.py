from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.http import request

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _can_user_review(self, user=None):
        if not user:
            user = request.env.user if request else self.env.user
        
        # Public/anonymous users cannot review
        if user._is_public():
            return False
            
        # Superuser and internal employees can always review/post
        if user.id == 1 or user.has_group('base.group_user'):
            return True

        # Count completed transactions (confirmed/done sales orders) containing this product template
        purchase_count = self.env['sale.order'].sudo().search_count([
            ('partner_id', '=', user.partner_id.id),
            ('state', 'in', ('sale', 'done')),
            ('order_line.product_id.product_tmpl_id', '=', self.id)
        ])
        
        if not purchase_count:
            return False

        # Count existing ratings submitted by this partner on this product template
        rating_count = self.env['rating.rating'].sudo().search_count([
            ('res_model', '=', 'product.template'),
            ('res_id', '=', self.id),
            ('partner_id', '=', user.partner_id.id),
            ('consumed', '=', True)
        ])

        return purchase_count > rating_count

    def message_post(self, **kwargs):
        # Determine the actual user posting (using request if available)
        user = request.env.user if request else self.env.user
        
        # Restrict if a rating_value is supplied or if the posting user is portal/public
        is_portal_or_public = not user.has_group('base.group_user') and user.id != 1
        if kwargs.get('rating_value') or is_portal_or_public:
            if not self._can_user_review(user):
                raise UserError(_("Anda hanya dapat memberikan ulasan untuk produk yang telah Anda beli."))
        return super().message_post(**kwargs)

