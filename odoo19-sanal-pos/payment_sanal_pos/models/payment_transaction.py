import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

SANAL_POS_PROVIDER_CODES = [
    'sanal_pos_garanti',
    'sanal_pos_estv3',
    'sanal_pos_payflex',
    'sanal_pos_posnet',
]


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # --- Sanal POS Banka Yanıt Bilgileri ---
    sanal_pos_order_id = fields.Char(
        string="Banka Sipariş No",
        readonly=True,
        index=True,
    )
    sanal_pos_auth_code = fields.Char(
        string="Yetkilendirme Kodu",
        readonly=True,
    )
    sanal_pos_rrn = fields.Char(
        string="RRN",
        readonly=True,
        help="Retrieval Reference Number",
    )
    sanal_pos_transaction_id = fields.Char(
        string="Banka Transaction ID",
        readonly=True,
    )
    sanal_pos_host_ref_num = fields.Char(
        string="Host Referans No",
        readonly=True,
    )

    # --- 3D Secure Bilgileri ---
    sanal_pos_3d_status = fields.Selection(
        [
            ('not_enrolled', "Kart Kayıtlı Değil"),
            ('enrolled', "Kart Kayıtlı"),
            ('authenticated', "Doğrulandı"),
            ('attempted', "Denendi"),
            ('failed', "Başarısız"),
        ],
        string="3D Secure Durumu",
        readonly=True,
    )
    sanal_pos_md_status = fields.Char(
        string="MD Status",
        readonly=True,
    )
    sanal_pos_eci = fields.Char(string="ECI", readonly=True)
    sanal_pos_cavv = fields.Char(string="CAVV", readonly=True)
    sanal_pos_xid = fields.Char(string="XID", readonly=True)

    # --- Taksit Bilgileri ---
    sanal_pos_installment_count = fields.Integer(
        string="Taksit Sayısı",
        default=1,
        readonly=True,
    )
    sanal_pos_installment_amount = fields.Float(
        string="Taksit Tutarı",
        readonly=True,
    )
    sanal_pos_total_with_interest = fields.Float(
        string="Toplam Tutar (Faizli)",
        readonly=True,
    )
    sanal_pos_interest_rate = fields.Float(
        string="Faiz Oranı (%)",
        readonly=True,
    )

    # --- Kart Bilgileri (Maskeli) ---
    sanal_pos_card_type = fields.Selection(
        [
            ('visa', "Visa"),
            ('mastercard', "Mastercard"),
            ('troy', "Troy"),
            ('amex', "American Express"),
        ],
        string="Kart Tipi",
        readonly=True,
    )
    sanal_pos_masked_pan = fields.Char(
        string="Maskeli Kart No",
        readonly=True,
        help="Örn: 4531****1234",
    )
    sanal_pos_card_bank = fields.Char(
        string="Kart Bankası",
        readonly=True,
    )

    # --- İade/İptal ---
    sanal_pos_refund_amount = fields.Float(
        string="İade Edilen Tutar",
        readonly=True,
    )
    sanal_pos_refund_date = fields.Datetime(
        string="İade Tarihi",
        readonly=True,
    )
    sanal_pos_cancel_date = fields.Datetime(
        string="İptal Tarihi",
        readonly=True,
    )
    sanal_pos_original_tx_id = fields.Many2one(
        'payment.transaction',
        string="Orijinal İşlem",
        readonly=True,
        ondelete='set null',
    )

    # --- Ham Banka Verisi (Debug) ---
    sanal_pos_raw_request = fields.Text(
        string="Gönderilen Request",
        readonly=True,
    )
    sanal_pos_raw_response = fields.Text(
        string="Banka Yanıtı",
        readonly=True,
    )
    sanal_pos_error_code = fields.Char(
        string="Hata Kodu",
        readonly=True,
    )
    sanal_pos_error_message = fields.Text(
        string="Hata Mesajı",
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # OVERRIDES
    # -------------------------------------------------------------------------

    def _get_specific_rendering_values(self, processing_values):
        """Override: 3D Secure form verileri hazırla.

        Banka 3D sayfasına yönlendirme için gerekli form alanlarını döndürür.
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code not in SANAL_POS_PROVIDER_CODES:
            return res

        provider = self.provider_id
        gateway = provider._sanal_pos_get_gateway()

        # Benzersiz sipariş ID oluştur
        order_id = gateway._generate_order_id()
        self.sanal_pos_order_id = order_id

        order = {
            'order_id': order_id,
            'amount': self.amount,
            'currency': self.currency_id.name,
            'installment': self.sanal_pos_installment_count or 1,
            'description': self.reference,
            'success_url': '/payment/sanal_pos/3d_return',
            'fail_url': '/payment/sanal_pos/3d_fail',
            'ip': processing_values.get('partner_ip', '127.0.0.1'),
            'email': processing_values.get('partner_email', ''),
        }

        card = processing_values.get('sanal_pos_card_data', {})

        try:
            form_data = gateway.make_3d_form_data(order, card)
            self._sanal_pos_log(
                'request', request_data=str(form_data.get('inputs', {})),
                url=form_data.get('gateway_url', ''),
            )
            res.update({
                'api_url': form_data['gateway_url'],
                'sanal_pos_form_inputs': form_data['inputs'],
            })
        except Exception as e:
            _logger.error("3D form verisi oluşturulamadı: %s", e, exc_info=True)
            raise ValidationError(
                _("Ödeme formu hazırlanırken bir hata oluştu: %s", str(e))
            )

        return res

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Override: 3D callback'ten gelen veriden transaction bul."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code not in SANAL_POS_PROVIDER_CODES:
            return tx

        # Sipariş ID'ye göre transaction bul
        order_id = self._sanal_pos_extract_order_id(provider_code, notification_data)
        if order_id:
            tx = self.search(
                [('sanal_pos_order_id', '=', order_id),
                 ('provider_code', '=', provider_code)],
                limit=1,
            )
        if not tx:
            raise ValidationError(
                _("Sanal POS: İşlem bulunamadı (order_id: %s)", order_id)
            )
        return tx

    def _process_notification_data(self, notification_data):
        """Override: Banka yanıtını işle, durumu güncelle."""
        super()._process_notification_data(notification_data)
        if self.provider_code not in SANAL_POS_PROVIDER_CODES:
            return

        provider = self.provider_id
        gateway = provider._sanal_pos_get_gateway()

        try:
            # Hash doğrulama
            if not gateway.validate_hash(notification_data):
                self._sanal_pos_log(
                    'error', error_message="Hash doğrulaması başarısız",
                    response_data=str(notification_data),
                )
                self._set_error(_("Güvenlik doğrulaması başarısız (hash mismatch)."))
                return

            # 3D callback işle
            result = gateway.process_3d_callback(notification_data)

            # 3D bilgilerini kaydet
            self.write({
                'sanal_pos_md_status': result.get('md_status'),
                'sanal_pos_3d_status': self._sanal_pos_map_3d_status(
                    result.get('md_status')
                ),
                'sanal_pos_eci': result.get('eci'),
                'sanal_pos_cavv': result.get('cavv'),
                'sanal_pos_xid': result.get('xid'),
                'sanal_pos_raw_response': str(notification_data),
            })

            if result.get('status') != 'success':
                error_msg = result.get('error_message', 'Bilinmeyen hata')
                self._sanal_pos_log(
                    '3d_callback', is_success=False,
                    error_message=error_msg,
                    response_data=str(notification_data),
                )
                self._set_error(
                    _("3D doğrulama başarısız: %s", error_msg)
                )
                return

            # 3D_SECURE modeli ise provizyon al
            if provider.sanal_pos_payment_model == '3d_secure':
                order = {
                    'order_id': self.sanal_pos_order_id,
                    'amount': self.amount,
                    'currency': self.currency_id.name,
                    'installment': self.sanal_pos_installment_count or 1,
                }
                provision_result = gateway.complete_3d_payment(
                    notification_data, order
                )

                self.write({
                    'sanal_pos_auth_code': provision_result.get('auth_code'),
                    'sanal_pos_rrn': provision_result.get('rrn'),
                    'sanal_pos_transaction_id': provision_result.get('transaction_id'),
                    'sanal_pos_host_ref_num': provision_result.get('host_ref_num'),
                    'sanal_pos_raw_request': provision_result.get('raw_request', ''),
                    'sanal_pos_raw_response': provision_result.get('raw_response', ''),
                })

                if provision_result.get('status') != 'success':
                    error_msg = provision_result.get(
                        'error_message', 'Provizyon alınamadı'
                    )
                    self._sanal_pos_log(
                        'response', is_success=False,
                        error_message=error_msg,
                        response_data=str(provision_result),
                    )
                    self._set_error(
                        _("Ödeme provizyonu başarısız: %s", error_msg)
                    )
                    return
            else:
                # 3D_PAY modeli - 3D ile birlikte ödeme tamamlanır
                self.write({
                    'sanal_pos_auth_code': result.get('auth_code'),
                    'sanal_pos_transaction_id': result.get('transaction_id'),
                })

            # Başarılı
            self._sanal_pos_log(
                '3d_callback', is_success=True,
                response_data=str(notification_data),
            )
            self._set_done()

        except Exception as e:
            _logger.error(
                "Sanal POS notification işleme hatası (tx=%s): %s",
                self.reference, e, exc_info=True,
            )
            self._sanal_pos_log(
                'error', error_message=str(e),
                response_data=str(notification_data),
            )
            self._set_error(
                _("Ödeme işlenirken hata oluştu: %s", str(e))
            )

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------

    @staticmethod
    def _sanal_pos_extract_order_id(provider_code, data):
        """Callback verisinden sipariş ID çıkar (gateway tipine göre)."""
        # Garanti: orderid, EstV3: oid, PayFlex: OrderId, PosNet: orderID
        for key in ('orderid', 'oid', 'OrderId', 'orderID',
                     'orderId', 'ReturnOid', 'md'):
            if key in data:
                return data[key]
        return None

    @staticmethod
    def _sanal_pos_map_3d_status(md_status):
        """MD status kodunu 3D secure durumuna dönüştür."""
        status_map = {
            '1': 'authenticated',
            '2': 'attempted',
            '3': 'not_enrolled',
            '4': 'not_enrolled',
            '5': 'failed',
            '6': 'failed',
            '7': 'failed',
            '8': 'failed',
            '0': 'failed',
        }
        return status_map.get(str(md_status), 'failed')

    def _sanal_pos_log(self, log_type, **kwargs):
        """Transaction log kaydı oluştur."""
        self.ensure_one()
        try:
            self.env['sanal.pos.transaction.log'].sudo().create({
                'transaction_id': self.id,
                'provider_id': self.provider_id.id,
                'log_type': log_type,
                'direction': kwargs.get('direction', 'incoming'),
                'url': kwargs.get('url', ''),
                'request_data': kwargs.get('request_data', ''),
                'response_data': kwargs.get('response_data', ''),
                'http_status': kwargs.get('http_status', 0),
                'duration_ms': kwargs.get('duration_ms', 0),
                'is_success': kwargs.get('is_success', False),
                'error_message': kwargs.get('error_message', ''),
                'ip_address': kwargs.get('ip_address', ''),
            })
        except Exception as e:
            _logger.warning("Transaction log yazılamadı: %s", e)
