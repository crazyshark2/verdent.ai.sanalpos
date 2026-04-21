import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class InstallmentController(http.Controller):
    """Taksit bilgisi REST API controller."""

    @http.route(
        '/sanal_pos/installments/by_bin',
        type='json', auth='public', methods=['POST'],
        csrf=False, website=True,
    )
    def get_installments_by_bin(self, bin_number, amount, category_id=None, **kwargs):
        """BIN numarasına göre taksit seçenekleri döndür.

        :param bin_number: str - Kart ilk 6 hanesi
        :param amount: float - Ödeme tutarı
        :param category_id: int - Ürün kategori ID (opsiyonel)
        :returns: dict(bank, card_network, card_type, installments)
        """
        if not bin_number or len(str(bin_number).strip()) < 6:
            return {
                'bank': None,
                'installments': [],
                'error': 'En az 6 haneli BIN numarası gerekli',
            }

        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return {
                'bank': None,
                'installments': [],
                'error': 'Geçersiz tutar',
            }

        cat_id = int(category_id) if category_id else None

        result = request.env['sanal.pos.bin'].sudo().get_available_installments(
            str(bin_number).strip(), amount, category_id=cat_id,
        )

        return result

    @http.route(
        '/sanal_pos/installments/by_product',
        type='json', auth='public', methods=['POST'],
        website=True,
    )
    def get_installments_for_product(self, product_id, **kwargs):
        """Ürün sayfası taksit tablosu - tüm aktif bankaların taksit seçenekleri.

        :param product_id: int - product.template ID
        :returns: dict(product_price, banks)
        """
        product = request.env['product.template'].sudo().browse(int(product_id))
        if not product.exists():
            return {'product_price': 0, 'banks': [], 'error': 'Ürün bulunamadı'}

        price = product.list_price
        if price <= 0:
            return {'product_price': 0, 'banks': []}

        # Ürün kategorisi
        category_id = product.categ_id.id if product.categ_id else None

        # Tüm aktif provider'ları bul
        providers = request.env['payment.provider'].sudo().search([
            ('code', 'in', [
                'sanal_pos_garanti', 'sanal_pos_estv3',
                'sanal_pos_payflex', 'sanal_pos_posnet',
            ]),
            ('state', 'in', ('enabled', 'test')),
            ('sanal_pos_installment_active', '=', True),
        ])

        banks = []
        seen_bank_codes = set()

        for provider in providers:
            bank_code = provider.sanal_pos_bank_name
            if bank_code in seen_bank_codes:
                continue
            seen_bank_codes.add(bank_code)

            bank_name = dict(
                provider._fields['sanal_pos_bank_name'].selection
            ).get(bank_code, bank_code)

            # Her kart ağı için taksit seçeneklerini hesapla
            # Varsayılan olarak Visa ve Mastercard göster
            all_installments = []
            for network in ('visa', 'mastercard'):
                configs = request.env['sanal.pos.installment'].sudo().search([
                    ('provider_id', '=', provider.id),
                    ('card_network', '=', network),
                    ('is_active', '=', True),
                ], order='installment_count asc')

                installments = [{
                    'count': 1,
                    'monthly': round(price, 2),
                    'total': round(price, 2),
                    'rate': 0.0,
                }]

                min_amount = provider.sanal_pos_min_installment_amount or 0
                if price >= min_amount:
                    for config in configs:
                        if config.installment_count <= 1:
                            continue
                        if config.min_amount and price < config.min_amount:
                            continue
                        if config.max_amount and price > config.max_amount:
                            continue

                        result = config.calculate_installment_amount(
                            price, category_id=category_id,
                        )
                        installments.append({
                            'count': config.installment_count,
                            'monthly': result['monthly_amount'],
                            'total': result['total_amount'],
                            'rate': result['rate'],
                        })

                if installments:
                    all_installments = installments
                    break  # İlk bulunan network yeterli

            if all_installments:
                banks.append({
                    'name': bank_name,
                    'code': bank_code,
                    'installments': all_installments,
                })

        return {
            'product_price': price,
            'banks': banks,
        }

    @http.route(
        '/sanal_pos/bin/detect',
        type='json', auth='public', methods=['POST'],
        csrf=False,
    )
    def detect_bin(self, bin_number, **kwargs):
        """BIN numarası ile banka tanıma.

        :param bin_number: str - Kart ilk 6 hanesi
        :returns: dict(bank_name, bank_code, card_network, card_type, card_category)
        """
        if not bin_number or len(str(bin_number).strip()) < 6:
            return {}

        return request.env['sanal.pos.bin'].sudo().detect_bank(
            str(bin_number).strip()
        )
