from odoo.tests.common import TransactionCase


class TestGarantiGateway(TransactionCase):
    """Garanti BBVA Gateway unit testleri."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env['payment.provider'].create({
            'name': 'Garanti Test',
            'code': 'sanal_pos_garanti',
            'state': 'test',
            'sanal_pos_gateway_type': 'garanti',
            'sanal_pos_bank_name': 'garanti',
            'sanal_pos_merchant_id': '7000679',
            'sanal_pos_terminal_id': '30691298',
            'sanal_pos_store_key': '12345678',
            'sanal_pos_provision_user': 'PROVAUT',
            'sanal_pos_provision_password': '123qweASD/',
            'sanal_pos_api_url_test': 'https://sanalposprovtest.garantibbva.com.tr/VPServlet',
            'sanal_pos_3d_gate_url_test': 'https://sanalposprovtest.garantibbva.com.tr/servlet/gt3dengine',
        })

    def test_gateway_creation(self):
        """Gateway instance oluşturma."""
        gateway = self.provider._sanal_pos_get_gateway()
        self.assertEqual(gateway.__class__.__name__, 'GarantiGateway')
        self.assertTrue(gateway.test_mode)

    def test_3d_form_data(self):
        """3D form verisi oluşturma."""
        gateway = self.provider._sanal_pos_get_gateway()
        order = {
            'order_id': 'TEST123',
            'amount': 100.50,
            'currency': 'TRY',
            'installment': 1,
            'success_url': 'https://example.com/success',
            'fail_url': 'https://example.com/fail',
            'ip': '127.0.0.1',
            'email': 'test@test.com',
        }
        card = {
            'number': '4531444531442283',
            'holder': 'TEST USER',
            'exp_month': '12',
            'exp_year': '2030',
            'cvv': '123',
        }
        result = gateway.make_3d_form_data(order, card)

        self.assertIn('gateway_url', result)
        self.assertIn('inputs', result)
        self.assertEqual(result['method'], 'POST')
        self.assertIn('secure3dhash', result['inputs'])
        self.assertEqual(result['inputs']['orderid'], 'TEST123')

    def test_order_id_generation(self):
        """Benzersiz sipariş ID üretme."""
        gateway = self.provider._sanal_pos_get_gateway()
        oid1 = gateway._generate_order_id()
        oid2 = gateway._generate_order_id()
        self.assertNotEqual(oid1, oid2)
        self.assertTrue(oid1.startswith('SP'))

    def test_card_masking(self):
        """Kart numarası maskeleme."""
        gateway = self.provider._sanal_pos_get_gateway()
        masked = gateway._mask_card_number('4531444531442283')
        self.assertEqual(masked, '453144****2283')
        self.assertNotIn('4531442283', masked)

    def test_currency_code(self):
        """Para birimi ISO kodu."""
        gateway = self.provider._sanal_pos_get_gateway()
        self.assertEqual(gateway._get_currency_code('TRY'), '949')
        self.assertEqual(gateway._get_currency_code('USD'), '840')
        self.assertEqual(gateway._get_currency_code('EUR'), '978')
