import logging
from xml.etree import ElementTree as ET

_logger = logging.getLogger(__name__)


class ResponseParser:
    """Banka yanıtı ayrıştırıcı.

    Farklı bankaların XML/JSON yanıtlarını standart formata dönüştürür.
    """

    # -------------------------------------------------------------------------
    # Garanti BBVA
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_garanti_response(xml_string):
        """Garanti BBVA XML yanıtını parse et.

        :param xml_string: XML yanıt string
        :returns: dict(
            status, response_code, response_message,
            auth_code, host_ref_num, rrn, transaction_id,
            order_id, error_code, error_message
        )
        """
        try:
            root = ET.fromstring(xml_string)
        except ET.ParseError as e:
            return {
                'status': 'fail',
                'error_code': 'XML_PARSE_ERROR',
                'error_message': f'XML parse hatası: {e}',
            }

        # Transaction yanıtı
        tx_elem = root.find('.//Transaction')
        order_elem = root.find('.//Order')

        response_code = ''
        response_msg = ''
        auth_code = ''
        host_ref_num = ''
        rrn = ''
        transaction_id = ''
        order_id = ''

        if tx_elem is not None:
            resp = tx_elem.find('Response')
            if resp is not None:
                code_elem = resp.find('Code')
                msg_elem = resp.find('Message')
                response_code = code_elem.text if code_elem is not None else ''
                response_msg = msg_elem.text if msg_elem is not None else ''

            auth_elem = tx_elem.find('AuthCode')
            auth_code = auth_elem.text if auth_elem is not None else ''
            ref_elem = tx_elem.find('RetrefNum')
            host_ref_num = ref_elem.text if ref_elem is not None else ''
            rrn_elem = tx_elem.find('RRN')
            rrn = rrn_elem.text if rrn_elem is not None else ''
            batch_elem = tx_elem.find('BatchNum')

        if order_elem is not None:
            oid_elem = order_elem.find('OrderID')
            order_id = oid_elem.text if oid_elem is not None else ''

        is_success = response_code == '00'

        return {
            'status': 'success' if is_success else 'fail',
            'response_code': response_code,
            'response_message': response_msg,
            'auth_code': auth_code,
            'host_ref_num': host_ref_num,
            'rrn': rrn,
            'transaction_id': host_ref_num,
            'order_id': order_id,
            'error_code': '' if is_success else response_code,
            'error_message': '' if is_success else response_msg,
        }

    # -------------------------------------------------------------------------
    # EstV3
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_estv3_response(xml_string):
        """EstV3 (Asseco/Payten) XML yanıtını parse et.

        :param xml_string: XML yanıt string
        :returns: dict
        """
        try:
            root = ET.fromstring(xml_string)
        except ET.ParseError as e:
            return {
                'status': 'fail',
                'error_code': 'XML_PARSE_ERROR',
                'error_message': f'XML parse hatası: {e}',
            }

        def get_text(tag):
            elem = root.find(tag)
            return elem.text.strip() if elem is not None and elem.text else ''

        response = get_text('Response')
        is_success = response == 'Approved'

        return {
            'status': 'success' if is_success else 'fail',
            'response_code': get_text('ProcReturnCode'),
            'response_message': response,
            'auth_code': get_text('AuthCode'),
            'host_ref_num': get_text('HostRefNum'),
            'rrn': get_text('Rrn'),
            'transaction_id': get_text('TransId'),
            'order_id': get_text('OrderId'),
            'error_code': '' if is_success else get_text('ErrCode'),
            'error_message': '' if is_success else get_text('ErrMsg'),
        }

    # -------------------------------------------------------------------------
    # PayFlex
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_payflex_response(response_data):
        """PayFlex JSON/XML yanıtını parse et.

        :param response_data: dict veya XML string
        :returns: dict
        """
        if isinstance(response_data, str):
            try:
                root = ET.fromstring(response_data)
                data = {}
                for elem in root:
                    data[elem.tag] = elem.text or ''
                response_data = data
            except ET.ParseError:
                return {
                    'status': 'fail',
                    'error_code': 'PARSE_ERROR',
                    'error_message': 'PayFlex yanıtı okunamadı',
                }

        response_code = response_data.get('ResultCode', response_data.get('Rc', ''))
        is_success = response_code == '0000' or response_code == '00'

        return {
            'status': 'success' if is_success else 'fail',
            'response_code': response_code,
            'response_message': response_data.get('ResultDetail',
                                                   response_data.get('Message', '')),
            'auth_code': response_data.get('AuthCode', ''),
            'host_ref_num': response_data.get('HostRefNum',
                                               response_data.get('Rrn', '')),
            'rrn': response_data.get('Rrn', ''),
            'transaction_id': response_data.get('TransactionId', ''),
            'order_id': response_data.get('OrderId', ''),
            'error_code': '' if is_success else response_code,
            'error_message': '' if is_success else response_data.get(
                'ResultDetail', response_data.get('ErrorMessage', '')),
        }

    # -------------------------------------------------------------------------
    # PosNet
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_posnet_response(xml_string):
        """PosNet (YapıKredi) XML yanıtını parse et.

        :param xml_string: XML yanıt string
        :returns: dict
        """
        try:
            root = ET.fromstring(xml_string)
        except ET.ParseError as e:
            return {
                'status': 'fail',
                'error_code': 'XML_PARSE_ERROR',
                'error_message': f'XML parse hatası: {e}',
            }

        def get_text(xpath):
            elem = root.find(xpath)
            return elem.text.strip() if elem is not None and elem.text else ''

        approved = get_text('.//approved')
        is_success = approved == '1'

        return {
            'status': 'success' if is_success else 'fail',
            'response_code': get_text('.//respCode'),
            'response_message': get_text('.//respText'),
            'auth_code': get_text('.//authCode'),
            'host_ref_num': get_text('.//hostlogkey'),
            'rrn': get_text('.//rrn'),
            'transaction_id': get_text('.//hostlogkey'),
            'order_id': get_text('.//orderID'),
            'error_code': '' if is_success else get_text('.//respCode'),
            'error_message': '' if is_success else get_text('.//respText'),
        }

    # -------------------------------------------------------------------------
    # 3D Callback Parsers
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_3d_callback(provider_code, data):
        """Ortak 3D callback parser.

        :param provider_code: Provider kodu
        :param data: dict - POST parametreleri
        :returns: dict - Standart format
        """
        md_status = (
            data.get('mdStatus')
            or data.get('MdStatus')
            or data.get('mdstatus')
            or '0'
        )
        # MD Status 1 = Tam doğrulama, 2-4 = kısmi, 0/5+ = başarısız
        is_success = str(md_status) in ('1', '2', '3', '4')

        return {
            'status': 'success' if is_success else 'fail',
            'md_status': str(md_status),
            'auth_code': data.get('AuthCode', data.get('authCode', '')),
            'transaction_id': data.get('TransId', data.get('transId', '')),
            'eci': data.get('eci', data.get('Eci', '')),
            'cavv': data.get('cavv', data.get('Cavv', '')),
            'xid': data.get('xid', data.get('Xid', '')),
            'order_id': data.get('oid', data.get('OrderId',
                                 data.get('orderid', ''))),
            'error_code': data.get('ErrCode', data.get('errCode', '')),
            'error_message': data.get('ErrMsg', data.get('errMsg',
                                      data.get('mdErrorMsg', ''))),
        }
