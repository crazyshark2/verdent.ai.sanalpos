import logging
from xml.etree import ElementTree as ET

_logger = logging.getLogger(__name__)


class RequestBuilder:
    """XML/JSON request oluşturucu.

    Her banka gateway'inin kendine özgü XML/JSON formatı vardır.
    Bu sınıf ortak builder fonksiyonlarını sağlar.
    """

    # -------------------------------------------------------------------------
    # Garanti BBVA XML
    # -------------------------------------------------------------------------

    @staticmethod
    def garanti_payment_xml(terminal, order, card=None, transaction=None,
                            hash_data=''):
        """Garanti BBVA ödeme XML isteği oluştur.

        :param terminal: dict(id, merchant_id, user, password)
        :param order: dict(order_id, amount, currency_code, installment, description)
        :param card: dict(number, exp_month, exp_year, cvv) veya None
        :param transaction: dict(type, amount, currency_code, installment,
                                 card_holder_present)
        :param hash_data: str - Hash değeri
        :returns: str - XML string
        """
        root = ET.Element('GVPSRequest')

        # Mode
        mode_elem = ET.SubElement(root, 'Mode')
        mode_elem.text = 'TEST' if not transaction else 'PROD'

        # Version
        version = ET.SubElement(root, 'Version')
        version.text = 'v1.0'

        # Terminal
        term_elem = ET.SubElement(root, 'Terminal')
        for key, tag in [('id', 'ProvUserID'), ('user', 'UserID'),
                         ('merchant_id', 'MerchantID')]:
            elem = ET.SubElement(term_elem, tag)
            elem.text = str(terminal.get(key, ''))
        hash_elem = ET.SubElement(term_elem, 'HashData')
        hash_elem.text = hash_data
        id_elem = ET.SubElement(term_elem, 'ID')
        id_elem.text = str(terminal.get('id', ''))

        # Customer
        customer = ET.SubElement(root, 'Customer')
        ip = ET.SubElement(customer, 'IPAddress')
        ip.text = order.get('ip', '127.0.0.1')
        email = ET.SubElement(customer, 'EmailAddress')
        email.text = order.get('email', '')

        # Card
        if card:
            card_elem = ET.SubElement(root, 'Card')
            number = ET.SubElement(card_elem, 'Number')
            number.text = card.get('number', '')
            exp_date = ET.SubElement(card_elem, 'ExpireDate')
            # Garanti format: MMYY
            exp_date.text = f"{card.get('exp_month', '01')}{card.get('exp_year', '99')[-2:]}"
            cvv = ET.SubElement(card_elem, 'CVV2')
            cvv.text = card.get('cvv', '')

        # Order
        order_elem = ET.SubElement(root, 'Order')
        oid = ET.SubElement(order_elem, 'OrderID')
        oid.text = order.get('order_id', '')
        if order.get('description'):
            desc = ET.SubElement(order_elem, 'Description')
            desc.text = order['description']

        # Transaction
        if transaction:
            tx = ET.SubElement(root, 'Transaction')
            tx_type = ET.SubElement(tx, 'Type')
            tx_type.text = transaction.get('type', 'sales')
            amount_elem = ET.SubElement(tx, 'Amount')
            amount_elem.text = str(transaction.get('amount', '0'))
            curr = ET.SubElement(tx, 'CurrencyCode')
            curr.text = str(transaction.get('currency_code', '949'))
            installment = ET.SubElement(tx, 'InstallmentCnt')
            inst_count = transaction.get('installment', 1)
            installment.text = '' if inst_count <= 1 else str(inst_count)
            chp = ET.SubElement(tx, 'CardholderPresentCode')
            chp.text = str(transaction.get('card_holder_present', '13'))

        return ET.tostring(root, encoding='unicode', xml_declaration=True)

    # -------------------------------------------------------------------------
    # EstV3 XML
    # -------------------------------------------------------------------------

    @staticmethod
    def estv3_payment_xml(client_id, order_id, amount, currency_code,
                          tx_type='Auth', installment=1, card=None,
                          extra_params=None):
        """EstV3 (Asseco/Payten) ödeme XML isteği oluştur.

        :returns: str - XML string
        """
        root = ET.Element('CC5Request')

        name = ET.SubElement(root, 'Name')
        name.text = ''  # prov user
        password = ET.SubElement(root, 'Password')
        password.text = ''  # prov password
        cid = ET.SubElement(root, 'ClientId')
        cid.text = str(client_id)
        mode = ET.SubElement(root, 'Mode')
        mode.text = 'P'  # Production
        type_elem = ET.SubElement(root, 'Type')
        type_elem.text = tx_type

        oid = ET.SubElement(root, 'OrderId')
        oid.text = order_id

        if card:
            num = ET.SubElement(root, 'Number')
            num.text = card.get('number', '')
            exp = ET.SubElement(root, 'Expires')
            exp.text = f"{card.get('exp_month', '01')}/{card.get('exp_year', '99')[-2:]}"
            cvv = ET.SubElement(root, 'Cvv2Val')
            cvv.text = card.get('cvv', '')

        total = ET.SubElement(root, 'Total')
        total.text = str(amount)
        curr = ET.SubElement(root, 'Currency')
        curr.text = str(currency_code)
        inst = ET.SubElement(root, 'Taksit')
        inst.text = '' if installment <= 1 else str(installment)

        if extra_params:
            for key, value in extra_params.items():
                elem = ET.SubElement(root, key)
                elem.text = str(value)

        return ET.tostring(root, encoding='unicode', xml_declaration=True)

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_xml_response(xml_string):
        """XML yanıtını dict'e dönüştür.

        :param xml_string: XML string
        :returns: dict - Tüm element'ler key-value olarak
        """
        try:
            root = ET.fromstring(xml_string)
            result = {}

            def _parse_element(elem, prefix=''):
                tag = f"{prefix}.{elem.tag}" if prefix else elem.tag
                if elem.text and elem.text.strip():
                    result[tag] = elem.text.strip()
                for child in elem:
                    _parse_element(child, tag)

            _parse_element(root)
            return result
        except ET.ParseError as e:
            _logger.error("XML parse hatası: %s", e)
            return {'parse_error': str(e), 'raw': xml_string}
