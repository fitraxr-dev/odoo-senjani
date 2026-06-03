# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SenjaniBankReconcileWizard(models.TransientModel):
    _name = 'senjani.bank.reconcile.wizard'
    _description = 'Senjani Bank Reconciliation Wizard (Community Edition)'

    statement_line_id = fields.Many2one(
        'account.bank.statement.line',
        string='Bank Mutation Line',
        required=True,
        ondelete='cascade',
    )

    payment_ref = fields.Char(
        related='statement_line_id.payment_ref',
        string='Mutation Reference',
        readonly=True,
    )

    date = fields.Date(
        related='statement_line_id.date',
        string='Mutation Date',
        readonly=True,
    )

    amount = fields.Monetary(
        related='statement_line_id.amount',
        string='Mutation Amount',
        currency_field='currency_id',
        readonly=True,
    )

    currency_id = fields.Many2one(
        related='statement_line_id.currency_id',
        string='Currency',
        readonly=True,
    )

    partner_id = fields.Many2one(
        related='statement_line_id.partner_id',
        string='Partner / Customer',
        readonly=True,
    )

    reconcile_type = fields.Selection(
        selection=[
            ('payment', 'Match with Existing Payment'),
            ('invoice', 'Reconcile Invoice / Bill Directly')
        ],
        string='Reconciliation Type',
        default='payment',
        required=True,
    )

    payment_id = fields.Many2one(
        'account.payment',
        string='Payment Document',
        help='Select the outstanding payment document to match.',
    )

    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice / Bill Document',
        help='Select the customer invoice or vendor bill to reconcile directly.',
    )

    @api.onchange('statement_line_id')
    def _onchange_statement_line_id(self):
        """
        Provide dynamic domains for filtering payments and invoices.
        """
        if not self.statement_line_id:
            return {}

        amount_abs = abs(self.amount)
        # Domain for Payment: outstanding payments matching the amount
        payment_domain = [
            ('state', '=', 'in_process'),
            ('amount', '=', amount_abs),
        ]
        if self.partner_id:
            payment_domain.append(('partner_id', '=', self.partner_id.id))

        # Domain for Invoice: unpaid posted moves
        invoice_type = ('out_invoice', 'out_refund') if self.amount >= 0 else ('in_invoice', 'in_refund')
        invoice_domain = [
            ('move_type', 'in', invoice_type),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
        ]
        if self.partner_id:
            invoice_domain.append(('partner_id', '=', self.partner_id.id))

        return {
            'domain': {
                'payment_id': payment_domain,
                'invoice_id': invoice_domain,
            }
        }

    def action_reconcile(self):
        self.ensure_one()
        line = self.statement_line_id
        if not line:
            raise UserError(_("Bank Mutation Line not found!"))

        if self.reconcile_type == 'payment':
            if not self.payment_id:
                raise UserError(_("Please select a payment document!"))
            
            payment = self.payment_id
            journal = line.journal_id
            
            # Find outstanding accounts from journal settings
            outstanding_account = False
            if line.amount >= 0:
                # Inbound payment (Outstanding Receipts)
                for method_line in journal.inbound_payment_method_line_ids:
                    if method_line.payment_account_id:
                        outstanding_account = method_line.payment_account_id
                        break
            else:
                # Outbound payment (Outstanding Payments)
                for method_line in journal.outbound_payment_method_line_ids:
                    if method_line.payment_account_id:
                        outstanding_account = method_line.payment_account_id
                        break
            
            if not outstanding_account:
                # Fallback based on standard codes
                code = '101403' if line.amount >= 0 else '101404'
                outstanding_account = self.env['account.account'].search([('code', '=', code)], limit=1)
                
            if not outstanding_account:
                raise UserError(_("Outstanding Receipts/Payments account not configured on your bank journal!"))
            
            # Find unreconciled outstanding line in the payment journal entry
            payment_line = payment.move_id.line_ids.filtered(
                lambda l: l.account_id == outstanding_account and not l.reconciled
            )
            if not payment_line:
                payment_line = payment.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_current' and not l.reconciled
                )
            if not payment_line:
                raise UserError(_("No unreconciled Outstanding Receipts/Payments line found on payment %s!") % payment.name)

            # Find unreconciled suspense line in the bank statement line journal entry
            suspense_line = line.move_id.line_ids.filtered(
                lambda l: l.account_id == journal.suspense_account_id and not l.reconciled
            )
            if not suspense_line:
                suspense_line = line.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_current' and not l.reconciled
                )
            if not suspense_line:
                raise UserError(_("No unreconciled suspense line found on this bank mutation!"))

            # Update suspense account to outstanding receipts/payments account
            stmt_move = line.move_id
            stmt_move.button_draft()
            suspense_line.account_id = outstanding_account.id
            stmt_move.action_post()

            # Execute accounting reconciliation
            (suspense_line + payment_line).reconcile()

        elif self.reconcile_type == 'invoice':
            if not self.invoice_id:
                raise UserError(_("Please select an Invoice / Bill document!"))
            
            invoice = self.invoice_id
            
            # Find receivable/payable line in the invoice
            receivable_line = invoice.line_ids.filtered(
                lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable') and not l.reconciled
            )
            if not receivable_line:
                raise UserError(_("No unreconciled Receivable/Payable line found on invoice %s!") % invoice.name)

            # Find unreconciled suspense line in the bank statement line journal entry
            journal = line.journal_id
            suspense_line = line.move_id.line_ids.filtered(
                lambda l: l.account_id == journal.suspense_account_id and not l.reconciled
            )
            if not suspense_line:
                suspense_line = line.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_current' and not l.reconciled
                )
            if not suspense_line:
                raise UserError(_("No unreconciled suspense line found on this bank mutation!"))

            # Update suspense account to receivable/payable account
            stmt_move = line.move_id
            stmt_move.button_draft()
            suspense_line.account_id = receivable_line.account_id.id
            stmt_move.action_post()

            # Execute accounting reconciliation
            (suspense_line + receivable_line).reconcile()

        return {'type': 'ir.actions.act_window_close'}
