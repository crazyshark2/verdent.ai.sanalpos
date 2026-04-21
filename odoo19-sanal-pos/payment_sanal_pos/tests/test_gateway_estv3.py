from odoo.tests.common import TransactionCase


class TestEstV3Gateway(TransactionCase):
    """EstV3 Gateway (Akbank/İşbank/Ziraat) unit testleri."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env['payment.provider'].create({
            'name': 'Akbank Test',
            'code': 'sanal_pos_estv3',
            'state': 'test',
            'sanal_pos_gateway_type': 'estv3',
            'sanal_pos_bank_name': 'akbank',
            'sanal_pos_merchant_id': '100100000',
            'sanal_pos_terminal_id': '10010000',
            'sanal_pos_store_key': 'TRPS0200',
            'sanal_pos_provision_user': 'apiuser',
            'sanal_pos_provision_password': 'apipassword',
            'sanal_pos_api_url_test': 'https://entegrasyon.asseco-see.com.tr/fim/api',
            'sanal_pos_3d_gate_url_test': 'https://entegrasyon.asseco-see.com.tr/fim/est3Dgate',
        })

    def test_gateway_creation(self):
        """Gateway instance oluşturma."""
        gateway = self.provider._sanal_pos_get_gateway()
        self.assertEqual(gateway.__class__.__name__, 'EstV3Gateway')

    def test_3d_form_data(self):
        """3D form verisi oluşturma."""
        gateway = self.provider._sanal_pos_get_gateway()
        order = {
            'order_id': 'TEST456',
            'amount': 250.00,
            'currency': 'TRY',
            'installment': 3,
            'success_url': 'https://example.com/success',
            'fail_url': 'https://example.com/fail',
        }
        card = {
            'number': '5571135571135575',
            'holder': 'TEST USER',
            'exp_month': '12',
            'exp_year': '2030',
            'cvv': '123',
        }
        result = gateway.make_3d_form_data(order, card)

        self.assertIn('gateway_url', result)
        self.assertIn('inputs', result)
        self.assertEqual(result['inputs']['oid'], 'TEST456')
        self.assertEqual(result['inputs']['amount'], '250.00')
        self.assertEqual(result['inputs']['taksit'], '3')
        self.assertIn('hash', result['inputs'])

    def test_hash_validation(self):
        """Hash doğrulama - sahte veri ile başarısız."""
        gateway = self.provider._sanal_pos_get_gateway()
        self.assertFalse(gateway.validate_hash({'hash': 'fake_hash'}))
