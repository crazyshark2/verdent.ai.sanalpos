# Odoo 19 Türkiye Sanal POS Ödeme Sistemi

## Goal
Tam kapsamlı Odoo 19 sanal POS modülü geliştirmek.

## Steps

### step-1: Temel Altyapı (Faz 1)
- Modül iskeleti: __manifest__.py, __init__.py, security, models, gateways/base_gateway.py
- BIN veritabanı modeli + CSV data + post_init_hook
- Menü ve temel view XML'leri
> ACCEPT: Modül dosya yapısı oluşturulmuş, tüm model dosyaları mevcut, __manifest__.py doğru
> VERIFY[dispatch]: Dosya yapısı ve Python syntax kontrolü

### step-2: Garanti Gateway (Faz 2)
- GarantiGateway tam implementasyonu
- payment.provider + payment.transaction extend
- 3D Secure controller + callback
- Transaction log sistemi
> GATE: step-1
> ACCEPT: Garanti gateway kodu yazılmış, 3D akışı controller mevcut
> VERIFY[dispatch]: Kod review + syntax check

### step-3: Diğer Gateway'ler (Faz 3)
- EstV3Gateway (Akbank, İşbank, Ziraat, Halkbank, TEB)
- PayFlexGateway (Vakıfbank)
- PosNetGateway (YapıKredi)
> GATE: step-2
> ACCEPT: 3 gateway tam kodlanmış, provider data XML'leri mevcut

### step-4: Taksit Sistemi (Faz 4)
- Taksit modelleri + kategori bazlı oranlar
- Taksit API endpoint'leri
- Taksit yönetim view'ları
- Varsayılan taksit oranları data XML
> GATE: step-3
> ACCEPT: Taksit API çalışır, kategori bazlı oran override mantığı mevcut

### step-5: OWL Frontend (Faz 5)
- Ürün sayfası taksit tablosu widget
- Checkout ödeme formu + BIN tanıma + taksit seçici
- QWeb template'leri + SCSS
> GATE: step-4
> ACCEPT: Frontend JS/XML dosyaları mevcut, widget ürün sayfasına entegre

### step-6: İade/İptal (Faz 6)
- RefundWizard + CancelWizard
- İade/iptal controller endpoint'leri
- Transaction güncelleme
> GATE: step-5
> ACCEPT: Wizard'lar çalışır, iade/iptal gateway metodları bağlı

### step-7: Test + Son Kontrol (Faz 7)
- Unit test dosyaları
- Hata yönetimi iyileştirmeleri
- Son entegrasyon kontrolü
> GATE: step-6
> ACCEPT: Test dosyaları mevcut, modül bütünlüğü doğrulanmış
> REPORT: Proje tamamlandı
