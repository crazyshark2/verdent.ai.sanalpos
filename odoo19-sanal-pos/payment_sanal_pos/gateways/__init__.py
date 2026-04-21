from .base_gateway import BaseGateway
from .garanti_gateway import GarantiGateway
from .estv3_gateway import EstV3Gateway
from .payflex_gateway import PayFlexGateway
from .posnet_gateway import PosNetGateway

GATEWAY_REGISTRY = {
    'garanti': GarantiGateway,
    'estv3': EstV3Gateway,
    'payflex': PayFlexGateway,
    'posnet': PosNetGateway,
}


def get_gateway(provider):
    """Provider'a göre doğru gateway instance oluşturur.

    :param provider: payment.provider recordset
    :returns: BaseGateway subclass instance
    :raises ValueError: Desteklenmeyen gateway tipi
    """
    gateway_type = provider.sanal_pos_gateway_type
    gateway_cls = GATEWAY_REGISTRY.get(gateway_type)
    if not gateway_cls:
        raise ValueError(f"Desteklenmeyen gateway tipi: {gateway_type}")
    return gateway_cls(provider)
