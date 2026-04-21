import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Sanal POS provider kodları
SANAL_POS_PROVIDER_CODES = [
    'sanal_pos_garanti',
    'sanal_pos_estv3',
    'sanal_pos_payflex',
    'sanal_pos_posnet',
]


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    # --- Provider kodları ---
    code = fields.Selection(
        selection_add=[
            ('sanal_pos_garanti', "Garanti BBVA"),
            ('sanal_pos_estv3', "EstV3 (Akbank/İşbank/Ziraat)"),
            ('sanal_pos_payflex', "PayFlex (Vakıfbank)"),
            ('sanal_pos_posnet', "PosNet (YapıKredi)"),
        ],
        ondelete={
            'sanal_pos_garanti': 'set default',
            'sanal_pos_estv3': 'set default',
            'sanal_pos_payflex': 'set default',
            'sanal_pos_posnet': 'set default',
        },
    )

    # --- Gateway Kimlik Bilgileri ---
    sanal_pos_merchant_id = fields.Char(
        string="Merchant/Üye İşyeri No",
        groups='base.group_system',
    )
    sanal_pos_terminal_id = fields.Char(
        string="Terminal No",
        groups='base.group_system',
    )
    sanal_pos_store_key = fields.Char(
        string="Store Key / 3D Secure Anahtar",
        groups='base.group_system',
    )
    sanal_pos_provision_user = fields.Char(
        string="Provizyon Kullanıcı Adı",
        groups='base.group_system',
    )
    sanal_pos_provision_password = fields.Char(
        string="Provizyon Şifresi",
        groups='base.group_system',
    )
    sanal_pos_refund_user = fields.Char(
        string="İade Kullanıcı Adı",
        groups='base.group_system',
    )
    sanal_pos_refund_password = fields.Char(
        string="İade Şifresi",
        groups='base.group_system',
    )

    # --- API Endpoint'leri ---
    sanal_pos_api_url = fields.Char(string="API URL (Production)")
    sanal_pos_api_url_test = fields.Char(string="API URL (Test)")
    sanal_pos_3d_gate_url = fields.Char(string="3D Gate URL (Production)")
    sanal_pos_3d_gate_url_test = fields.Char(string="3D Gate URL (Test)")

    # --- Gateway ve Banka Tipi ---
    sanal_pos_gateway_type = fields.Selection(
        [
            ('garanti', "Garanti BBVA"),
            ('estv3', "EstV3 (Asseco/Payten)"),
            ('payflex', "PayFlex MPI VPOS"),
            ('posnet', "PosNet"),
        ],
        string="Gateway Tipi",
    )
    sanal_pos_bank_name = fields.Selection(
        [
            ('garanti', "Garanti BBVA"),
            ('akbank', "Akbank"),
            ('isbank', "Türkiye İş Bankası"),
            ('yapikredi', "Yapı Kredi"),
            ('ziraat', "Ziraat Bankası"),
            ('vakifbank', "Vakıfbank"),
            ('halkbank', "Halkbank"),
            ('finansbank', "QNB Finansbank"),
            ('teb', "TEB"),
            ('denizbank', "Denizbank"),
            ('kuveytturk', "Kuveyt Türk"),
        ],
        string="Banka",
    )

    # --- 3D Secure Ayarları ---
    sanal_pos_3d_secure_active = fields.Boolean(
        string="3D Secure Zorunlu",
        default=True,
    )
    sanal_pos_payment_model = fields.Selection(
        [
            ('3d_secure', "3D Secure"),
            ('3d_pay', "3D Pay"),
            ('3d_host', "3D Host"),
            ('non_secure', "Non-Secure (3D'siz)"),
        ],
        string="Ödeme Modeli",
        default='3d_secure',
    )

    # --- Taksit Ayarları ---
    sanal_pos_installment_active = fields.Boolean(
        string="Taksit Aktif",
        default=True,
    )
    sanal_pos_max_installment = fields.Integer(
        string="Maksimum Taksit Sayısı",
        default=12,
    )
    sanal_pos_min_installment_amount = fields.Float(
        string="Minimum Taksit Tutarı (TL)",
        default=100.0,
    )
    sanal_pos_installment_config_ids = fields.One2many(
        'sanal.pos.installment',
        'provider_id',
        string="Taksit Konfigürasyonları",
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    def _compute_feature_support_fields(self):
        """Override: Sanal POS provider'lar için feature support ayarla."""
        super()._compute_feature_support_fields()
        for provider in self.filtered(lambda p: p.code in SANAL_POS_PROVIDER_CODES):
            provider.support_refund = 'partial'
            provider.support_tokenization = False

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    def _is_sanal_pos_provider(self):
        """Bu provider bir Sanal POS provider mı?"""
        self.ensure_one()
        return self.code in SANAL_POS_PROVIDER_CODES

    def _get_default_payment_method_codes(self):
        """Override: Sanal POS provider'lar için varsayılan ödeme yöntemi."""
        self.ensure_one()
        if self._is_sanal_pos_provider():
            return ['card']
        return super()._get_default_payment_method_codes()

    def _sanal_pos_get_api_url(self):
        """Mevcut duruma göre (test/prod) aktif API URL döndürür."""
        self.ensure_one()
        if self.state == 'test':
            return self.sanal_pos_api_url_test
        return self.sanal_pos_api_url

    def _sanal_pos_get_3d_url(self):
        """Mevcut duruma göre (test/prod) aktif 3D Gate URL döndürür."""
        self.ensure_one()
        if self.state == 'test':
            return self.sanal_pos_3d_gate_url_test
        return self.sanal_pos_3d_gate_url

    def _sanal_pos_get_gateway(self):
        """Gateway factory - doğru gateway instance döndürür.

        :returns: BaseGateway subclass instance
        :raises UserError: Desteklenmeyen gateway tipi
        """
        self.ensure_one()
        from ..gateways import get_gateway
        try:
            return get_gateway(self)
        except ValueError as e:
            raise UserError(_("Gateway hatası: %s", str(e)))

    @api.onchange('sanal_pos_bank_name')
    def _onchange_sanal_pos_bank_name(self):
        """Banka seçildiğinde gateway tipi ve varsayılan URL'leri otomatik doldur."""
        bank_gateway_map = {
            'garanti': 'garanti',
            'akbank': 'estv3',
            'isbank': 'estv3',
            'ziraat': 'estv3',
            'vakifbank': 'payflex',
            'yapikredi': 'posnet',
            'halkbank': 'estv3',
            'finansbank': 'estv3',
            'teb': 'estv3',
            'denizbank': 'estv3',
            'kuveytturk': 'estv3',
        }
        bank_urls = {
            'garanti': {
                'api': 'https://sanalposprov.garantibbva.com.tr/VPServlet',
                'api_test': 'https://sanalposprovtest.garantibbva.com.tr/VPServlet',
                '3d': 'https://sanalposprov.garantibbva.com.tr/servlet/gt3dengine',
                '3d_test': 'https://sanalposprovtest.garantibbva.com.tr/servlet/gt3dengine',
            },
            'akbank': {
                'api': 'https://www.sanalakpos.com/fim/api',
                'api_test': 'https://entegrasyon.asseco-see.com.tr/fim/api',
                '3d': 'https://www.sanalakpos.com/fim/est3Dgate',
                '3d_test': 'https://entegrasyon.asseco-see.com.tr/fim/est3Dgate',
            },
            'isbank': {
                'api': 'https://sanalpos.isbank.com.tr/fim/api',
                'api_test': 'https://entegrasyon.asseco-see.com.tr/fim/api',
                '3d': 'https://sanalpos.isbank.com.tr/fim/est3Dgate',
                '3d_test': 'https://entegrasyon.asseco-see.com.tr/fim/est3Dgate',
            },
            'ziraat': {
                'api': 'https://sanalpos2.ziraatbank.com.tr/fim/api',
                'api_test': 'https://entegrasyon.asseco-see.com.tr/fim/api',
                '3d': 'https://sanalpos2.ziraatbank.com.tr/fim/est3Dgate',
                '3d_test': 'https://entegrasyon.asseco-see.com.tr/fim/est3Dgate',
            },
            'vakifbank': {
                'api': 'https://onlineodeme.vakifbank.com.tr/VirtualPOS/v3/ALLPayment',
                'api_test': 'https://onlineodemetest.vakifbank.com.tr/VirtualPOS/v3/ALLPayment',
                '3d': 'https://3dsecure.vakifbank.com.tr/MPIAPI/MPI_Enrollment.aspx',
                '3d_test': 'https://3dsecuretest.vakifbank.com.tr/MPIAPI/MPI_Enrollment.aspx',
            },
            'yapikredi': {
                'api': 'https://posnet.yapikredi.com.tr/PosnetWebService/XML',
                'api_test': 'https://setmpos.ykb.com/PosnetWebService/XML',
                '3d': 'https://posnet.yapikredi.com.tr/3DSWebService/YKBPaymentService',
                '3d_test': 'https://setmpos.ykb.com/3DSWebService/YKBPaymentService',
            },
        }

        if self.sanal_pos_bank_name:
            self.sanal_pos_gateway_type = bank_gateway_map.get(
                self.sanal_pos_bank_name, 'estv3'
            )
            urls = bank_urls.get(self.sanal_pos_bank_name, {})
            if urls:
                self.sanal_pos_api_url = urls.get('api', '')
                self.sanal_pos_api_url_test = urls.get('api_test', '')
                self.sanal_pos_3d_gate_url = urls.get('3d', '')
                self.sanal_pos_3d_gate_url_test = urls.get('3d_test', '')
