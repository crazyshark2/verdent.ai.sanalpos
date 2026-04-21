from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    sanal_pos_installment_enabled = fields.Boolean(
        string="Taksit Tablosu Göster",
        default=True,
        help="Ürün sayfasında taksit seçenekleri tablosunu gösterir.",
    )
    sanal_pos_max_installment = fields.Integer(
        string="Maksimum Taksit",
        default=0,
        help="0 = provider ayarlarındaki varsayılanı kullan",
    )
