import logging
import random
import string

from .base_gateway import BaseGateway
from .hash_helper import HashHelper
from .request_builder import RequestBuilder
from .response_parser import ResponseParser

_logger = logging.getLogger(__name__)


class EstV3Gateway(BaseGateway):
    """EstV3 (Asseco/Payten) Gateway.

    Desteklenen bankalar: Akbank, İşbank, Ziraat, Halkbank, TEB, Finansbank,
                          Şekerbank
    API: XML tabanlı, SHA512 hash (v3).
    Hash: Base64(SHA512(param1|param2|...|storeKey))

    Akbank Test: https://entegrasyon.asseco-see.com.tr/fim/api
    Akbank 3D: https://entegrasyon.asseco-see.com.tr/fim/est3Dgate
    """

    TX_TYPE_MAP = {
        'pay': 'Auth',
        'pre_auth': 'PreAuth',
        'post_auth': 'PostAuth',
        'refund': 'Credit',
        'cancel': 'Void',
    }

    def _generate_random(self, length=20):
        """Rastgele alfanumerik string üret."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    def _calculate_hash(self, params_list):
        """EstV3 hash hesapla.

        Hash = Base64(SHA512(param1|param2|...|storeKey))
        Escape: \\, |, : karakterleri escape edilir.
        """
        store_key = self.provider.sanal_pos_store_key or ''
        return HashHelper.estv3_hash(store_key, *params_list)

    def make_payment(self, order, card):
        """Non-secure ödeme."""
        client_id = self.provider.sanal_pos_merchant_id or ''
        amount = f"{order['amount']:.2f}"
        currency_code = self._get_currency_code(order.get('currency', 'TRY'))
        installment = order.get('installment', 1)

        xml_request = RequestBuilder.estv3_payment_xml(
            client_id=client_id,
            order_id=order['order_id'],
            amount=amount,
            currency_code=currency_code,
            tx_type='Auth',
            installment=installment,
            card=card,
        )

        # Name ve Password ekle
        xml_request = xml_request.replace(
            '<Name></Name>',
            f'<Name>{self.provider.sanal_pos_provision_user or ""}</Name>'
        ).replace(
            '<Password></Password>',
            f'<Password>{self.provider.sanal_pos_provision_password or ""}</Password>'
        )

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_estv3_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("EstV3 ödeme hatası: %s", e)
            return self._build_error_result(
                error_code='CONNECTION_ERROR',
                error_message=str(e),
            )

    def make_3d_form_data(self, order, card):
        """3D yönlendirme formu verileri."""
        client_id = self.provider.sanal_pos_merchant_id or ''
        store_key = self.provider.sanal_pos_store_key or ''
        amount = f"{order['amount']:.2f}"
        currency_code = self._get_currency_code(order.get('currency', 'TRY'))
        installment = order.get('installment', 1)
        order_id = order['order_id']
        success_url = order.get('success_url', '')
        fail_url = order.get('fail_url', '')
        rnd = self._generate_random()
        store_type = '3d'

        # Hash parametreleri: clientId, oid, amount, okUrl, failUrl,
        #                     islemtipi, taksit, rnd, storeKey
        hash_params = [
            client_id, order_id, amount, success_url, fail_url,
            'Auth', str(installment) if installment > 1 else '',
            rnd, store_key,
        ]
        hash_value = self._calculate_hash(hash_params[:-1])  # storeKey zaten içinde

        inputs = {
            'clientid': client_id,
            'storetype': store_type,
            'hash': hash_value,
            'islemtipi': 'Auth',
            'amount': amount,
            'currency': currency_code,
            'oid': order_id,
            'okUrl': success_url,
            'failUrl': fail_url,
            'rnd': rnd,
            'taksit': str(installment) if installment > 1 else '',
            'lang': 'tr',
        }

        # Kart bilgileri
        if card and self.provider.sanal_pos_payment_model != '3d_host':
            inputs.update({
                'pan': card.get('number', ''),
                'cardHolderName': card.get('holder', ''),
                'Ecom_Payment_Card_ExpDate_Month': card.get('exp_month', ''),
                'Ecom_Payment_Card_ExpDate_Year': card.get('exp_year', ''),
                'cv2': card.get('cvv', ''),
            })

        return {
            'gateway_url': self.get_3d_gate_url(),
            'method': 'POST',
            'inputs': inputs,
        }

    def process_3d_callback(self, callback_data):
        """3D callback verilerini işle."""
        result = ResponseParser.parse_3d_callback('sanal_pos_estv3', callback_data)

        # EstV3 spesifik: ProcReturnCode kontrolü
        proc_return_code = callback_data.get('ProcReturnCode', '')
        if proc_return_code == '00' and result['status'] == 'success':
            result['auth_code'] = callback_data.get('AuthCode', '')
            result['transaction_id'] = callback_data.get('TransId', '')
        elif result['status'] == 'success' and proc_return_code != '00':
            # 3D başarılı ama ödeme başarısız
            result['error_message'] = callback_data.get('ErrMsg', '')

        return result

    def complete_3d_payment(self, callback_data, order):
        """3D doğrulama sonrası provizyon al."""
        client_id = self.provider.sanal_pos_merchant_id or ''
        amount = f"{order['amount']:.2f}"
        currency_code = self._get_currency_code(order.get('currency', 'TRY'))
        installment = order.get('installment', 1)

        # 3D callback'ten gelen verileri provizyon isteğine ekle
        extra_params = {
            'PayerTxnId': callback_data.get('PayerTxnId', ''),
            'PayerSecurityLevel': callback_data.get('PayerSecurityLevel', ''),
            'PayerAuthenticationCode': callback_data.get('PayerAuthenticationCode', ''),
            'CardholderPresentCode': '13',
        }

        xml_request = RequestBuilder.estv3_payment_xml(
            client_id=client_id,
            order_id=order['order_id'],
            amount=amount,
            currency_code=currency_code,
            tx_type='Auth',
            installment=installment,
            extra_params=extra_params,
        )

        xml_request = xml_request.replace(
            '<Name></Name>',
            f'<Name>{self.provider.sanal_pos_provision_user or ""}</Name>'
        ).replace(
            '<Password></Password>',
            f'<Password>{self.provider.sanal_pos_provision_password or ""}</Password>'
        )

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_estv3_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("EstV3 provizyon hatası: %s", e)
            return self._build_error_result(
                error_code='PROVISION_ERROR',
                error_message=str(e),
            )

    def refund(self, order):
        """Tam veya kısmi iade."""
        client_id = self.provider.sanal_pos_merchant_id or ''
        amount = f"{order['amount']:.2f}"
        currency_code = self._get_currency_code(order.get('currency', 'TRY'))

        xml_request = RequestBuilder.estv3_payment_xml(
            client_id=client_id,
            order_id=order['order_id'],
            amount=amount,
            currency_code=currency_code,
            tx_type='Credit',
        )

        xml_request = xml_request.replace(
            '<Name></Name>',
            f'<Name>{self.provider.sanal_pos_refund_user or self.provider.sanal_pos_provision_user or ""}</Name>'
        ).replace(
            '<Password></Password>',
            f'<Password>{self.provider.sanal_pos_refund_password or self.provider.sanal_pos_provision_password or ""}</Password>'
        )

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_estv3_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("EstV3 iade hatası: %s", e)
            return self._build_error_result(
                error_code='REFUND_ERROR',
                error_message=str(e),
            )

    def cancel(self, order):
        """İptal işlemi."""
        client_id = self.provider.sanal_pos_merchant_id or ''
        amount = f"{order.get('amount', 0):.2f}"
        currency_code = self._get_currency_code(order.get('currency', 'TRY'))

        xml_request = RequestBuilder.estv3_payment_xml(
            client_id=client_id,
            order_id=order['order_id'],
            amount=amount,
            currency_code=currency_code,
            tx_type='Void',
        )

        xml_request = xml_request.replace(
            '<Name></Name>',
            f'<Name>{self.provider.sanal_pos_provision_user or ""}</Name>'
        ).replace(
            '<Password></Password>',
            f'<Password>{self.provider.sanal_pos_provision_password or ""}</Password>'
        )

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_estv3_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("EstV3 iptal hatası: %s", e)
            return self._build_error_result(
                error_code='CANCEL_ERROR',
                error_message=str(e),
            )

    def query_status(self, order):
        """İşlem durum sorgulama."""
        client_id = self.provider.sanal_pos_merchant_id or ''

        xml_request = RequestBuilder.estv3_payment_xml(
            client_id=client_id,
            order_id=order['order_id'],
            amount='0',
            currency_code='949',
            tx_type='OrderInquiry',
        )

        xml_request = xml_request.replace(
            '<Name></Name>',
            f'<Name>{self.provider.sanal_pos_provision_user or ""}</Name>'
        ).replace(
            '<Password></Password>',
            f'<Password>{self.provider.sanal_pos_provision_password or ""}</Password>'
        )

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            return ResponseParser.parse_estv3_response(response.text)
        except Exception as e:
            _logger.error("EstV3 durum sorgulama hatası: %s", e)
            return self._build_error_result(
                error_code='STATUS_ERROR',
                error_message=str(e),
            )

    def validate_hash(self, data):
        """3D callback hash doğrulama (EstV3)."""
        received_hash = data.get('HASH', data.get('hash', ''))
        if not received_hash:
            return False

        store_key = self.provider.sanal_pos_store_key or ''

        # EstV3 hash doğrulama parametreleri
        # Hash = Base64(SHA512(
        #   clientId|oid|AuthCode|ProcReturnCode|Response|mdStatus|
        #   cavv|eci|md|rnd|StoreKey
        # ))
        params = [
            data.get('clientid', ''),
            data.get('oid', ''),
            data.get('AuthCode', ''),
            data.get('ProcReturnCode', ''),
            data.get('Response', ''),
            data.get('mdStatus', ''),
            data.get('cavv', ''),
            data.get('eci', ''),
            data.get('md', ''),
            data.get('rnd', ''),
        ]

        calculated = HashHelper.estv3_hash(store_key, *params)
        return received_hash == calculated

    def generate_hash(self, params):
        """Genel hash üretme."""
        return self._calculate_hash(list(params.values()))
