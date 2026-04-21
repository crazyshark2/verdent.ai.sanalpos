import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SanalPosBin(models.Model):
    _name = 'sanal.pos.bin'
    _description = 'BIN Veritabanı'
    _order = 'bin_number'

    bin_number = fields.Char(
        string="BIN (İlk 6-8 Hane)",
        required=True,
        size=8,
        index=True,
    )
    bank_name = fields.Char(
        string="Banka Adı",
        required=True,
        index=True,
    )
    bank_code = fields.Selection(
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
            ('sekerbank', "Şekerbank"),
            ('ingbank', "ING Bank"),
            ('hsbc', "HSBC"),
            ('turkiyefinans', "Türkiye Finans"),
            ('other', "Diğer"),
        ],
        string="Banka Kodu",
        index=True,
        default='other',
    )
    card_network = fields.Selection(
        [
            ('visa', "Visa"),
            ('mastercard', "Mastercard"),
            ('troy', "Troy"),
            ('amex', "American Express"),
        ],
        string="Kart Ağı",
        required=True,
    )
    card_type = fields.Selection(
        [
            ('credit', "Kredi Kartı"),
            ('debit', "Banka Kartı"),
            ('prepaid', "Ön Ödemeli"),
        ],
        string="Kart Tipi",
        default='credit',
    )
    card_category = fields.Selection(
        [
            ('standard', "Standard"),
            ('classic', "Classic"),
            ('gold', "Gold"),
            ('platinum', "Platinum"),
            ('business', "Business"),
            ('commercial', "Commercial"),
            ('infinite', "Infinite"),
            ('world', "World"),
        ],
        string="Kart Kategorisi",
        default='standard',
    )
    is_active = fields.Boolean(
        string="Aktif",
        default=True,
    )

    _sql_constraints = [
        (
            'unique_bin',
            'unique(bin_number)',
            'BIN numarası benzersiz olmalıdır.',
        ),
    ]

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    @api.model
    def detect_bank(self, card_number_prefix):
        """İlk 6-8 haneye göre banka ve kart bilgisi döndürür.

        :param card_number_prefix: Kart numarasının ilk haneleri (en az 6)
        :returns: dict(bank_name, bank_code, card_network, card_type, card_category)
                  veya bulunamazsa boş dict
        """
        if not card_number_prefix:
            return {}
        prefix = card_number_prefix.replace(' ', '').replace('-', '')[:8]
        if len(prefix) < 6:
            return {}

        # Önce 8 hane, sonra 7, sonra 6 hanede ara
        for length in (8, 7, 6):
            search_bin = prefix[:length]
            if len(search_bin) < length:
                continue
            record = self.search(
                [('bin_number', '=', search_bin), ('is_active', '=', True)],
                limit=1,
            )
            if record:
                return {
                    'bank_name': record.bank_name,
                    'bank_code': record.bank_code,
                    'card_network': record.card_network,
                    'card_type': record.card_type,
                    'card_category': record.card_category,
                }
        return {}

    @api.model
    def get_available_installments(self, card_number_prefix, amount, category_id=None):
        """BIN'e göre banka tespit et, o bankaya ait aktif provider'ların
        taksit seçeneklerini hesaplayarak döndür.

        :param card_number_prefix: Kart numarasının ilk haneleri
        :param amount: Ödeme tutarı
        :param category_id: Ürün kategori ID (opsiyonel)
        :returns: dict(bank, card_network, card_type, installments)
        """
        bank_info = self.detect_bank(card_number_prefix)
        if not bank_info:
            return {'bank': None, 'installments': []}

        bank_code = bank_info.get('bank_code', 'other')
        card_network = bank_info.get('card_network', 'visa')

        # Bu bankaya ait aktif provider bul
        providers = self.env['payment.provider'].sudo().search([
            ('sanal_pos_bank_name', '=', bank_code),
            ('state', 'in', ('enabled', 'test')),
            ('sanal_pos_installment_active', '=', True),
        ])

        if not providers:
            return {
                'bank': bank_info,
                'card_network': card_network,
                'installments': [
                    {'count': 1, 'monthly': amount, 'total': amount, 'rate': 0.0}
                ],
            }

        provider = providers[0]
        installment_configs = self.env['sanal.pos.installment'].search([
            ('provider_id', '=', provider.id),
            ('card_network', '=', card_network),
            ('is_active', '=', True),
        ], order='installment_count asc')

        installments = []
        # Tek çekim her zaman ekle
        installments.append({
            'count': 1,
            'monthly': round(amount, 2),
            'total': round(amount, 2),
            'rate': 0.0,
        })

        min_amount = provider.sanal_pos_min_installment_amount or 0
        if amount >= min_amount:
            for config in installment_configs:
                if config.installment_count <= 1:
                    continue
                if config.min_amount and amount < config.min_amount:
                    continue
                if config.max_amount and amount > config.max_amount:
                    continue

                result = config.calculate_installment_amount(
                    amount, category_id=category_id
                )
                installments.append({
                    'count': config.installment_count,
                    'monthly': result['monthly_amount'],
                    'total': result['total_amount'],
                    'rate': result['rate'],
                })

        return {
            'bank': bank_info,
            'card_network': card_network,
            'installments': installments,
        }
