from odoo.tests.common import TransactionCase


class TestBinDetection(TransactionCase):
    """BIN veritabanı ve banka tanıma testleri."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bin_model = cls.env['sanal.pos.bin']

        cls.bin_garanti = cls.bin_model.create({
            'bin_number': '453188',
            'bank_name': 'Garanti BBVA',
            'bank_code': 'garanti',
            'card_network': 'visa',
            'card_type': 'credit',
            'card_category': 'gold',
            'is_active': True,
        })

        cls.bin_akbank = cls.bin_model.create({
            'bin_number': '557113',
            'bank_name': 'Akbank',
            'bank_code': 'akbank',
            'card_network': 'mastercard',
            'card_type': 'credit',
            'card_category': 'standard',
            'is_active': True,
        })

    def test_detect_garanti(self):
        """Garanti BIN algılama."""
        result = self.bin_model.detect_bank('453188')
        self.assertEqual(result['bank_code'], 'garanti')
        self.assertEqual(result['card_network'], 'visa')
        self.assertEqual(result['card_category'], 'gold')

    def test_detect_akbank(self):
        """Akbank BIN algılama."""
        result = self.bin_model.detect_bank('557113')
        self.assertEqual(result['bank_code'], 'akbank')
        self.assertEqual(result['card_network'], 'mastercard')

    def test_detect_with_full_card(self):
        """Tam kart numarasıyla algılama."""
        result = self.bin_model.detect_bank('4531 8800 0000 1234')
        self.assertEqual(result['bank_code'], 'garanti')

    def test_detect_unknown_bin(self):
        """Bilinmeyen BIN."""
        result = self.bin_model.detect_bank('999999')
        self.assertEqual(result, {})

    def test_detect_short_input(self):
        """Kısa input (6'dan az)."""
        result = self.bin_model.detect_bank('4531')
        self.assertEqual(result, {})

    def test_detect_empty_input(self):
        """Boş input."""
        result = self.bin_model.detect_bank('')
        self.assertEqual(result, {})

    def test_inactive_bin_not_detected(self):
        """Pasif BIN algılanmaz."""
        inactive_bin = self.bin_model.create({
            'bin_number': '999888',
            'bank_name': 'Test',
            'bank_code': 'other',
            'card_network': 'visa',
            'is_active': False,
        })
        result = self.bin_model.detect_bank('999888')
        self.assertEqual(result, {})
