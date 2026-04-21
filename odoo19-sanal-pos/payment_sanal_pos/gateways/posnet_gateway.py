import logging
from xml.etree import ElementTree as ET

from .base_gateway import BaseGateway
from .hash_helper import HashHelper
from .response_parser import ResponseParser

_logger = logging.getLogger(__name__)


class PosNetGateway(BaseGateway):
    """PosNet Gateway - YapıKredi Bankası.

    API: XML tabanlı.
    Test API: https://setmpos.ykb.com/PosnetWebService/XML
    Test 3D: https://setmpos.ykb.com/3DSWebService/YKBPaymentService
    Prod API: https://posnet.yapikredi.com.tr/PosnetWebService/XML
    Prod 3D: https://posnet.yapikredi.com.tr/3DSWebService/YKBPaymentService

    PosNet özellikleri:
    - Tutar kuruş cinsindendir (100 = 1 TL)
    - Para birimi: YT (TRY), US (USD), EU (EUR)
    - Taksit: 00 = tek çekim
    - MAC hash kullanılır
    """

    CURRENCY_MAP_POSNET = {
        'TRY': 'YT',
        'USD': 'US',
        'EUR': 'EU',
        'GBP': 'GB',
    }

    def _get_posnet_currency(self, currency_name):
        """PosNet para birimi kodu."""
        return self.CURRENCY_MAP_POSNET.get(currency_name, 'YT')

    def _format_posnet_amount(self, amount):
        """PosNet tutar formatı: kuruş cinsinden int string."""
        return str(int(round(amount * 100)))

    def _format_installment(self, installment):
        """PosNet taksit formatı: 00 = tek çekim."""
        if installment <= 1:
            return '00'
        return str(installment).zfill(2)

    def _build_posnet_xml(self, operation, params):
        """PosNet XML isteği oluştur."""
        root = ET.Element('posnetRequest')

        mid = ET.SubElement(root, 'mid')
        mid.text = self.provider.sanal_pos_merchant_id or ''
        tid = ET.SubElement(root, 'tid')
        tid.text = self.provider.sanal_pos_terminal_id or ''

        op_elem = ET.SubElement(root, operation)
        for key, value in params.items():
            param_elem = ET.SubElement(op_elem, key)
            param_elem.text = str(value)

        return ET.tostring(root, encoding='unicode', xml_declaration=True)

    def make_payment(self, order, card):
        """Non-secure ödeme."""
        amount = self._format_posnet_amount(order['amount'])
        currency = self._get_posnet_currency(order.get('currency', 'TRY'))
        installment = self._format_installment(order.get('installment', 1))

        params = {
            'ccno': card.get('number', ''),
            'expDate': f"{card.get('exp_year', '99')[-2:]}{card.get('exp_month', '01')}",
            'cvc': card.get('cvv', ''),
            'amount': amount,
            'currencyCode': currency,
            'orderID': order['order_id'],
            'installment': installment,
        }

        xml_request = self._build_posnet_xml('sale', params)

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_posnet_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("PosNet ödeme hatası: %s", e)
            return self._build_error_result(
                error_code='CONNECTION_ERROR',
                error_message=str(e),
            )

    def make_3d_form_data(self, order, card):
        """3D yönlendirme formu verileri."""
        merchant_id = self.provider.sanal_pos_merchant_id or ''
        terminal_id = self.provider.sanal_pos_terminal_id or ''
        store_key = self.provider.sanal_pos_store_key or ''
        amount = self._format_posnet_amount(order['amount'])
        currency = self._get_posnet_currency(order.get('currency', 'TRY'))
        installment = self._format_installment(order.get('installment', 1))
        order_id = order['order_id']
        success_url = order.get('success_url', '')

        # PosNet için önceden OOS isteği gönder (resolve merchant packet)
        oos_params = {
            'posnetid': store_key,
            'XID': order_id,
            'amount': amount,
            'currencyCode': currency,
            'installment': installment,
            'tranType': 'Sale',
            'merchantReturnURL': success_url,
        }

        if card:
            oos_params.update({
                'cardHolderName': card.get('holder', ''),
                'ccno': card.get('number', ''),
                'expDate': f"{card.get('exp_year', '99')[-2:]}{card.get('exp_month', '01')}",
                'cvc': card.get('cvv', ''),
            })

        oos_xml = self._build_posnet_xml('oosRequestData', oos_params)

        try:
            oos_response = self._send_xml_request(self.get_api_url(), oos_xml)
            oos_root = ET.fromstring(oos_response.text)

            data1_elem = oos_root.find('.//data1')
            data2_elem = oos_root.find('.//data2')
            sign_elem = oos_root.find('.//sign')

            data1 = data1_elem.text if data1_elem is not None else ''
            data2 = data2_elem.text if data2_elem is not None else ''
            sign = sign_elem.text if sign_elem is not None else ''

        except Exception as e:
            _logger.error("PosNet OOS isteği hatası: %s", e)
            data1 = data2 = sign = ''

        inputs = {
            'mid': merchant_id,
            'posnetID': store_key,
            'posnetData': data1,
            'posnetData2': data2,
            'digest': sign,
            'merchantReturnURL': success_url,
            'url': '',
            'lang': 'tr',
        }

        return {
            'gateway_url': self.get_3d_gate_url(),
            'method': 'POST',
            'inputs': inputs,
        }

    def process_3d_callback(self, callback_data):
        """3D callback verilerini işle."""
        result = ResponseParser.parse_3d_callback('sanal_pos_posnet', callback_data)

        # PosNet spesifik: MerchantPacket çözümleme
        merchant_packet = callback_data.get('MerchantPacket', '')
        if merchant_packet:
            try:
                oos_resolve_xml = self._build_posnet_xml('oosResolveMerchantData', {
                    'bankData': callback_data.get('BankPacket', ''),
                    'merchantData': merchant_packet,
                    'sign': callback_data.get('Sign', ''),
                })
                response = self._send_xml_request(self.get_api_url(), oos_resolve_xml)
                resolve_root = ET.fromstring(response.text)

                md_status_elem = resolve_root.find('.//mdStatus')
                if md_status_elem is not None:
                    result['md_status'] = md_status_elem.text
                    result['status'] = 'success' if md_status_elem.text == '1' else 'fail'

                xid_elem = resolve_root.find('.//XID')
                if xid_elem is not None:
                    result['xid'] = xid_elem.text
                    result['order_id'] = xid_elem.text

            except Exception as e:
                _logger.error("PosNet OOS resolve hatası: %s", e)
                result['status'] = 'fail'
                result['error_message'] = str(e)

        return result

    def complete_3d_payment(self, callback_data, order):
        """3D doğrulama sonrası provizyon al."""
        amount = self._format_posnet_amount(order['amount'])
        currency = self._get_posnet_currency(order.get('currency', 'TRY'))
        installment = self._format_installment(order.get('installment', 1))

        params = {
            'amount': amount,
            'currencyCode': currency,
            'installment': installment,
            'XID': order['order_id'],
            'bankData': callback_data.get('BankPacket', ''),
            'wpAmount': '0',
            'mac': callback_data.get('Mac', callback_data.get('mac', '')),
        }

        xml_request = self._build_posnet_xml('oosTranData', params)

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_posnet_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("PosNet provizyon hatası: %s", e)
            return self._build_error_result(
                error_code='PROVISION_ERROR',
                error_message=str(e),
            )

    def refund(self, order):
        """Tam veya kısmi iade."""
        amount = self._format_posnet_amount(order['amount'])
        currency = self._get_posnet_currency(order.get('currency', 'TRY'))

        params = {
            'amount': amount,
            'currencyCode': currency,
            'orderID': order['order_id'],
        }

        xml_request = self._build_posnet_xml('return', params)

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_posnet_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("PosNet iade hatası: %s", e)
            return self._build_error_result(
                error_code='REFUND_ERROR',
                error_message=str(e),
            )

    def cancel(self, order):
        """İptal işlemi."""
        params = {
            'transaction': 'sale',
            'hostLogKey': order.get('auth_code', ''),
            'authCode': order.get('auth_code', ''),
        }

        xml_request = self._build_posnet_xml('reverse', params)

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            result = ResponseParser.parse_posnet_response(response.text)
            result['raw_request'] = xml_request
            result['raw_response'] = response.text
            return result
        except Exception as e:
            _logger.error("PosNet iptal hatası: %s", e)
            return self._build_error_result(
                error_code='CANCEL_ERROR',
                error_message=str(e),
            )

    def query_status(self, order):
        """İşlem durum sorgulama."""
        params = {
            'orderID': order['order_id'],
        }

        xml_request = self._build_posnet_xml('agreement', params)

        try:
            response = self._send_xml_request(self.get_api_url(), xml_request)
            return ResponseParser.parse_posnet_response(response.text)
        except Exception as e:
            _logger.error("PosNet durum sorgulama hatası: %s", e)
            return self._build_error_result(
                error_code='STATUS_ERROR',
                error_message=str(e),
            )

    def validate_hash(self, data):
        """3D callback hash doğrulama (PosNet)."""
        # PosNet BankPacket ve MerchantPacket ile doğrulama
        bank_packet = data.get('BankPacket', '')
        merchant_packet = data.get('MerchantPacket', '')
        sign = data.get('Sign', '')
        return bool(bank_packet and merchant_packet and sign)

    def generate_hash(self, params):
        """Genel hash üretme (PosNet MAC)."""
        store_key = self.provider.sanal_pos_store_key or ''
        return HashHelper.posnet_mac(store_key, *params.values())
