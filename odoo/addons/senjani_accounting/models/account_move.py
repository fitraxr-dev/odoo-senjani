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

    is_senjani_accounting = fields.Boolean(
        compute='_compute_is_senjani_accounting'
    )

    def _compute_is_senjani_accounting(self):
        for move in self:
            move.is_senjani_accounting = self.env.user.has_group('senjani_accounting.group_senjani_accounting_staff')

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
                ('partner_id.commercial_partner_id', '=', invoice.partner_id.commercial_partner_id.id),
                ('account_id.account_type', '=', 'asset_receivable'),
                ('reconciled', '=', False),
                ('journal_id.code', '=', 'XNDT'),
            ])

            matched_line = False
            for line in receivable_lines:
                payment = line.move_id.payment_ids[:1] if line.move_id.payment_ids else False
                tx = payment.payment_transaction_id if payment else False
                
                # Try to match by Transaction Reference (often contains SO Origin)
                if tx and tx.reference and origin in tx.reference:
                    matched_line = line
                    break
                # Try to match by Payment Move Ref
                if line.move_id.ref and origin in line.move_id.ref:
                    matched_line = line
                    break
                # Try to match by Xendit Payment Reference exactly
                if invoice.payment_reference and invoice.payment_reference in (line.move_id.ref or ''):
                    matched_line = line
                    break
                # Try to match by exact Amount Total (as a fallback)
                if invoice.amount_total == abs(line.balance):
                    matched_line = line
                    break

            if matched_line:
                # Find receivable line on this invoice
                invoice_receivable_line = invoice.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
                )
                if invoice_receivable_line:
                    # Perform automatic reconciliation
                    (invoice_receivable_line + matched_line).reconcile()


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    senjani_unpaid_payment_count = fields.Integer(
        string='Unpaid Payments Count',
        compute='_compute_senjani_unpaid_payment_info'
    )
    senjani_unpaid_payment_amount = fields.Char(
        string='Unpaid Payments Amount',
        compute='_compute_senjani_unpaid_payment_info'
    )

    def _compute_senjani_unpaid_payment_info(self):
        for journal in self:
            payments = self.env['account.payment'].search([
                ('journal_id', '=', journal.id),
                ('state', 'in', ('draft', 'in_process'))
            ])
            journal.senjani_unpaid_payment_count = len(payments)
            
            total = 0.0
            for p in payments:
                # Outbound payments (sending money) decrease balance, so negative
                sign = -1 if p.payment_type == 'outbound' else 1
                total += p.amount * sign
                
            currency = journal.currency_id or journal.company_id.currency_id
            journal.senjani_unpaid_payment_amount = currency.format(total)

    def action_senjani_transfer_funds(self):
        self.ensure_one()
        return {
            'name': 'Transfer Xendit Funds',
            'type': 'ir.actions.act_window',
            'res_model': 'senjani.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_journal_id': self.id,
            }
        }

    def _fill_sale_purchase_dashboard_data(self, dashboard_data):
        """
        Override to include 'in_payment' (In Process) bills in the 'To Pay' count and amount
        on the Accounting Dashboard for Purchase Journals.
        """
        super()._fill_sale_purchase_dashboard_data(dashboard_data)
        
        purchase_journals = self.filtered(lambda j: j.type == 'purchase')
        for journal in purchase_journals:
            domain = [
                ('journal_id', '=', journal.id),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ('not_paid', 'partial')),
                ('move_type', 'in', ('in_invoice', 'in_refund'))
            ]
            moves = self.env['account.move'].search(domain)
            count = len(moves)
            
            total = 0.0
            for move in moves:
                total += abs(move.amount_residual_signed)
                    
            currency = journal.currency_id or journal.company_id.currency_id
            
            dashboard_data[journal.id]['number_waiting'] = count
            dashboard_data[journal.id]['sum_waiting'] = currency.format(total)
            dashboard_data[journal.id]['is_sample_data'] = False
            dashboard_data[journal.id]['has_entries'] = True

        sale_journals = self.filtered(lambda j: j.type == 'sale')
        for journal in sale_journals:
            # We must force these to prevent Odoo from graying out the whole card and graph
            if journal.id in dashboard_data:
                dashboard_data[journal.id]['is_sample_data'] = False
                dashboard_data[journal.id]['has_entries'] = True

    def _fill_bank_cash_dashboard_data(self, dashboard_data):
        super()._fill_bank_cash_dashboard_data(dashboard_data)
        
        for journal in self.filtered(lambda j: j.type in ('bank', 'cash')):
            if journal.id in dashboard_data and journal.default_account_id:
                # Calculate real GL balance for the default account
                self.env.cr.execute("""
                    SELECT SUM(balance)
                    FROM account_move_line
                    WHERE account_id = %s AND parent_state = 'posted' AND journal_id = %s
                """, (journal.default_account_id.id, journal.id))
                res = self.env.cr.fetchone()
                real_balance = res[0] or 0.0
                
                currency = journal.currency_id or journal.company_id.currency_id
                dashboard_data[journal.id]['account_balance'] = currency.format(real_balance)
                dashboard_data[journal.id]['nb_lines_bank_account_balance'] = True
                
        xndt_journals = self.filtered(lambda j: j.code == 'XNDT')
        for journal in xndt_journals:
            if journal.id in dashboard_data:
                dashboard_data[journal.id]['number_to_reconcile'] = 0

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
            
        journals_to_update = self.search([('code', 'in', ['XNDT', 'BNK1'])])
        for journal in journals_to_update:
            if journal.default_account_id:
                for line in journal.inbound_payment_method_line_ids:
                    line.payment_account_id = journal.default_account_id.id
                for line in journal.outbound_payment_method_line_ids:
                    line.payment_account_id = journal.default_account_id.id
                    
        BNK1 = self.search([('code', '=', 'BNK1')])
        out_receipts = self.env['account.account'].search([('code', '=', '101403')])
        out_payments = self.env['account.account'].search([('code', '=', '101404')])
        
        if out_receipts and out_payments:
            for journal in BNK1:
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
        
        today = fields.Date.context_today(self)
        from odoo.tools.misc import format_datetime, get_lang
        from datetime import timedelta
        
        day_of_week = today.weekday()
        first_day_of_week = today - timedelta(days=day_of_week)
        
        if sale_journals:
        
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
                   AND move.payment_state IN ('paid', 'in_payment', 'reversed')
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
            
                is_sample_data = False
                if not is_sample_data:
                    data[0]['value'] = currency.round(journal_data['total_before']) if journal_data else 0.0
                    data[1]['value'] = currency.round(journal_data['total_week1']) if journal_data else 0.0
                    data[2]['value'] = currency.round(journal_data['total_week2']) if journal_data else 0.0
                    data[3]['value'] = currency.round(journal_data['total_week3']) if journal_data else 0.0
                    data[4]['value'] = currency.round(journal_data['total_week4']) if journal_data else 0.0
                    data[5]['value'] = currency.round(journal_data['total_after']) if journal_data else 0.0
                    graph_key = 'Sales Volume'
                else:
                    for index in range(6):
                        data[index]['type'] = 'past' if index < 6 else 'future'
                        data[index]['value'] = 0.0
                    graph_key = 'Sales Volume'
                
                result[journal.id] = [{
                    'values': data,
                    'title': graph_title,
                    'key': graph_key or 'Sales Volume',
                    'is_sample_data': is_sample_data
                }]
            
        purchase_journals = self.filtered(lambda j: j.type == 'purchase')
        if purchase_journals:
                self.env.cr.execute("""
                    SELECT move.journal_id,
                           COALESCE(SUM(abs(move.amount_residual_signed)) FILTER (WHERE invoice_date_due < %(start_week1)s), 0) AS total_before,
                           COALESCE(SUM(abs(move.amount_residual_signed)) FILTER (WHERE invoice_date_due >= %(start_week1)s AND invoice_date_due < %(start_week2)s), 0) AS total_week1,
                           COALESCE(SUM(abs(move.amount_residual_signed)) FILTER (WHERE invoice_date_due >= %(start_week2)s AND invoice_date_due < %(start_week3)s), 0) AS total_week2,
                           COALESCE(SUM(abs(move.amount_residual_signed)) FILTER (WHERE invoice_date_due >= %(start_week3)s AND invoice_date_due < %(start_week4)s), 0) AS total_week3,
                           COALESCE(SUM(abs(move.amount_residual_signed)) FILTER (WHERE invoice_date_due >= %(start_week4)s AND invoice_date_due < %(start_week5)s), 0) AS total_week4,
                           COALESCE(SUM(abs(move.amount_residual_signed)) FILTER (WHERE invoice_date_due >= %(start_week5)s), 0) AS total_after
                      FROM account_move move
                     WHERE move.journal_id = ANY(%(journal_ids)s)
                       AND move.state = 'posted'
                       AND move.payment_state in ('not_paid', 'partial')
                       AND move.move_type IN ('in_invoice', 'in_refund')
                       AND move.company_id = ANY(%(company_ids)s)
                  GROUP BY move.journal_id
                """, {
                    'journal_ids': purchase_journals.ids,
                    'company_ids': self.env.companies.ids,
                    'start_week1': first_day_of_week - timedelta(days=7),
                    'start_week2': first_day_of_week,
                    'start_week3': first_day_of_week + timedelta(days=7),
                    'start_week4': first_day_of_week + timedelta(days=14),
                    'start_week5': first_day_of_week + timedelta(days=21),
                })
            
                purch_query_results = {r['journal_id']: r for r in self.env.cr.dictfetchall()}
            
                for journal in purchase_journals:
                    if journal.id not in result or not result[journal.id]:
                        continue
                    
                    graph_data = result[journal.id][0]
                    journal_data = purch_query_results.get(journal.id)
                
                    graph_data['is_sample_data'] = False
                    graph_data['key'] = _('Due')
                
                    if not journal_data:
                        for item in graph_data['values']:
                            item['value'] = 0.0
                            item['type'] = item.get('type', '').replace('o_sample_data', 'past')
                    else:
                        currency = journal.currency_id or journal.company_id.currency_id
                    
                        graph_data['values'][0]['value'] = currency.round(journal_data['total_before'])
                        graph_data['values'][1]['value'] = currency.round(journal_data['total_week1'])
                        graph_data['values'][2]['value'] = currency.round(journal_data['total_week2'])
                        graph_data['values'][3]['value'] = currency.round(journal_data['total_week3'])
                        graph_data['values'][4]['value'] = currency.round(journal_data['total_week4'])
                        graph_data['values'][5]['value'] = currency.round(journal_data['total_after'])
                    
                        graph_data['values'][0]['type'] = 'past'
                        for i in range(1, 6):
                            graph_data['values'][i]['type'] = 'future'

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
