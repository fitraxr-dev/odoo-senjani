from odoo import models, fields, api


class AccountMove(models.Model):
    """
    Ekstensi account.move untuk integrasi Xendit Payment.

    Menyimpan referensi pembayaran Xendit pada invoice customer
    yang terbuat otomatis dari Sales Order via webhook Xendit.
    """
    _inherit = 'account.move'

    # Referensi pembayaran dari Xendit (diisi otomatis via webhook SO)
    x_xendit_payment_ref = fields.Char(
        string='Xendit Payment Reference',
        readonly=True,
        copy=False,
        help='ID pembayaran dari Xendit yang terhubung dengan invoice ini. '
             'Diisi otomatis saat Sales Order terbuat via webhook Xendit.',
        tracking=True,
    )

    # Status pembayaran di sisi Xendit
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
        help='Status pembayaran di sistem Xendit.',
        tracking=True,
    )

    # Metode pembayaran Xendit (transfer, QRIS, VA, dll)
    x_xendit_payment_method = fields.Char(
        string='Metode Bayar (Xendit)',
        readonly=True,
        copy=False,
        help='Contoh: BANK_TRANSFER, QRIS, VIRTUAL_ACCOUNT_BNI, dll.',
    )

    @api.depends('x_xendit_payment_ref', 'move_type')
    def _compute_display_xendit_info(self):
        """Apakah perlu tampilkan info Xendit di form."""
        for move in self:
            move.x_show_xendit_info = bool(
                move.x_xendit_payment_ref and move.move_type == 'out_invoice'
            )

    x_show_xendit_info = fields.Boolean(
        compute='_compute_display_xendit_info',
        string='Tampilkan Info Xendit',
    )

    def action_senjani_confirm_invoice(self):
        """
        Aksi batch: konfirmasi invoice dari status Draft ke Posted.
        Digunakan dari list view untuk efisiensi kerja tim accounting.
        """
        draft_invoices = self.filtered(
            lambda m: m.state == 'draft' and m.move_type in ('out_invoice', 'out_refund')
        )
        if draft_invoices:
            draft_invoices.action_post()
        return True

    def action_senjani_confirm_bill(self):
        """
        Aksi batch: konfirmasi vendor bill dari status Draft ke Posted.
        Digunakan dari list view untuk efisiensi kerja tim accounting.
        """
        draft_bills = self.filtered(
            lambda m: m.state == 'draft' and m.move_type in ('in_invoice', 'in_refund')
        )
        if draft_bills:
            draft_bills.action_post()
        return True

    def action_post(self):
        """
        Override action_post untuk otomatis mencocokkan pembayaran Xendit.
        """
        res = super(AccountMove, self).action_post()
        self._auto_link_xendit_payment()
        return res

    def _auto_link_xendit_payment(self):
        """
        Fungsi kustom untuk otomatis mencari outstanding payment di Jurnal Xendit
        berdasarkan referensi Sales Order (invoice_origin) dan merekonsiliasikannya.
        """
        for invoice in self:
            if invoice.move_type != 'out_invoice' or invoice.state != 'posted' or invoice.payment_state not in ('not_paid', 'partial'):
                continue

            # Cari referensi Sales Order (misal: S00050)
            origin = invoice.invoice_origin or invoice.ref
            if not origin:
                continue

            # Cari baris piutang (receivable) yang belum direkonsiliasi di Jurnal Xendit (XNDT)
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
                # Ambil line piutang dari invoice ini sendiri
                invoice_receivable_line = invoice.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
                )
                if invoice_receivable_line:
                    # Lakukan rekonsiliasi otomatis
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
        Override open_action agar klik pada kartu dashboard (Faktur Penjualan / Faktur Pembelian)
        langsung membuka aksi kustom kita dengan filter kustom dan Bahasa Indonesia.
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
        return super(AccountJournal, self).open_action()
