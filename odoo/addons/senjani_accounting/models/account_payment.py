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
        # First, run standard post to create the payment move and reconcile with bills
        res = super(AccountPayment, self).action_validate()
        
        # Second, for bank journals, automatically create a bank statement line 
        # and reconcile it so it updates the bank balance and marks bill as paid.
        for payment in self:
            if payment.journal_id.type == 'bank' and not payment.is_reconciled:
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
                
                # 2. Find payable/receivable lines on the linked bills
                moves = payment.reconciled_bill_ids or payment.reconciled_invoice_ids
                if not moves:
                    continue
                    
                bill_lines = moves.line_ids.filtered(
                    lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable') and not l.reconciled
                )
                if not bill_lines:
                    continue
                
                # 3. Find suspense line on the statement line
                suspense_line = bsl.move_id.line_ids.filtered(
                    lambda l: l.account_id == journal.suspense_account_id and not l.reconciled
                )
                if not suspense_line:
                    suspense_line = bsl.move_id.line_ids.filtered(
                        lambda l: l.account_id.account_type == 'asset_current' and not l.reconciled
                    )
                    
                if bill_lines and suspense_line:
                    payable_account = bill_lines[0].account_id
                    
                    # 4. Perform reconciliation
                    stmt_move = bsl.move_id
                    stmt_move.button_draft()
                    suspense_line.with_context(skip_account_move_synchronization=True).account_id = payable_account.id
                    stmt_move.with_context(skip_account_move_synchronization=True).action_post()
                    (suspense_line + bill_lines).reconcile()
                    
                    # Update payment state
                    payment.is_reconciled = True
                    if payment.state != 'paid':
                        payment.state = 'paid'

        return res

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
