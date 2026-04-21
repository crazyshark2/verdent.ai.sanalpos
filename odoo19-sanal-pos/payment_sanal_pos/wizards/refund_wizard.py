import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class RefundWizard(models.TransientModel):
    _name = 'sanal.pos.refund.wizard'
    _description = 'Sanal POS İade Wizard'

    transaction_id = fields.Many2one(
        'payment.transaction',
        string="İşlem",
        required=True,
        readonly=True,
    )
    original_amount = fields.Float(
        string="Orijinal Tutar",
        readonly=True,
    )
    already_refunded = fields.Float(
        string="Daha Önce İade Edilen",
        readonly=True,
    )
    max_refund_amount = fields.Float(
        string="Maksimum İade Tutarı",
        readonly=True,
    )
    refund_type = fields.Selection(
        [
            ('full', "Tam İade"),
            ('partial', "Kısmi İade"),
        ],
        string="İade Tipi",
        default='full',
        required=True,
    )
    refund_amount = fields.Float(
        string="İade Tutarı",
    )
    reason = fields.Text(
        string="İade Nedeni",
    )

    @api.onchange('refund_type')
    def _onchange_refund_type(self):
        if self.refund_type == 'full':
            self.refund_amount = self.max_refund_amount

    def action_refund(self):
        """İade işlemini başlat."""
        self.ensure_one()
        tx = self.transaction_id

        if not tx.sanal_pos_order_id:
            raise UserError(_("Bu işlem için banka sipariş numarası bulunamadı."))

        if tx.state != 'done':
            raise UserError(_("Yalnızca tamamlanmış işlemler iade edilebilir."))

        amount = self.refund_amount
        if self.refund_type == 'full':
            amount = self.max_refund_amount

        if amount <= 0:
            raise UserError(_("İade tutarı 0'dan büyük olmalıdır."))

        if amount > self.max_refund_amount:
            raise UserError(
                _("İade tutarı maksimum tutarı (%(max)s) aşamaz.",
                  max=self.max_refund_amount)
            )

        provider = tx.provider_id
        gateway = provider._sanal_pos_get_gateway()

        order = {
            'order_id': tx.sanal_pos_order_id,
            'amount': amount,
            'currency': tx.currency_id.name,
            'auth_code': tx.sanal_pos_auth_code,
        }

        try:
            result = gateway.refund(order)
        except Exception as e:
            raise UserError(_("İade isteği gönderilemedi: %s", str(e)))

        if result.get('status') == 'success':
            tx.write({
                'sanal_pos_refund_amount': (tx.sanal_pos_refund_amount or 0) + amount,
                'sanal_pos_refund_date': fields.Datetime.now(),
            })
            tx._sanal_pos_log(
                'refund', is_success=True,
                request_data=str(order),
                response_data=str(result),
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("İade Başarılı"),
                    'message': _("%(amount)s %(currency)s tutarında iade yapıldı.",
                                 amount=amount, currency=tx.currency_id.name),
                    'type': 'success',
                    'sticky': False,
                },
            }
        else:
            error_msg = result.get('error_message', 'Bilinmeyen hata')
            tx._sanal_pos_log(
                'refund', is_success=False,
                request_data=str(order),
                response_data=str(result),
                error_message=error_msg,
            )
            raise UserError(_("İade başarısız: %s", error_msg))
