import logging

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CancelWizard(models.TransientModel):
    _name = 'sanal.pos.cancel.wizard'
    _description = 'Sanal POS İptal Wizard'

    transaction_id = fields.Many2one(
        'payment.transaction',
        string="İşlem",
        required=True,
        readonly=True,
    )
    amount = fields.Float(
        string="İşlem Tutarı",
        readonly=True,
    )
    reason = fields.Text(
        string="İptal Nedeni",
    )

    def action_cancel(self):
        """İptal işlemini başlat."""
        self.ensure_one()
        tx = self.transaction_id

        if not tx.sanal_pos_order_id:
            raise UserError(_("Bu işlem için banka sipariş numarası bulunamadı."))

        if tx.state != 'done':
            raise UserError(_("Yalnızca tamamlanmış işlemler iptal edilebilir."))

        provider = tx.provider_id
        gateway = provider._sanal_pos_get_gateway()

        order = {
            'order_id': tx.sanal_pos_order_id,
            'amount': tx.amount,
            'currency': tx.currency_id.name,
            'auth_code': tx.sanal_pos_auth_code,
        }

        try:
            result = gateway.cancel(order)
        except Exception as e:
            raise UserError(_("İptal isteği gönderilemedi: %s", str(e)))

        if result.get('status') == 'success':
            tx.write({
                'sanal_pos_cancel_date': fields.Datetime.now(),
            })
            tx._sanal_pos_log(
                'cancel', is_success=True,
                request_data=str(order),
                response_data=str(result),
            )
            # Transaction durumunu iptal olarak ayarla
            tx._set_canceled()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("İptal Başarılı"),
                    'message': _("İşlem başarıyla iptal edildi."),
                    'type': 'success',
                    'sticky': False,
                },
            }
        else:
            error_msg = result.get('error_message', 'Bilinmeyen hata')
            tx._sanal_pos_log(
                'cancel', is_success=False,
                request_data=str(order),
                response_data=str(result),
                error_message=error_msg,
            )
            raise UserError(_("İptal başarısız: %s", error_msg))
