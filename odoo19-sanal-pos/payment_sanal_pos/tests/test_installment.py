from odoo.tests.common import TransactionCase


class TestInstallment(TransactionCase):
    """Taksit hesaplama testleri."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env['payment.provider'].create({
            'name': 'Taksit Test Provider',
            'code': 'sanal_pos_garanti',
            'state': 'test',
            'sanal_pos_gateway_type': 'garanti',
            'sanal_pos_bank_name': 'garanti',
            'sanal_pos_installment_active': True,
            'sanal_pos_min_installment_amount': 100,
        })

        # 3 taksit, %1.5 faiz
        cls.installment_3 = cls.env['sanal.pos.installment'].create({
            'provider_id': cls.provider.id,
            'card_network': 'visa',
            'installment_count': 3,
            'interest_rate': 1.5,
            'is_active': True,
        })

        # 6 taksit, %3.5 faiz
        cls.installment_6 = cls.env['sanal.pos.installment'].create({
            'provider_id': cls.provider.id,
            'card_network': 'visa',
            'installment_count': 6,
            'interest_rate': 3.5,
            'is_active': True,
        })

    def test_installment_calculation_3(self):
        """3 taksit hesaplama."""
        result = self.installment_3.calculate_installment_amount(1000.0)
        self.assertEqual(result['rate'], 1.5)
        self.assertEqual(result['interest_amount'], 15.0)
        self.assertEqual(result['total_amount'], 1015.0)
        self.assertAlmostEqual(result['monthly_amount'], 338.33, places=2)

    def test_installment_calculation_6(self):
        """6 taksit hesaplama."""
        result = self.installment_6.calculate_installment_amount(1000.0)
        self.assertEqual(result['rate'], 3.5)
        self.assertEqual(result['interest_amount'], 35.0)
        self.assertEqual(result['total_amount'], 1035.0)
        self.assertAlmostEqual(result['monthly_amount'], 172.5, places=2)

    def test_category_rate_override(self):
        """Kategori bazlı oran override."""
        category = self.env['product.category'].create({
            'name': 'Elektronik',
        })
        self.env['sanal.pos.category.rate'].create({
            'installment_id': self.installment_3.id,
            'category_id': category.id,
            'interest_rate': 0.0,
            'is_active': True,
        })

        result = self.installment_3.calculate_installment_amount(
            1000.0, category_id=category.id
        )
        self.assertEqual(result['rate'], 0.0)
        self.assertEqual(result['interest_amount'], 0.0)
        self.assertEqual(result['total_amount'], 1000.0)

    def test_zero_interest(self):
        """Sıfır faiz hesaplama."""
        installment_0 = self.env['sanal.pos.installment'].create({
            'provider_id': self.provider.id,
            'card_network': 'mastercard',
            'installment_count': 2,
            'interest_rate': 0.0,
            'is_active': True,
        })
        result = installment_0.calculate_installment_amount(500.0)
        self.assertEqual(result['total_amount'], 500.0)
        self.assertEqual(result['monthly_amount'], 250.0)
