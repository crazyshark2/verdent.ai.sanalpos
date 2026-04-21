import json
import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SanalPosController(http.Controller):
    """Sanal POS ana controller.

    3D Secure callback, webhook ve durum sorgulama endpoint'leri.
    """

    @http.route(
        '/payment/sanal_pos/3d_return',
        type='http', auth='public', methods=['POST', 'GET'],
        csrf=False, save_session=False, website=True,
    )
    def sanal_pos_3d_return(self, **post):
        """3D Secure başarılı callback.

        Banka 3D sayfasından yönlendirme sonrası çağrılır.
        1. Transaction bul (order_id ile)
        2. Notification verisini işle
        3. Kullanıcıyı ödeme durumu sayfasına yönlendir
        """
        _logger.info(
            "Sanal POS 3D callback alındı: %s",
            {k: v for k, v in post.items() if 'card' not in k.lower() and 'pan' not in k.lower()},
        )

        try:
            # Provider kodunu belirle
            provider_code = self._detect_provider_code(post)
            if not provider_code:
                _logger.error("Provider kodu tespit edilemedi: %s", post.keys())
                return request.redirect('/payment/status')

            # Transaction bul ve notification işle
            tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
                provider_code, post,
            )
            tx_sudo._process_notification_data(post)

        except Exception as e:
            _logger.error("3D callback işleme hatası: %s", e, exc_info=True)

        return request.redirect('/payment/status')

    @http.route(
        '/payment/sanal_pos/3d_fail',
        type='http', auth='public', methods=['POST', 'GET'],
        csrf=False, save_session=False, website=True,
    )
    def sanal_pos_3d_fail(self, **post):
        """3D Secure başarısız callback.

        Banka 3D doğrulama başarısız olduğunda çağrılır.
        """
        _logger.warning(
            "Sanal POS 3D başarısız callback: %s",
            {k: v for k, v in post.items() if 'card' not in k.lower()},
        )

        try:
            provider_code = self._detect_provider_code(post)
            if provider_code:
                tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
                    provider_code, post,
                )
                # Hata mesajını ayarla
                error_msg = (
                    post.get('ErrMsg')
                    or post.get('errMsg')
                    or post.get('mdErrorMsg')
                    or post.get('ErrorMessage')
                    or '3D doğrulama başarısız'
                )
                tx_sudo.write({
                    'sanal_pos_raw_response': json.dumps(post, ensure_ascii=False),
                    'sanal_pos_error_message': error_msg,
                    'sanal_pos_md_status': post.get('mdStatus', post.get('MdStatus', '0')),
                })
                tx_sudo._set_error(error_msg)
                tx_sudo._sanal_pos_log(
                    'error',
                    error_message=error_msg,
                    response_data=json.dumps(post, ensure_ascii=False),
                )
        except Exception as e:
            _logger.error("3D fail callback işleme hatası: %s", e, exc_info=True)

        return request.redirect('/payment/status')

    @http.route(
        '/payment/sanal_pos/webhook',
        type='json', auth='public', methods=['POST'],
        csrf=False,
    )
    def sanal_pos_webhook(self, **post):
        """Banka webhook callback (asenkron bildirim).

        Bazı bankalar ödeme sonucunu asenkron olarak bildirir.
        """
        _logger.info("Sanal POS webhook alındı")
        data = request.get_json_data() if hasattr(request, 'get_json_data') else post

        try:
            provider_code = self._detect_provider_code(data)
            if provider_code:
                tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
                    provider_code, data,
                )
                tx_sudo._process_notification_data(data)
                return {'status': 'ok'}
        except Exception as e:
            _logger.error("Webhook işleme hatası: %s", e, exc_info=True)

        return {'status': 'error'}

    @http.route(
        '/payment/sanal_pos/refund',
        type='json', auth='user', methods=['POST'],
    )
    def sanal_pos_refund(self, transaction_id, amount=None, **kwargs):
        """Admin panelinden iade başlatma.

        :param transaction_id: payment.transaction ID
        :param amount: İade tutarı (None = tam iade)
        """
        tx = request.env['payment.transaction'].browse(int(transaction_id))
        if not tx.exists():
            return {'status': 'error', 'message': 'İşlem bulunamadı'}

        provider = tx.provider_id
        gateway = provider._sanal_pos_get_gateway()

        refund_amount = float(amount) if amount else tx.amount

        order = {
            'order_id': tx.sanal_pos_order_id,
            'amount': refund_amount,
            'currency': tx.currency_id.name,
            'auth_code': tx.sanal_pos_auth_code,
        }

        try:
            result = gateway.refund(order)

            tx.write({
                'sanal_pos_refund_amount': (tx.sanal_pos_refund_amount or 0) + refund_amount,
                'sanal_pos_refund_date': fields.Datetime.now(),
            })
            tx._sanal_pos_log(
                'refund',
                is_success=result.get('status') == 'success',
                request_data=str(order),
                response_data=str(result),
                error_message=result.get('error_message', ''),
            )

            return {
                'status': result.get('status', 'fail'),
                'message': result.get('error_message', 'İade başarılı'),
                'refund_amount': refund_amount,
            }
        except Exception as e:
            _logger.error("İade hatası: %s", e, exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route(
        '/payment/sanal_pos/cancel',
        type='json', auth='user', methods=['POST'],
    )
    def sanal_pos_cancel(self, transaction_id, **kwargs):
        """Admin panelinden iptal işlemi."""
        tx = request.env['payment.transaction'].browse(int(transaction_id))
        if not tx.exists():
            return {'status': 'error', 'message': 'İşlem bulunamadı'}

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

            if result.get('status') == 'success':
                tx.write({
                    'sanal_pos_cancel_date': fields.Datetime.now(),
                })
                tx._set_canceled()

            tx._sanal_pos_log(
                'cancel',
                is_success=result.get('status') == 'success',
                request_data=str(order),
                response_data=str(result),
                error_message=result.get('error_message', ''),
            )

            return {
                'status': result.get('status', 'fail'),
                'message': result.get('error_message', 'İptal başarılı'),
            }
        except Exception as e:
            _logger.error("İptal hatası: %s", e, exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route(
        '/payment/sanal_pos/status',
        type='json', auth='user', methods=['POST'],
    )
    def sanal_pos_query_status(self, transaction_id, **kwargs):
        """İşlem durum sorgulama."""
        tx = request.env['payment.transaction'].browse(int(transaction_id))
        if not tx.exists():
            return {'status': 'error', 'message': 'İşlem bulunamadı'}

        provider = tx.provider_id
        gateway = provider._sanal_pos_get_gateway()

        order = {
            'order_id': tx.sanal_pos_order_id,
        }

        try:
            result = gateway.query_status(order)
            tx._sanal_pos_log(
                'status_query',
                is_success=result.get('status') == 'success',
                response_data=str(result),
            )
            return result
        except Exception as e:
            _logger.error("Durum sorgulama hatası: %s", e, exc_info=True)
            return {'status': 'error', 'message': str(e)}

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @staticmethod
    def _detect_provider_code(data):
        """Callback verisinden provider kodunu tespit et.

        Her gateway'in callback'inde farklı parametreler bulunur.
        """
        # Garanti: secure3dsecuritylevel, terminalid
        if data.get('secure3dsecuritylevel') or data.get('terminalid'):
            return 'sanal_pos_garanti'

        # EstV3: clientid, storetype
        if data.get('clientid') or data.get('storetype'):
            return 'sanal_pos_estv3'

        # PayFlex: MerchantId, TransactionType
        if data.get('MerchantId') or data.get('TransactionType'):
            return 'sanal_pos_payflex'

        # PosNet: MerchantPacket, BankPacket
        if data.get('MerchantPacket') or data.get('BankPacket'):
            return 'sanal_pos_posnet'

        # Genel: oid/orderid/OrderId ile transaction'dan bul
        for key in ('oid', 'orderid', 'OrderId', 'orderID'):
            if data.get(key):
                tx = request.env['payment.transaction'].sudo().search([
                    ('sanal_pos_order_id', '=', data[key]),
                ], limit=1)
                if tx:
                    return tx.provider_code

        return None
