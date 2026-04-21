import hashlib
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod

import requests

_logger = logging.getLogger(__name__)


class BaseGateway(ABC):
    """Tüm banka gateway'lerinin abstract base sınıfı.

    mewebstudio/pos PosInterface pattern'inden esinlenilmiştir.
    Her banka gateway'i bu sınıftan türetilir ve abstract
    metodları implement eder.
    """

    # Transaction tipleri
    TX_PAY = 'pay'
    TX_PRE_AUTH = 'pre_auth'
    TX_POST_AUTH = 'post_auth'
    TX_REFUND = 'refund'
    TX_CANCEL = 'cancel'
    TX_STATUS = 'status'

    # Ödeme modelleri
    MODEL_3D_SECURE = '3d_secure'
    MODEL_3D_PAY = '3d_pay'
    MODEL_3D_HOST = '3d_host'
    MODEL_NON_SECURE = 'non_secure'

    # ISO 4217 para birimi kodları
    CURRENCY_MAP = {
        'TRY': '949',
        'USD': '840',
        'EUR': '978',
        'GBP': '826',
        'JPY': '392',
    }

    def __init__(self, provider):
        """
        :param provider: payment.provider recordset
        """
        self.provider = provider
        self.test_mode = provider.state == 'test'
        self._http_client = requests.Session()
        self._timeout = 30  # saniye

    # -------------------------------------------------------------------------
    # ABSTRACT METHODS - Alt sınıflar tarafından implement edilmeli
    # -------------------------------------------------------------------------

    @abstractmethod
    def make_payment(self, order, card):
        """Non-secure ödeme.

        :param order: dict - Sipariş bilgileri
            keys: order_id, amount, currency, installment, description
        :param card: dict - Kart bilgileri
            keys: number, holder, exp_month, exp_year, cvv
        :returns: dict(status, auth_code, transaction_id, error_code, error_message)
        """

    @abstractmethod
    def make_3d_form_data(self, order, card):
        """3D yönlendirme formu verileri oluştur.

        :param order: dict - Sipariş bilgileri
            keys: order_id, amount, currency, installment, success_url, fail_url
        :param card: dict - Kart bilgileri
            keys: number, holder, exp_month, exp_year, cvv
        :returns: dict(
            gateway_url: str,   # Banka 3D sayfası URL
            method: str,        # 'POST' veya 'GET'
            inputs: dict        # Form input parametreleri
        )
        """

    @abstractmethod
    def process_3d_callback(self, callback_data):
        """3D callback verilerini işle.

        :param callback_data: dict - Bankadan gelen POST parametreleri
        :returns: dict(
            status: 'success' | 'fail',
            md_status: str,
            auth_code: str,
            transaction_id: str,
            eci: str,
            cavv: str,
            xid: str,
            error_code: str,
            error_message: str,
            order_id: str,
        )
        """

    @abstractmethod
    def complete_3d_payment(self, callback_data, order):
        """3D doğrulama sonrası provizyon al (MODEL_3D_SECURE için).

        :param callback_data: dict - 3D callback verileri
        :param order: dict - Sipariş bilgileri
        :returns: dict(status, auth_code, transaction_id, host_ref_num, rrn,
                       raw_request, raw_response, error_code, error_message)
        """

    @abstractmethod
    def refund(self, order):
        """Tam veya kısmi iade.

        :param order: dict - keys: order_id, amount, currency, auth_code
        :returns: dict(status, transaction_id, error_code, error_message)
        """

    @abstractmethod
    def cancel(self, order):
        """İptal işlemi.

        :param order: dict - keys: order_id, auth_code
        :returns: dict(status, transaction_id, error_code, error_message)
        """

    @abstractmethod
    def query_status(self, order):
        """İşlem durum sorgulama.

        :param order: dict - keys: order_id
        :returns: dict(status, order_status, auth_code, error_message)
        """

    @abstractmethod
    def validate_hash(self, data):
        """3D callback hash doğrulama.

        :param data: dict - Callback verileri
        :returns: bool - Hash geçerli mi?
        """

    @abstractmethod
    def generate_hash(self, params):
        """İstek için hash üretme.

        :param params: dict - Hash parametreleri
        :returns: str - Hash değeri
        """

    # -------------------------------------------------------------------------
    # ORTAK METODLAR
    # -------------------------------------------------------------------------

    def get_api_url(self):
        """Mevcut duruma göre (test/prod) aktif API URL."""
        if self.test_mode:
            return self.provider.sanal_pos_api_url_test
        return self.provider.sanal_pos_api_url

    def get_3d_gate_url(self):
        """Mevcut duruma göre (test/prod) aktif 3D Gate URL."""
        if self.test_mode:
            return self.provider.sanal_pos_3d_gate_url_test
        return self.provider.sanal_pos_3d_gate_url

    def _send_request(self, url, data, headers=None, method='POST',
                      content_type='application/x-www-form-urlencoded'):
        """HTTP isteği gönder.

        :param url: Hedef URL
        :param data: İstek verisi (str veya dict)
        :param headers: Ek HTTP başlıkları
        :param method: HTTP metodu (POST/GET)
        :param content_type: Content-Type
        :returns: requests.Response
        :raises: requests.RequestException
        """
        if headers is None:
            headers = {}

        if 'Content-Type' not in headers:
            headers['Content-Type'] = content_type

        start_time = time.time()
        try:
            if method.upper() == 'POST':
                if isinstance(data, str):
                    response = self._http_client.post(
                        url, data=data, headers=headers, timeout=self._timeout
                    )
                else:
                    response = self._http_client.post(
                        url, data=data, headers=headers, timeout=self._timeout
                    )
            else:
                response = self._http_client.get(
                    url, params=data, headers=headers, timeout=self._timeout
                )

            duration = int((time.time() - start_time) * 1000)
            _logger.info(
                "Gateway isteği: %s %s -> HTTP %s (%dms)",
                method, url, response.status_code, duration,
            )
            return response

        except requests.Timeout:
            duration = int((time.time() - start_time) * 1000)
            _logger.error("Gateway timeout: %s %s (%dms)", method, url, duration)
            raise
        except requests.RequestException as e:
            _logger.error("Gateway iletişim hatası: %s %s -> %s", method, url, e)
            raise

    def _send_xml_request(self, url, xml_data):
        """XML formatlı HTTP isteği gönder.

        :param url: Hedef URL
        :param xml_data: XML string
        :returns: requests.Response
        """
        return self._send_request(
            url, xml_data,
            headers={'Content-Type': 'application/xml; charset=utf-8'},
        )

    def _send_json_request(self, url, json_data):
        """JSON formatlı HTTP isteği gönder.

        :param url: Hedef URL
        :param json_data: dict
        :returns: requests.Response
        """
        import json as json_lib
        return self._send_request(
            url, json_lib.dumps(json_data),
            headers={'Content-Type': 'application/json; charset=utf-8'},
        )

    def _get_currency_code(self, currency_name):
        """ISO 4217 para birimi kodu döndür.

        :param currency_name: Para birimi adı (TRY, USD, EUR)
        :returns: str - ISO kodu (949, 840, 978)
        """
        return self.CURRENCY_MAP.get(currency_name, '949')

    def _format_amount(self, amount, decimal_separator=''):
        """Banka formatında tutar.

        :param amount: float - Tutar
        :param decimal_separator: Ondalık ayırıcı (boş=kuruş)
        :returns: str - Formatlanmış tutar
        """
        if decimal_separator:
            return f"{amount:.2f}".replace('.', decimal_separator)
        # Kuruş cinsinden (100 ile çarp, tam sayı)
        return str(int(round(amount * 100)))

    def _generate_order_id(self):
        """Benzersiz sipariş numarası üret.

        Format: SPyyyyMMddHHmmss_XXXXX
        """
        timestamp = time.strftime('%Y%m%d%H%M%S')
        unique = uuid.uuid4().hex[:5].upper()
        return f"SP{timestamp}_{unique}"

    def _mask_card_number(self, card_number):
        """Kart numarasını maskele.

        :param card_number: Tam kart numarası
        :returns: str - Maskeli kart no (453188****1234)
        """
        if not card_number:
            return ''
        clean = re.sub(r'\D', '', card_number)
        if len(clean) < 10:
            return '****'
        return f"{clean[:6]}{'*' * (len(clean) - 10)}{clean[-4:]}"

    def _sha512(self, data):
        """SHA512 hash hesapla.

        :param data: Hash verilecek string
        :returns: str - SHA512 hex digest (uppercase)
        """
        return hashlib.sha512(data.encode('utf-8')).hexdigest().upper()

    def _sha256(self, data):
        """SHA256 hash hesapla.

        :param data: Hash verilecek string
        :returns: str - SHA256 hex digest (uppercase)
        """
        return hashlib.sha256(data.encode('utf-8')).hexdigest().upper()

    def _base64_encode(self, data):
        """Base64 encode.

        :param data: Encode edilecek bytes veya string
        :returns: str - Base64 encoded string
        """
        import base64
        if isinstance(data, str):
            data = data.encode('utf-8')
        return base64.b64encode(data).decode('utf-8')

    def _base64_decode(self, data):
        """Base64 decode.

        :param data: Decode edilecek string
        :returns: str - Decoded string
        """
        import base64
        return base64.b64decode(data).decode('utf-8')

    def _build_success_result(self, **kwargs):
        """Başarılı sonuç dict oluştur."""
        result = {
            'status': 'success',
            'error_code': '',
            'error_message': '',
        }
        result.update(kwargs)
        return result

    def _build_error_result(self, error_code='', error_message='', **kwargs):
        """Hatalı sonuç dict oluştur."""
        result = {
            'status': 'fail',
            'error_code': error_code,
            'error_message': error_message,
        }
        result.update(kwargs)
        return result
