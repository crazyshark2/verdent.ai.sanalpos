import csv
import logging
import os

_logger = logging.getLogger(__name__)

# BIN bankası adından banka koduna eşleme
BANK_NAME_TO_CODE = {
    'TURKIYE GARANTI BANKASI': 'garanti',
    'GARANTI BBVA': 'garanti',
    'T. GARANTI BANKASI A.S.': 'garanti',
    'TURKIYE GARANTI BANKASI A.S.': 'garanti',
    'AKBANK T.A.S.': 'akbank',
    'AKBANK': 'akbank',
    'TURKIYE IS BANKASI': 'isbank',
    'TURKIYE IS BANKASI A.S.': 'isbank',
    'T. IS BANKASI A.S.': 'isbank',
    'YAPI VE KREDI BANKASI': 'yapikredi',
    'YAPI VE KREDI BANKASI A.S.': 'yapikredi',
    'YAPI KREDI': 'yapikredi',
    'T.C. ZIRAAT BANKASI': 'ziraat',
    'T.C. ZIRAAT BANKASI A.S.': 'ziraat',
    'ZIRAAT BANKASI': 'ziraat',
    'TURKIYE VAKIFLAR BANKASI': 'vakifbank',
    'TURKIYE VAKIFLAR BANKASI T.A.O.': 'vakifbank',
    'VAKIFBANK': 'vakifbank',
    'TURKIYE HALK BANKASI': 'halkbank',
    'TURKIYE HALK BANKASI A.S.': 'halkbank',
    'QNB FINANSBANK': 'finansbank',
    'QNB FINANSBANK A.S.': 'finansbank',
    'FINANSBANK A.S.': 'finansbank',
    'TURK EKONOMI BANKASI': 'teb',
    'TURK EKONOMI BANKASI A.S.': 'teb',
    'TEB': 'teb',
    'DENIZBANK': 'denizbank',
    'DENIZBANK A.S.': 'denizbank',
    'KUVEYT TURK': 'kuveytturk',
    'KUVEYT TURK KATILIM BANKASI': 'kuveytturk',
    'KUVEYT TURK KATILIM BANKASI A.S.': 'kuveytturk',
    'SEKERBANK': 'sekerbank',
    'SEKERBANK T.A.S.': 'sekerbank',
    'ING BANK A.S.': 'ingbank',
    'HSBC BANK A.S.': 'hsbc',
    'TURKIYE FINANS KATILIM BANKASI': 'turkiyefinans',
}

NETWORK_MAP = {
    'VISA': 'visa',
    'MASTERCARD': 'mastercard',
    'TROY': 'troy',
    'AMERICAN EXPRESS': 'amex',
    'AMEX': 'amex',
}

TYPE_MAP = {
    'CREDIT': 'credit',
    'DEBIT': 'debit',
    'PREPAID': 'prepaid',
}

CATEGORY_MAP = {
    'STANDARD': 'standard',
    'CLASSIC': 'classic',
    'GOLD': 'gold',
    'PLATINUM': 'platinum',
    'BUSINESS': 'business',
    'COMMERCIAL': 'commercial',
    'INFINITE': 'infinite',
    'WORLD': 'world',
    'ELECTRON': 'standard',
    'TITANIUM': 'platinum',
}


def _map_bank_code(issuer_name):
    """Banka adından banka koduna dönüştür."""
    if not issuer_name:
        return 'other'
    name_upper = issuer_name.strip().upper()
    for key, code in BANK_NAME_TO_CODE.items():
        if key in name_upper:
            return code
    return 'other'


def _post_init_hook(env):
    """Modül kurulumunda BIN veritabanını CSV'den yükle."""
    csv_path = os.path.join(os.path.dirname(__file__), 'data', 'bin_data.csv')
    if not os.path.exists(csv_path):
        _logger.warning("BIN veri dosyası bulunamadı: %s", csv_path)
        return

    _logger.info("BIN veritabanı yükleniyor: %s", csv_path)
    BinModel = env['sanal.pos.bin']

    vals_list = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                bin_number = row.get('BIN', '').strip()
                if not bin_number:
                    continue
                network_raw = row.get('Network', '').strip().upper()
                type_raw = row.get('Type', '').strip().upper()
                category_raw = row.get('Category', '').strip().upper()
                issuer = row.get('Issuer', '').strip()

                card_network = NETWORK_MAP.get(network_raw, 'visa')
                card_type = TYPE_MAP.get(type_raw, 'credit')
                card_category = CATEGORY_MAP.get(category_raw, 'standard')

                vals_list.append({
                    'bin_number': bin_number,
                    'bank_name': issuer,
                    'bank_code': _map_bank_code(issuer),
                    'card_network': card_network,
                    'card_type': card_type,
                    'card_category': card_category,
                    'is_active': True,
                })
    except Exception as e:
        _logger.error("BIN veritabanı yükleme hatası: %s", e)
        return

    if vals_list:
        # Toplu oluşturma
        try:
            BinModel.create(vals_list)
            _logger.info("%d BIN kaydı başarıyla yüklendi.", len(vals_list))
        except Exception as e:
            _logger.error("BIN kayıtları oluşturulurken hata: %s", e)
