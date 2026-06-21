import random
from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, get_lang


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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('x_xendit_payment_ref'):
                vals['payment_reference'] = vals['x_xendit_payment_ref']
                if not vals.get('x_xendit_payment_method'):
                    vals['x_xendit_payment_method'] = 'Xendit(Xendit)'
        return super(AccountMove, self).create(vals_list)

    def write(self, vals):
        if vals.get('x_xendit_payment_ref'):
            vals['payment_reference'] = vals['x_xendit_payment_ref']
            if not vals.get('x_xendit_payment_method'):
                vals['x_xendit_payment_method'] = 'Xendit(Xendit)'
        return super(AccountMove, self).write(vals)

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
        Override action_post to restrict Vendor Bill confirmation to Accounting Staff
        and automatically match Xendit payments.
        """
        for move in self:
            if move.move_type in ('in_invoice', 'in_refund') and not self.env.user.has_group('senjani_accounting.group_senjani_accounting_staff'):
                raise UserError(_("Hanya tim Accounting yang diizinkan untuk melakukan konfirmasi (Post) pada Vendor Bill."))
        
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
        Creates XNDT journal if it does not exist.
        """
        XNDT = self.search([('code', '=', 'XNDT')])
        if not XNDT:
            XNDT = self.create({
                'name': 'Xendit',
                'code': 'XNDT',
                'type': 'bank',
                'show_on_dashboard': True,
            })
            
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

    def _get_bank_cash_graph_data(self):
        """
        Override to plot the actual ledger balance for Xendit journal (XNDT)
        since Xendit payments do not have statement lines, which causes
        Odoo to display random placeholder data.
        """
        result = super(AccountJournal, self)._get_bank_cash_graph_data()
        
        xndt_journals = self.filtered(lambda j: j.code == 'XNDT')
        if not xndt_journals:
            return result
            
        today = fields.Date.context_today(self)
        start_date = today - timedelta(days=7)
        
        for journal in xndt_journals:
            accounts = [journal.default_account_id.id] if journal.default_account_id else []
            for line in journal.inbound_payment_method_line_ids:
                if line.payment_account_id:
                    accounts.append(line.payment_account_id.id)
            for line in journal.outbound_payment_method_line_ids:
                if line.payment_account_id:
                    accounts.append(line.payment_account_id.id)
            accounts = list(set(accounts))
            
            if not accounts:
                continue
                
            # Find all matching numbers of reconciled payments in the Xendit journal
            self.env.cr.execute("""
                SELECT DISTINCT matching_number
                FROM account_move_line
                WHERE account_id = ANY(%s)
                  AND journal_id = %s
                  AND matching_number IS NOT NULL
            """, (accounts, journal.id))
            match_nums = [r[0] for r in self.env.cr.fetchall()]
            
            # Query starting balance on or before start_date
            if match_nums:
                self.env.cr.execute("""
                    SELECT COALESCE(SUM(debit - credit), 0.0) AS balance
                    FROM account_move_line
                    WHERE account_id = ANY(%s)
                      AND parent_state = 'posted'
                      AND date <= %s
                      AND (journal_id = %s OR (matching_number IS NOT NULL AND matching_number = ANY(%s)))
                """, (accounts, start_date, journal.id, match_nums))
            else:
                self.env.cr.execute("""
                    SELECT COALESCE(SUM(debit - credit), 0.0) AS balance
                    FROM account_move_line
                    WHERE account_id = ANY(%s)
                      AND parent_state = 'posted'
                      AND date <= %s
                      AND journal_id = %s
                """, (accounts, start_date, journal.id))
            starting_balance = self.env.cr.fetchone()[0] or 0.0
            
            # Query daily changes after start_date
            if match_nums:
                self.env.cr.execute("""
                    SELECT date, SUM(debit - credit) AS balance
                    FROM account_move_line
                    WHERE account_id = ANY(%s)
                      AND parent_state = 'posted'
                      AND date > %s
                      AND date <= %s
                      AND (journal_id = %s OR (matching_number IS NOT NULL AND matching_number = ANY(%s)))
                    GROUP BY date
                """, (accounts, start_date, today, journal.id, match_nums))
            else:
                self.env.cr.execute("""
                    SELECT date, SUM(debit - credit) AS balance
                    FROM account_move_line
                    WHERE account_id = ANY(%s)
                      AND parent_state = 'posted'
                      AND date > %s
                      AND date <= %s
                      AND journal_id = %s
                    GROUP BY date
                """, (accounts, start_date, today, journal.id))
            query_result = self.env.cr.dictfetchall()
            daily_changes = {row['date']: row['balance'] for row in query_result}
            
            # Fall back to placeholder if completely empty
            if not daily_changes and starting_balance == 0.0:
                continue
                
            def build_graph_data(date_val, amount_val, currency_val):
                name = format_date(self.env, date_val, 'd LLLL Y')
                short_name = format_date(self.env, date_val, 'd MMM')
                return {'x': short_name, 'y': currency_val.round(amount_val), 'name': name}
                
            currency = journal.currency_id or journal.company_id.currency_id
            data = []
            
            running_amount = starting_balance
            
            # Add starting date data point
            data.append(build_graph_data(start_date, running_amount, currency))
            
            # Add daily balances forward from (today - 6 days) to today
            for day_offset in range(6, -1, -1):
                current_day = today - timedelta(days=day_offset)
                day_change = daily_changes.get(current_day, 0.0)
                running_amount += day_change
                data.append(build_graph_data(current_day, running_amount, currency))
                
            graph_title, graph_key = journal._graph_title_and_key()
            color = '#7c7bad'
            result[journal.id] = [{
                'values': data,
                'title': graph_title,
                'key': 'Escrow Balance',
                'area': True,
                'color': color,
                'is_sample_data': False
            }]
            
        return result

    def _get_sale_purchase_graph_data(self):
        """
        Override to show total sales volume (invoiced sales amount) by invoice_date
        on the Sales Journal card, instead of the default Odoo behavior of showing
        only unpaid invoice due balances.
        """
        result = super(AccountJournal, self)._get_sale_purchase_graph_data()
        
        sale_journals = self.filtered(lambda j: j.type == 'sale')
        if not sale_journals:
            return result
            
        today = fields.Date.context_today(self)
        day_of_week = today.weekday()
        first_day_of_week = today - timedelta(days=day_of_week)
        
        locale = get_lang(self.env).code
        format_month = lambda d: format_date(self.env, d, 'MMM')
        
        self.env.cr.execute("""
            SELECT move.journal_id,
                   COALESCE(SUM(move.amount_total_signed) FILTER (WHERE invoice_date < %(start_week1)s), 0) AS total_before,
                   COALESCE(SUM(move.amount_total_signed) FILTER (WHERE invoice_date >= %(start_week1)s AND invoice_date < %(start_week2)s), 0) AS total_week1,
                   COALESCE(SUM(move.amount_total_signed) FILTER (WHERE invoice_date >= %(start_week2)s AND invoice_date < %(start_week3)s), 0) AS total_week2,
                   COALESCE(SUM(move.amount_total_signed) FILTER (WHERE invoice_date >= %(start_week3)s AND invoice_date < %(start_week4)s), 0) AS total_week3,
                   COALESCE(SUM(move.amount_total_signed) FILTER (WHERE invoice_date >= %(start_week4)s AND invoice_date < %(start_week5)s), 0) AS total_week4,
                   COALESCE(SUM(move.amount_total_signed) FILTER (WHERE invoice_date >= %(start_week5)s), 0) AS total_after
              FROM account_move move
             WHERE move.journal_id = ANY(%(journal_ids)s)
               AND move.state = 'posted'
               AND move.move_type IN ('out_invoice', 'out_refund')
               AND move.company_id = ANY(%(company_ids)s)
          GROUP BY move.journal_id
        """, {
            'journal_ids': sale_journals.ids,
            'company_ids': self.env.companies.ids,
            'start_week1': first_day_of_week - timedelta(days=7),
            'start_week2': first_day_of_week,
            'start_week3': first_day_of_week + timedelta(days=7),
            'start_week4': first_day_of_week + timedelta(days=14),
            'start_week5': first_day_of_week + timedelta(days=21),
        })
        query_results = {r['journal_id']: r for r in self.env.cr.dictfetchall()}
        
        for journal in sale_journals:
            currency = journal.currency_id or journal.company_id.currency_id
            graph_title, graph_key = journal._graph_title_and_key()
            journal_data = query_results.get(journal.id)
            
            data = []
            data.append({'label': _('Before'), 'type': 'past'})
            for i in range(-1, 3):
                if i == 0:
                    label = _('This Week')
                else:
                    start_week = first_day_of_week + timedelta(days=i*7)
                    end_week = start_week + timedelta(days=6)
                    if start_week.month == end_week.month:
                        label = f"{start_week.day} - {end_week.day} {format_month(end_week)}"
                    else:
                        label = f"{start_week.day} {format_month(start_week)} - {end_week.day} {format_month(end_week)}"
                data.append({'label': label, 'type': 'past' if i < 0 else 'future'})
            data.append({'label': _('After'), 'type': 'future'})
            
            has_sales = journal_data and any(journal_data[k] != 0.0 for k in ['total_before', 'total_week1', 'total_week2', 'total_week3', 'total_week4', 'total_after'])
            
            is_sample_data = not has_sales
            if not is_sample_data:
                data[0]['value'] = currency.round(journal_data['total_before'])
                data[1]['value'] = currency.round(journal_data['total_week1'])
                data[2]['value'] = currency.round(journal_data['total_week2'])
                data[3]['value'] = currency.round(journal_data['total_week3'])
                data[4]['value'] = currency.round(journal_data['total_week4'])
                data[5]['value'] = currency.round(journal_data['total_after'])
                graph_key = 'Sales Volume'
            else:
                for index in range(6):
                    data[index]['type'] = 'o_sample_data'
                    data[index]['value'] = random.randint(0, 20)
                graph_key = _('Sample data')
                
            result[journal.id] = [{
                'values': data,
                'title': graph_title,
                'key': graph_key or 'Sales Volume',
                'is_sample_data': is_sample_data
            }]
            
        return result

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
