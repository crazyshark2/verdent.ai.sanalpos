class GatewayError(Exception):
    """Gateway temel hata sınıfı."""


class HashMismatchError(GatewayError):
    """Hash doğrulaması başarısız."""


class ConnectionError(GatewayError):
    """Banka iletişim hatası."""


class TimeoutError(GatewayError):
    """Banka yanıt zaman aşımı."""


class AuthenticationError(GatewayError):
    """Kimlik doğrulama hatası."""


class UnsupportedTransactionError(GatewayError):
    """Desteklenmeyen işlem tipi."""


class InvalidResponseError(GatewayError):
    """Geçersiz banka yanıtı."""


class RefundError(GatewayError):
    """İade işlemi hatası."""


class CancelError(GatewayError):
    """İptal işlemi hatası."""
