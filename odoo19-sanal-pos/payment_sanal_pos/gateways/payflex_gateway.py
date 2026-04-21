import logging
from xml.etree import ElementTree as ET

from .base_gateway import BaseGateway
from .hash_helper import HashHelper
from .response_parser import ResponseParser

_logger = logging.getLogger(__name__)


class PayFlexGateway(BaseGateway):
    """PayFlex MPI VPOS V4 Gateway.

    Desteklenen bankalar: Vakıfbank, Ziraat (alternatif), İşbank (alternatif)
    API: XML/Form POST tabanlı.
    Test: https://onlineodemetest.vakifbank.com.tr/
    Prod: https://onlineodeme.vakifbank.com.tr/

    İşlem Akışı:
    1. SessionToken oluştur
    2. 3D formunu bankaya POST et
    3. Callback'te SessionToken ile provizyon al
    """

    def _build_payment_xml(self, order, tx_type='Sale', card=None):
        """PayFlex ödeme XML isteği oluştur."""
        root = ET.Element('VposRequest')

        merchant = ET.SubElement(root, 'MerchantId')
        merchant.text = self.provider.sanal_pos_merchant_id or ''
        password = ET.SubElement(root, 'Password')
        password.text = self.provider.sanal_pos_provision_password or ''
        terminal = ET.SubElement(root, 'TerminalNo')
        terminal.text = self.provider.sanal_pos_terminal_id or ''

        tx_type_elem = ET.SubElement(root, 'TransactionType')
        tx_type_elem.text = tx_type

        amount_elem = ET.SubElement(root, 'Amount')
        amount_elem.text = f"{order['amount']:.2f}"
        currency_elem = ET.SubElement(root, 'CurrencyCode')
        currency_elem.text = self._get_currency_code(order.get('currency', 'TRY'))

        order_id_elem = ET.SubElement(root, 'OrderId')
        order_id_elem.text = order.get('order_id', '')

        installment = order.get('installment', 1)
        if installment > 1:
            inst_elem = ET.SubElement(root, 'NumberOfInstallments')
            inst_elem.text = str(installment)

        if card:
            pan = ET.SubElement(root, 'Pan')
            pan.text = card.get('number', '')
            expiry = ET.SubElement(root, 'Expiry')
            expiry.text = f"{card.get('exp_year', '2099')}{card.get('exp_month', '01')}"
            cvv = ET.SubElement(root, 'Cvv')
            cvv.text = card.get('cvv', '')

        return ET.tostring(root, encoding='unicode', xml_declaration=True)

    def make_payment(self, order, card):
        """Non-secure ödeme."""
        xml_request = self._build_payment_xml(order, tx_type='Sale', card=card)

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_payflex_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("PayFlex ödeme hatası: %s", e)
            return self._build_error_result(
                error_code='CONNECTION_ERROR',
                error_message=str(e),
            )

    def make_3d_form_data(self, order, card):
        """3D yönlendirme formu verileri."""
        merchant_id = self.provider.sanal_pos_merchant_id or ''
        password = self.provider.sanal_pos_provision_password or ''
        terminal_no = self.provider.sanal_pos_terminal_id or ''
        amount = f"{order['amount']:.2f}"
        currency_code = self._get_currency_code(order.get('currency', 'TRY'))
        installment = order.get('installment', 1)
        order_id = order['order_id']
        success_url = order.get('success_url', '')
        fail_url = order.get('fail_url', '')

        inputs = {
            'MerchantId': merchant_id,
            'MerchantPassword': password,
            'TerminalNo': terminal_no,
            'TransactionType': 'Sale',
            'AmountCode': currency_code,
            'Amount': amount,
            'OrderId': order_id,
            'ClientIp': order.get('ip', '127.0.0.1'),
            'TransactionDeviceSource': '0',
            'SuccessUrl': success_url,
            'FailUrl': fail_url,
        }

        if installment > 1:
            inputs['NumberOfInstallments'] = str(installment)

        if card and self.provider.sanal_pos_payment_model != '3d_host':
            inputs.update({
                'Pan': card.get('number', ''),
                'ExpiryDate': f"{card.get('exp_year', '2099')}{card.get('exp_month', '01')}",
                'Cvv': card.get('cvv', ''),
                'CardHoldersName': card.get('holder', ''),
            })

        return {
            'gateway_url': self.get_3d_gate_url(),
            'method': 'POST',
            'inputs': inputs,
        }

    def process_3d_callback(self, callback_data):
        """3D callback verilerini işle."""
        result = ResponseParser.parse_3d_callback('sanal_pos_payflex', callback_data)

        # PayFlex spesifik alanlar
        result['auth_code'] = callback_data.get('AuthCode', '')
        result['transaction_id'] = callback_data.get('TransactionId', '')

        # PayFlex ResponseCode kontrolü
        response_code = callback_data.get('ResponseCode', callback_data.get('Rc', ''))
        if response_code not in ('0000', '00', ''):
            result['status'] = 'fail'
            result['error_code'] = response_code
            result['error_message'] = callback_data.get(
                'ResponseMessage', callback_data.get('ErrorMessage', '')
            )

        return result

    def complete_3d_payment(self, callback_data, order):
        """3D doğrulama sonrası provizyon al."""
        xml_request = self._build_payment_xml(order, tx_type='Sale')

        # Session token ekle
        session_token = callback_data.get('SessionToken',
                                           callback_data.get('sessionToken', ''))
        if session_token:
            xml_request = xml_request.replace(
                '</VposRequest>',
                f'<SessionToken>{session_token}</SessionToken></VposRequest>'
            )

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_payflex_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("PayFlex provizyon hatası: %s", e)
            return self._build_error_result(
                error_code='PROVISION_ERROR',
                error_message=str(e),
            )

    def refund(self, order):
        """Tam veya kısmi iade."""
        xml_request = self._build_payment_xml(order, tx_type='Refund')

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_payflex_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("PayFlex iade hatası: %s", e)
            return self._build_error_result(
                error_code='REFUND_ERROR',
                error_message=str(e),
            )

    def cancel(self, order):
        """İptal işlemi."""
        xml_request = self._build_payment_xml(order, tx_type='Cancel')

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_payflex_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("PayFlex iptal hatası: %s", e)
            return self._build_error_result(
                error_code='CANCEL_ERROR',
                error_message=str(e),
            )

    def query_status(self, order):
        """İşlem durum sorgulama."""
        xml_request = self._build_payment_xml(order, tx_type='OrderInquiry')

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            return ResponseParser.parse_payflex_response(response.text)
        except Exception as e:
            _logger.error("PayFlex durum sorgulama hatası: %s", e)
            return self._build_error_result(
                error_code='STATUS_ERROR',
                error_message=str(e),
            )

    def validate_hash(self, data):
        """3D callback hash doğrulama (PayFlex)."""
        # PayFlex ResponseCode ile doğrulama
        response_code = data.get('ResponseCode', data.get('Rc', ''))
        md_status = data.get('MdStatus', data.get('mdStatus', ''))
        return str(md_status) in ('1', '2', '3', '4')

    def generate_hash(self, params):
        """Genel hash üretme."""
        password = self.provider.sanal_pos_provision_password or ''
        terminal_no = self.provider.sanal_pos_terminal_id or ''
        return HashHelper.payflex_hash(password, terminal_no, *params.values())
