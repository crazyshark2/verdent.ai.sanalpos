from odoo import fields, models


class SanalPosCategoryRate(models.Model):
    _name = 'sanal.pos.category.rate'
    _description = 'Kategori Bazlı Taksit Oranı'

    installment_id = fields.Many2one(
        'sanal.pos.installment',
        string="Taksit Tanımı",
        required=True,
        ondelete='cascade',
    )
    category_id = fields.Many2one(
        'product.category',
        string="Ürün Kategorisi",
        required=True,
    )
    interest_rate = fields.Float(
        string="Kategori Özel Faiz Oranı (%)",
        digits=(5, 2),
    )
    is_active = fields.Boolean(
        string="Aktif",
        default=True,
    )

    _sql_constraints = [
        (
            'unique_cat_rate',
            'unique(installment_id, category_id)',
            'Bir taksit tanımı için her kategoride yalnızca bir oran olabilir.',
        ),
    ]
