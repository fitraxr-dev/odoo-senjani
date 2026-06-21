from odoo import models, fields, api

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer/Vendor'
    )

    is_senjani_bank_journal = fields.Boolean(
        compute='_compute_is_senjani_bank_journal'
    )

    @api.depends('journal_id')
    def _compute_is_senjani_bank_journal(self):
        for rec in self:
            rec.is_senjani_bank_journal = (rec.journal_id.type == 'bank')

    def action_validate(self):
        # We don't call super() because base Odoo 18 account.payment doesn't have action_validate
        
        for payment in self:
            if payment.journal_id.type == 'bank' and not payment.is_matched:
                journal = payment.journal_id
                
                # 1. Create bank statement line
                bsl_vals = {
                    'payment_ref': payment.name or payment.ref or 'Auto Reconciled Payment',
                    'journal_id': journal.id,
                    'date': payment.date,
                    'amount': payment.amount if payment.payment_type == 'inbound' else -payment.amount,
                    'partner_id': payment.partner_id.id,
                }
                bsl = self.env['account.bank.statement.line'].create(bsl_vals)
                
                # 2. Find outstanding line on the payment
                payment_outstanding_line = payment.move_id.line_ids.filtered(
                    lambda l: l.account_id == payment.outstanding_account_id and not l.reconciled
                )
                if not payment_outstanding_line:
                    continue
                
                # 3. Find suspense line on the statement line
                suspense_line = bsl.move_id.line_ids.filtered(
                    lambda l: l.account_id == journal.suspense_account_id and not l.reconciled
                )
                if not suspense_line:
                    suspense_line = bsl.move_id.line_ids.filtered(
                        lambda l: l.account_id.account_type == 'asset_current' and not l.reconciled
                    )
                    
                if payment_outstanding_line and suspense_line:
                    # 4. Perform reconciliation
                    stmt_move = bsl.move_id
                    stmt_move.button_draft()
                    suspense_line.with_context(skip_account_move_synchronization=True).account_id = payment_outstanding_line[0].account_id.id
                    stmt_move.with_context(skip_account_move_synchronization=True).action_post()
                    (suspense_line + payment_outstanding_line).reconcile()
                    
                    # Update payment match state
                    payment.is_matched = True

        return True

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _create_payments(self):
        payments = super()._create_payments()
        
        # Automatically populate the payment_reference on the vendor bill 
        # to match the generated payment name so it's visible in the list view.
        moves = self.line_ids.move_id
        if moves:
            bills = moves.filtered(lambda m: m.move_type == 'in_invoice')
            for bill in bills:
                if payments and not bill.payment_reference:
                    bill.payment_reference = payments[0].name
                    
        return payments
