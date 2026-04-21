import hashlib
import hmac
import logging

_logger = logging.getLogger(__name__)


class HashHelper:
    """Banka hash hesaplama yardımcı sınıfı.

    Her bankanın kendine özgü hash algoritması vardır.
    Bu sınıf ortak hash hesaplama fonksiyonlarını sağlar.
    """

    @staticmethod
    def sha512(data):
        """SHA512 hash hesapla.

        :param data: str
        :returns: str - uppercase hex digest
        """
        return hashlib.sha512(data.encode('utf-8')).hexdigest().upper()

    @staticmethod
    def sha256(data):
        """SHA256 hash hesapla.

        :param data: str
        :returns: str - uppercase hex digest
        """
        return hashlib.sha256(data.encode('utf-8')).hexdigest().upper()

    @staticmethod
    def sha1(data):
        """SHA1 hash hesapla.

        :param data: str
        :returns: str - uppercase hex digest
        """
        return hashlib.sha1(data.encode('utf-8')).hexdigest().upper()

    @staticmethod
    def md5(data):
        """MD5 hash hesapla.

        :param data: str
        :returns: str - uppercase hex digest
        """
        return hashlib.md5(data.encode('utf-8')).hexdigest().upper()

    @staticmethod
    def hmac_sha512(key, data):
        """HMAC-SHA512 hesapla.

        :param key: str - Secret key
        :param data: str - Data
        :returns: str - uppercase hex digest
        """
        return hmac.new(
            key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha512,
        ).hexdigest().upper()

    @staticmethod
    def hmac_sha256(key, data):
        """HMAC-SHA256 hesapla.

        :param key: str - Secret key
        :param data: str - Data
        :returns: str - uppercase hex digest
        """
        return hmac.new(
            key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest().upper()

    # -------------------------------------------------------------------------
    # Garanti BBVA Hash
    # -------------------------------------------------------------------------

    @staticmethod
    def garanti_security_data(password, terminal_id):
        """Garanti BBVA SecurityData hesapla.

        SecurityData = SHA512(Password + '0' + TerminalID)

        :param password: Provizyon şifresi
        :param terminal_id: Terminal ID (9 hane)
        :returns: str - uppercase hex digest
        """
        # TerminalID 9 hane olmalı (soldan 0 ile doldur)
        terminal_id = str(terminal_id).zfill(9)
        data = password + '0' + terminal_id
        return hashlib.sha512(data.encode('utf-8')).hexdigest().upper()

    @staticmethod
    def garanti_hash_data(security_data, *params):
        """Garanti BBVA HashData hesapla.

        HashData = SHA512(param1 + param2 + ... + SecurityData)

        :param security_data: SecurityData değeri
        :param params: Hash'e eklenecek parametreler (sıralı)
        :returns: str - uppercase hex digest
        """
        data = ''.join(str(p) for p in params) + security_data
        return hashlib.sha512(data.encode('utf-8')).hexdigest().upper()

    # -------------------------------------------------------------------------
    # EstV3 Hash
    # -------------------------------------------------------------------------

    @staticmethod
    def estv3_hash(store_key, *params):
        """EstV3 hash hesapla (SHA512).

        Hash = SHA512(param1|param2|...|storeKey)
        Parametre ayırıcı: | (pipe)

        :param store_key: Store Key (3D Secure anahtarı)
        :param params: Hash'e eklenecek parametreler (sıralı)
        :returns: str - base64 encoded SHA512 hash
        """
        import base64
        separator = '|'
        data = separator.join(str(p) for p in params) + separator + store_key
        hash_bytes = hashlib.sha512(data.encode('utf-8')).digest()
        return base64.b64encode(hash_bytes).decode('utf-8')

    # -------------------------------------------------------------------------
    # PayFlex Hash
    # -------------------------------------------------------------------------

    @staticmethod
    def payflex_hash(password, terminal_no, *params):
        """PayFlex VPOS hash hesapla.

        :param password: Şifre
        :param terminal_no: Terminal no
        :param params: Ek parametreler
        :returns: str - SHA512 hex digest
        """
        data = password + terminal_no + ''.join(str(p) for p in params)
        return hashlib.sha512(data.encode('utf-8')).hexdigest().upper()

    # -------------------------------------------------------------------------
    # PosNet MAC
    # -------------------------------------------------------------------------

    @staticmethod
    def posnet_mac(encryption_key, *params):
        """PosNet (YapıKredi) MAC hesapla.

        :param encryption_key: Şifreleme anahtarı
        :param params: MAC parametreleri
        :returns: str
        """
        data = ''.join(str(p) for p in params)
        return hmac.new(
            bytes.fromhex(encryption_key),
            data.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest().upper()
