from odoo import models, fields, api

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_senjani_bank_journal = fields.Boolean(
        compute='_compute_is_senjani_bank_journal'
    )

    @api.depends('journal_id')
    def _compute_is_senjani_bank_journal(self):
        for rec in self:
            rec.is_senjani_bank_journal = (rec.journal_id.type == 'bank')
