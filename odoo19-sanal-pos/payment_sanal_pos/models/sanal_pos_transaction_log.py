from odoo import fields, models


class SanalPosTransactionLog(models.Model):
    _name = 'sanal.pos.transaction.log'
    _description = 'Sanal POS İşlem Logu'
    _order = 'create_date desc'

    transaction_id = fields.Many2one(
        'payment.transaction',
        string="İşlem",
        index=True,
        ondelete='cascade',
    )
    provider_id = fields.Many2one(
        'payment.provider',
        string="Ödeme Sağlayıcı",
        index=True,
    )
    log_type = fields.Selection(
        [
            ('request', "API İsteği"),
            ('response', "API Yanıtı"),
            ('3d_redirect', "3D Yönlendirme"),
            ('3d_callback', "3D Geri Dönüş"),
            ('error', "Hata"),
            ('refund', "İade"),
            ('cancel', "İptal"),
            ('status_query', "Durum Sorgulama"),
        ],
        string="Log Tipi",
        required=True,
    )
    direction = fields.Selection(
        [
            ('outgoing', "Giden"),
            ('incoming', "Gelen"),
        ],
        string="Yön",
    )
    url = fields.Char(string="Endpoint URL")
    request_data = fields.Text(string="İstek Verisi")
    response_data = fields.Text(string="Yanıt Verisi")
    http_status = fields.Integer(string="HTTP Durum Kodu")
    duration_ms = fields.Integer(string="Süre (ms)")
    is_success = fields.Boolean(string="Başarılı")
    error_message = fields.Text(string="Hata Mesajı")
    ip_address = fields.Char(string="IP Adresi")
