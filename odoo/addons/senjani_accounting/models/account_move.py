from odoo import models, fields, api


class AccountMove(models.Model):
    """
    Extension of account.move for Xendit Payment integration.

    Saves Xendit payment references on customer invoices
    generated automatically from Sales Orders via Xendit webhooks.
    """
    _inherit = 'account.move'

    # Payment reference from Xendit (auto-filled via SO webhook)
    x_xendit_payment_ref = fields.Char(
        string='Xendit Payment Reference',
        readonly=True,
        copy=False,
        help='Payment ID from Xendit linked with this invoice. '
             'Auto-filled when the Sales Order is created via Xendit webhook.',
        tracking=True,
    )

    # Payment status on Xendit side
    x_xendit_payment_status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('settled', 'Settled'),
            ('expired', 'Expired'),
            ('failed', 'Failed'),
        ],
        string='Xendit Payment Status',
        readonly=True,
        copy=False,
        help='Payment status in the Xendit system.',
        tracking=True,
    )

    # Xendit payment method (transfer, QRIS, VA, etc)
    x_xendit_payment_method = fields.Char(
        string='Payment Method (Xendit)',
        readonly=True,
        copy=False,
        help='Example: BANK_TRANSFER, QRIS, VIRTUAL_ACCOUNT_BNI, etc.',
    )

    @api.depends('x_xendit_payment_ref', 'move_type')
    def _compute_display_xendit_info(self):
        """Check if Xendit info should be shown on form."""
        for move in self:
            move.x_show_xendit_info = bool(
                move.x_xendit_payment_ref and move.move_type == 'out_invoice'
            )

    x_show_xendit_info = fields.Boolean(
        compute='_compute_display_xendit_info',
        string='Show Xendit Info',
    )

    def action_senjani_confirm_invoice(self):
        """
        Batch action: confirm invoice from Draft to Posted.
        Used in list views to improve accounting team efficiency.
        """
        draft_invoices = self.filtered(
            lambda m: m.state == 'draft' and m.move_type in ('out_invoice', 'out_refund')
        )
        if draft_invoices:
            draft_invoices.action_post()
        return True

    def action_senjani_confirm_bill(self):
        """
        Batch action: confirm vendor bill from Draft to Posted.
        Used in list views to improve accounting team efficiency.
        """
        draft_bills = self.filtered(
            lambda m: m.state == 'draft' and m.move_type in ('in_invoice', 'in_refund')
        )
        if draft_bills:
            draft_bills.action_post()
        return True

    def action_post(self):
        """
        Override action_post to automatically match Xendit payments.
        """
        res = super(AccountMove, self).action_post()
        self._auto_link_xendit_payment()
        return res

    def _auto_link_xendit_payment(self):
        """
        Custom helper to find outstanding payments in the Xendit Journal
        matching the Sales Order reference (invoice_origin) and reconcile them.
        """
        for invoice in self:
            if invoice.move_type != 'out_invoice' or invoice.state != 'posted' or invoice.payment_state not in ('not_paid', 'partial'):
                continue

            # Find Sales Order reference (e.g. S00050)
            origin = invoice.invoice_origin or invoice.ref
            if not origin:
                continue

            # Find outstanding receivable lines in Xendit Journal (XNDT)
            receivable_lines = self.env['account.move.line'].search([
                ('partner_id', '=', invoice.partner_id.id),
                ('account_id.account_type', '=', 'asset_receivable'),
                ('reconciled', '=', False),
                ('journal_id.code', '=', 'XNDT'),
                '|',
                ('move_id.ref', 'ilike', origin),
                ('name', 'ilike', origin),
            ])

            if receivable_lines:
                # Find receivable line on this invoice
                invoice_receivable_line = invoice.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
                )
                if invoice_receivable_line:
                    # Perform automatic reconciliation
                    (invoice_receivable_line + receivable_lines[0]).reconcile()


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    @api.model
    def _setup_senjani_outstanding_accounts(self):
        """
        Setup Outstanding Receipts and Payments accounts for XNDT and BNK1 journals.
        """
        XNDT = self.search([('code', '=', 'XNDT')])
        BNK1 = self.search([('code', '=', 'BNK1')])
        out_receipts = self.env['account.account'].search([('code', '=', '101403')])
        out_payments = self.env['account.account'].search([('code', '=', '101404')])
        
        if out_receipts and out_payments:
            for journal in (XNDT + BNK1):
                for line in journal.inbound_payment_method_line_ids:
                    if not line.payment_account_id:
                        line.payment_account_id = out_receipts.id
                for line in journal.outbound_payment_method_line_ids:
                    if not line.payment_account_id:
                        line.payment_account_id = out_payments.id

    def open_action(self):
        """
        Override open_action so clicking on the dashboard cards opens our custom actions with custom filters.
        """
        self.ensure_one()
        action_name = self.env.context.get('action_name', False)
        if self.type == 'sale':
            if action_name == 'action_move_out_refund_type':
                action = self.env["ir.actions.act_window"]._for_xml_id('senjani_accounting.action_senjani_customer_refunds')
            else:
                action = self.env["ir.actions.act_window"]._for_xml_id('senjani_accounting.action_senjani_customer_invoices')
            ctx = dict(self.env.context, default_journal_id=self.id)
            action['context'] = ctx
            return action
        elif self.type == 'purchase':
            if action_name == 'action_move_in_refund_type':
                action = self.env["ir.actions.act_window"]._for_xml_id('senjani_accounting.action_senjani_vendor_refunds')
            else:
                action = self.env["ir.actions.act_window"]._for_xml_id('senjani_accounting.action_senjani_vendor_bills')
            ctx = dict(self.env.context, default_journal_id=self.id)
            action['context'] = ctx
            return action
        elif self.type == 'bank':
            action = self.env["ir.actions.act_window"]._for_xml_id('senjani_accounting.action_senjani_bank_statement_bri')
            ctx = dict(self.env.context, default_journal_id=self.id)
            action['context'] = ctx
            return action

        return super(AccountJournal, self).open_action()

    def open_customer_payments_action(self):
        """
        Open the customer payments list (inbound payments) for this journal.
        """
        self.ensure_one()
        return self.open_payments_action(payment_type='inbound')


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    # Override journal_id to be writable so users can select it in the form view
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        compute='_compute_journal_id',
        inverse='_inverse_journal_id',
        store=True,
        readonly=False,
    )

    # Override date to be writable so users can set it in the form view
    date = fields.Date(
        string='Date',
        compute='_compute_date_index',
        inverse='_inverse_date_index',
        store=True,
        readonly=False,
    )

    def _inverse_journal_id(self):
        for stmt in self:
            if stmt.journal_id:
                for line in stmt.line_ids:
                    if not line.journal_id or line.journal_id != stmt.journal_id:
                        line.journal_id = stmt.journal_id

    def _inverse_date_index(self):
        for stmt in self:
            if stmt.date:
                for line in stmt.line_ids:
                    if not line.date or line.date != stmt.date:
                        line.date = stmt.date


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    def action_open_reconcile_wizard(self):
        self.ensure_one()
        return {
            'name': 'Bank Mutation Reconciliation',
            'type': 'ir.actions.act_window',
            'res_model': 'senjani.bank.reconcile.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_statement_line_id': self.id,
            }
        }
