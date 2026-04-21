{
    'name': 'Türkiye Sanal POS Ödeme Sistemi',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'Türk bankalarıyla sanal POS entegrasyonu - Taksit, 3D Secure, BIN tanıma',
    'description': """
Türkiye Sanal POS Ödeme Sistemi
================================
Desteklenen bankalar:
- Garanti BBVA
- Akbank (EstV3)
- Türkiye İş Bankası (EstV3)
- Ziraat Bankası (EstV3 / PayFlex)
- Vakıfbank (PayFlex)
- Yapı Kredi (PosNet)

Özellikler:
- 3D Secure ödeme akışı
- Taksit yönetimi (kategori bazlı)
- BIN numarasıyla otomatik banka tanıma
- Tam/kısmi iade ve iptal
- Detaylı loglama
    """,
    'author': 'Sanal POS Ekibi',
    'website': 'https://github.com/omerk/odoo19-sanal-pos',
    'license': 'LGPL-3',
    'depends': [
        'payment',
        'website_sale',
        'sale',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',
        'data/installment_default_data.xml',
        'views/menus.xml',
        'views/payment_provider_views.xml',
        'views/installment_views.xml',
        'views/category_rate_views.xml',
        'views/bin_views.xml',
        'views/transaction_log_views.xml',
        'views/refund_wizard_views.xml',
        'views/cancel_wizard_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_sanal_pos/static/src/scss/sanal_pos.scss',
            'payment_sanal_pos/static/src/js/bin_detector.js',
            'payment_sanal_pos/static/src/js/installment_selector.js',
            'payment_sanal_pos/static/src/js/installment_widget.js',
            'payment_sanal_pos/static/src/js/payment_form.js',
            'payment_sanal_pos/static/src/xml/installment_widget.xml',
            'payment_sanal_pos/static/src/xml/payment_form.xml',
            'payment_sanal_pos/static/src/xml/installment_selector.xml',
        ],
    },
    'post_init_hook': '_post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
