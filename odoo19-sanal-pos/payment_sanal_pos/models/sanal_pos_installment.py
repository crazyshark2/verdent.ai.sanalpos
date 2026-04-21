import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SanalPosInstallment(models.Model):
    _name = 'sanal.pos.installment'
    _description = 'Sanal POS Taksit Konfigürasyonu'
    _order = 'provider_id, card_network, installment_count'

    provider_id = fields.Many2one(
        'payment.provider',
        string="Ödeme Sağlayıcı",
        required=True,
        ondelete='cascade',
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
    installment_count = fields.Integer(
        string="Taksit Sayısı",
        required=True,
    )
    interest_rate = fields.Float(
        string="Faiz Oranı (%)",
        digits=(5, 2),
        default=0.0,
    )
    is_active = fields.Boolean(
        string="Aktif",
        default=True,
    )
    min_amount = fields.Float(
        string="Minimum Tutar (TL)",
        default=0.0,
    )
    max_amount = fields.Float(
        string="Maksimum Tutar (TL)",
        default=0.0,
        help="0 = limit yok",
    )
    category_rate_ids = fields.One2many(
        'sanal.pos.category.rate',
        'installment_id',
        string="Kategori Bazlı Oranlar",
    )

    _sql_constraints = [
        (
            'unique_installment',
            'unique(provider_id, card_network, installment_count)',
            'Aynı provider, kart ağı ve taksit sayısı için tekrar tanım yapılamaz.',
        ),
    ]

    def calculate_installment_amount(self, total_amount, category_id=None):
        """Taksit tutarını hesapla.

        Kategori bazlı oran varsa onu kullan, yoksa genel oranı kullan.

        :param total_amount: Toplam tutar
        :param category_id: Ürün kategori ID (opsiyonel)
        :returns: dict(monthly_amount, total_amount, interest_amount, rate)
        """
        self.ensure_one()
        rate = self.interest_rate

        # Kategori bazlı oran kontrolü
        if category_id and self.category_rate_ids:
            cat_rate = self.category_rate_ids.filtered(
                lambda r: r.category_id.id == category_id and r.is_active
            )
            if cat_rate:
                rate = cat_rate[0].interest_rate

        interest_amount = total_amount * (rate / 100.0)
        total_with_interest = total_amount + interest_amount
        monthly_amount = total_with_interest / self.installment_count

        return {
            'monthly_amount': round(monthly_amount, 2),
            'total_amount': round(total_with_interest, 2),
            'interest_amount': round(interest_amount, 2),
            'rate': rate,
        }
