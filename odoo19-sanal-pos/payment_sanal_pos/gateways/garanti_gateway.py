import logging

from .base_gateway import BaseGateway
from .hash_helper import HashHelper
from .request_builder import RequestBuilder
from .response_parser import ResponseParser

_logger = logging.getLogger(__name__)


class GarantiGateway(BaseGateway):
    """Garanti BBVA Sanal POS Gateway.

    API: XML tabanlı, SHA512 hash.
    Test API: https://sanalposprovtest.garantibbva.com.tr/VPServlet
    Test 3D: https://sanalposprovtest.garantibbva.com.tr/servlet/gt3dengine
    Prod API: https://sanalposprov.garantibbva.com.tr/VPServlet
    Prod 3D: https://sanalposprov.garantibbva.com.tr/servlet/gt3dengine

    Transaction Type mapping:
        sales -> normal satış
        void  -> iptal
        refund -> iade
        preauth -> ön yetkilendirme
        postauth -> ön yetkilendirme kapama
    """

    # Garanti TX Type mapping
    TX_TYPE_MAP = {
        'pay': 'sales',
        'pre_auth': 'preauth',
        'post_auth': 'postauth',
        'refund': 'refund',
        'cancel': 'void',
        'status': 'orderinq',
    }

    def _get_security_data(self, password=None):
        """SecurityData hesapla.

        SecurityData = SHA512(Password + '0' + TerminalID)
        """
        if password is None:
            password = self.provider.sanal_pos_provision_password or ''
        terminal_id = str(self.provider.sanal_pos_terminal_id or '').zfill(9)
        return HashHelper.garanti_security_data(password, terminal_id)

    def _get_hash_data(self, *params, password=None):
        """HashData hesapla.

        HashData = SHA512(param1 + param2 + ... + SecurityData)
        """
        security_data = self._get_security_data(password)
        return HashHelper.garanti_hash_data(security_data, *params)

    def make_payment(self, order, card):
        """Non-secure ödeme."""
        terminal_id = str(self.provider.sanal_pos_terminal_id or '').zfill(9)
        merchant_id = self.provider.sanal_pos_merchant_id or ''
        amount = self._format_amount(order['amount'])
        currency_code = self._get_currency_code(order.get('currency', 'TRY'))
        installment = order.get('installment', 1)

        # Hash: TerminalID + OrderID + Amount + SecurityData
        hash_data = self._get_hash_data(
            terminal_id, order['order_id'], amount,
        )

        terminal = {
            'id': terminal_id,
            'merchant_id': merchant_id,
            'user': self.provider.sanal_pos_provision_user or '',
            'password': self.provider.sanal_pos_provision_password or '',
        }
        transaction = {
            'type': 'sales',
            'amount': amount,
            'currency_code': currency_code,
            'installment': installment,
            'card_holder_present': '0',
        }

        xml_request = RequestBuilder.garanti_payment_xml(
            terminal, order, card, transaction, hash_data
        )

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_garanti_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("Garanti ödeme hatası: %s", e)
            return self._build_error_result(
                error_code='CONNECTION_ERROR',
                error_message=str(e),
            )

    def make_3d_form_data(self, order, card):
        """3D yönlendirme formu verileri."""
        terminal_id = str(self.provider.sanal_pos_terminal_id or '').zfill(9)
        merchant_id = self.provider.sanal_pos_merchant_id or ''
        store_key = self.provider.sanal_pos_store_key or ''
        prov_user = self.provider.sanal_pos_provision_user or ''

        amount = self._format_amount(order['amount'])
        currency_code = self._get_currency_code(order.get('currency', 'TRY'))
        installment = order.get('installment', 1)
        order_id = order['order_id']
        success_url = order.get('success_url', '')
        fail_url = order.get('fail_url', '')

        # 3D Hash: TerminalID + OrderID + Amount + SuccessURL + FailURL +
        #          Type + InstallmentCount + StoreKey + SecurityData
        security_data = self._get_security_data()
        hash_str = (
            terminal_id + order_id + amount + success_url + fail_url
            + 'sales' + (str(installment) if installment > 1 else '')
            + store_key + security_data
        )
        hash_data = self._sha512(hash_str)

        inputs = {
            'secure3dsecuritylevel': '3D',
            'mode': 'TEST' if self.test_mode else 'PROD',
            'apiversion': 'v0.01',
            'terminalprovuserid': prov_user,
            'terminaluserid': prov_user,
            'terminalmerchantid': merchant_id,
            'terminalid': terminal_id,
            'txntype': 'sales',
            'txnamount': amount,
            'txncurrencycode': currency_code,
            'txninstallmentcount': str(installment) if installment > 1 else '',
            'orderid': order_id,
            'successurl': success_url,
            'errorurl': fail_url,
            'customeripaddress': order.get('ip', '127.0.0.1'),
            'customeremailaddress': order.get('email', ''),
            'secure3dhash': hash_data,
        }

        # Kart bilgileri (eğer 3D_HOST değilse)
        if card and self.provider.sanal_pos_payment_model != '3d_host':
            inputs.update({
                'cardnumber': card.get('number', ''),
                'cardexpiredatemonth': card.get('exp_month', ''),
                'cardexpiredateyear': card.get('exp_year', '')[-2:],
                'cardcvv2': card.get('cvv', ''),
            })

        return {
            'gateway_url': self.get_3d_gate_url(),
            'method': 'POST',
            'inputs': inputs,
        }

    def process_3d_callback(self, callback_data):
        """3D callback verilerini işle."""
        result = ResponseParser.parse_3d_callback('sanal_pos_garanti', callback_data)

        # Garanti-spesifik alanlar
        result['auth_code'] = callback_data.get('authcode', '')
        result['transaction_id'] = callback_data.get('transid', '')
        result['host_ref_num'] = callback_data.get('hostrefnum', '')

        return result

    def complete_3d_payment(self, callback_data, order):
        """3D doğrulama sonrası provizyon al."""
        terminal_id = str(self.provider.sanal_pos_terminal_id or '').zfill(9)
        merchant_id = self.provider.sanal_pos_merchant_id or ''
        amount = self._format_amount(order['amount'])
        currency_code = self._get_currency_code(order.get('currency', 'TRY'))
        installment = order.get('installment', 1)

        # Provizyon hash
        hash_data = self._get_hash_data(
            terminal_id, order['order_id'], amount,
        )

        terminal = {
            'id': terminal_id,
            'merchant_id': merchant_id,
            'user': self.provider.sanal_pos_provision_user or '',
        }
        transaction = {
            'type': 'sales',
            'amount': amount,
            'currency_code': currency_code,
            'installment': installment,
            'card_holder_present': '13',  # 3D ile
        }

        xml_request = RequestBuilder.garanti_payment_xml(
            terminal, order, card=None, transaction=transaction,
            hash_data=hash_data,
        )

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_garanti_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("Garanti provizyon hatası: %s", e)
            return self._build_error_result(
                error_code='PROVISION_ERROR',
                error_message=str(e),
            )

    def refund(self, order):
        """Tam veya kısmi iade."""
        terminal_id = str(self.provider.sanal_pos_terminal_id or '').zfill(9)
        merchant_id = self.provider.sanal_pos_merchant_id or ''
        amount = self._format_amount(order['amount'])
        currency_code = self._get_currency_code(order.get('currency', 'TRY'))

        # İade için refund user/password kullan
        refund_user = self.provider.sanal_pos_refund_user or self.provider.sanal_pos_provision_user or ''
        refund_password = self.provider.sanal_pos_refund_password or self.provider.sanal_pos_provision_password or ''

        hash_data = self._get_hash_data(
            terminal_id, order['order_id'], amount,
            password=refund_password,
        )

        terminal = {
            'id': terminal_id,
            'merchant_id': merchant_id,
            'user': refund_user,
        }
        transaction = {
            'type': 'refund',
            'amount': amount,
            'currency_code': currency_code,
            'installment': 1,
        }

        xml_request = RequestBuilder.garanti_payment_xml(
            terminal, order, card=None, transaction=transaction,
            hash_data=hash_data,
        )

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_garanti_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("Garanti iade hatası: %s", e)
            return self._build_error_result(
                error_code='REFUND_ERROR',
                error_message=str(e),
            )

    def cancel(self, order):
        """İptal işlemi."""
        terminal_id = str(self.provider.sanal_pos_terminal_id or '').zfill(9)
        merchant_id = self.provider.sanal_pos_merchant_id or ''
        amount = self._format_amount(order.get('amount', 0))

        hash_data = self._get_hash_data(
            terminal_id, order['order_id'], amount,
        )

        terminal = {
            'id': terminal_id,
            'merchant_id': merchant_id,
            'user': self.provider.sanal_pos_provision_user or '',
        }
        transaction = {
            'type': 'void',
            'amount': amount,
            'currency_code': self._get_currency_code(order.get('currency', 'TRY')),
            'installment': 1,
        }

        xml_request = RequestBuilder.garanti_payment_xml(
            terminal, order, card=None, transaction=transaction,
            hash_data=hash_data,
        )

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_garanti_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("Garanti iptal hatası: %s", e)
            return self._build_error_result(
                error_code='CANCEL_ERROR',
                error_message=str(e),
            )

    def query_status(self, order):
        """İşlem durum sorgulama."""
        terminal_id = str(self.provider.sanal_pos_terminal_id or '').zfill(9)
        merchant_id = self.provider.sanal_pos_merchant_id or ''

        hash_data = self._get_hash_data(
            terminal_id, order['order_id'], '0',
        )

        terminal = {
            'id': terminal_id,
            'merchant_id': merchant_id,
            'user': self.provider.sanal_pos_provision_user or '',
        }
        transaction = {
            'type': 'orderinq',
            'amount': '0',
            'currency_code': '949',
            'installment': 1,
        }

        xml_request = RequestBuilder.garanti_payment_xml(
            terminal, order, card=None, transaction=transaction,
            hash_data=hash_data,
        )

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            return ResponseParser.parse_garanti_response(response.text)
        except Exception as e:
            _logger.error("Garanti durum sorgulama hatası: %s", e)
            return self._build_error_result(
                error_code='STATUS_ERROR',
                error_message=str(e),
            )

    def validate_hash(self, data):
        """3D callback hash doğrulama."""
        received_hash = data.get('secure3dhash', data.get('hash', ''))
        if not received_hash:
            return False

        terminal_id = str(self.provider.sanal_pos_terminal_id or '').zfill(9)
        store_key = self.provider.sanal_pos_store_key or ''
        security_data = self._get_security_data()

        # Garanti 3D hash doğrulama parametreleri
        order_id = data.get('orderid', '')
        md_status = data.get('mdstatus', data.get('mdStatus', ''))
        response_msg = data.get('response', '')
        tx_amount = data.get('txnamount', '')

        hash_str = (
            terminal_id + order_id + md_status + response_msg
            + tx_amount + store_key + security_data
        )
        calculated_hash = self._sha512(hash_str)

        return received_hash.upper() == calculated_hash.upper()

    def generate_hash(self, params):
        """Genel hash üretme."""
        return self._get_hash_data(*params.values())
