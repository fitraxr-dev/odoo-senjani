from odoo import models, fields, api

class SenjaniTransferWizard(models.TransientModel):
    _name = 'senjani.transfer.wizard'
    _description = 'Transfer Funds Wizard'

    journal_id = fields.Many2one('account.journal', string='From Journal', required=True, readonly=True)
    destination_journal_id = fields.Many2one('account.journal', string='To Journal', required=True, domain="[('type', '=', 'bank'), ('id', '!=', journal_id)]")
    amount = fields.Monetary(string='Amount', required=True)
    currency_id = fields.Many2one('res.currency', related='journal_id.currency_id')
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    memo = fields.Char(string='Memo')

    def action_transfer(self):
        self.ensure_one()
        
        transfer_account = self.env.company.transfer_account_id
        partner = self.env.company.partner_id
        
        # 1. Create Outbound Payment
        outbound = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'journal_id': self.journal_id.id,
            'partner_id': partner.id,
            'destination_account_id': transfer_account.id,
            'amount': self.amount,
            'date': self.date,
            'memo': self.memo,
        })
        outbound.action_post()

        # 2. Create Inbound Payment (Draft)
        inbound = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'journal_id': self.destination_journal_id.id,
            'partner_id': partner.id,
            'destination_account_id': transfer_account.id,
            'amount': self.amount,
            'date': self.date,
            'memo': self.memo,
            'paired_internal_transfer_payment_id': outbound.id,
        })
        outbound.paired_internal_transfer_payment_id = inbound.id
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
