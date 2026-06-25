# Senin Yapacakların — App Store'a Çıkış

Kod tarafı bitti (IAP, doğrulama, gizlilik sayfaları, uyum). Aşağıdakiler **yalnızca senin
yapabileceğin** Apple hesabı / finans / portal + deploy adımlarıdır. Sırayla git.

Bundle ID (her yerde aynı): **com.bilyadadus.app**

---

## 0) Ön koşul
- [ ] **Apple Developer Program** üyeliği (yıllık ~$99) — developer.apple.com/programs

## 1) Backend'i canlıya al (en kritik — bu olmadan inceleme reddeder)
Apple inceleme ekibi uygulamayı çalıştırır; backend'e HTTPS ile ulaşmalı.
- [ ] Backend'i deploy et (`DEPLOY.md` — Railway). Bir HTTPS alan adı al: `https://<domain>`
- [ ] Sunucu ortam değişkenlerini (env) ayarla:
  - `IAP_SANDBOX=false`  ← **gerçek para için şart**
  - `APPLE_BUNDLE_ID=com.bilyadadus.app`
  - `APPLE_SHARED_SECRET=<Adım 4'te alacaksın>`
  - `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET` (güçlü), `CORS` vb. (`.env.example`)
- [ ] `https://<domain>/health` → 200, `https://<domain>/legal/privacy` ve `/legal/terms` açılıyor mu kontrol et (Gizlilik Politikası URL'in artık hazır).

## 2) App Store Connect — Sözleşme & Finans (IAP satmak için zorunlu)
- [ ] App Store Connect → **Agreements, Tax, and Banking** → "Paid Apps" sözleşmesini kabul et
- [ ] Banka hesabı + vergi bilgilerini gir (onaylanması 1-2 gün sürebilir)

## 3) Uygulama kaydı
- [ ] developer.apple.com → Identifiers → App ID **com.bilyadadus.app** oluştur, **In-App Purchase** yeteneğini işaretle
- [ ] App Store Connect → My Apps → **+** → yeni uygulama (bundle id'yi seç, isim "Bil ya da Düş")

## 4) IAP ürünlerini oluştur  (ayrıntı: `03_iap_setup.md`)
App Store Connect → uygulaman → In-App Purchases / Subscriptions:
- [ ] **Consumable** (4 adet — altın):
  - `com.bilyadadus.gold_small`  → ₺29,99 fiyat seviyesi
  - `com.bilyadadus.gold_medium` → ₺59,99
  - `com.bilyadadus.gold_large`  → ₺119,99
  - `com.bilyadadus.gold_mega`   → ₺499,99
- [ ] **Auto-Renewable Subscription** — "Premium" grubu (2 süre):
  - `com.bilyadadus.premium_monthly` → ₺79,99 / ay
  - `com.bilyadadus.premium_yearly`  → ₺199,99 / yıl
- [ ] Her ürüne görünen ad + açıklama (TR) + inceleme ekran görüntüsü ekle
- [ ] **App-Specific Shared Secret** üret (App Information / Subscriptions) → değeri **Adım 1'deki `APPLE_SHARED_SECRET`** olarak sunucuya yaz, backend'i yeniden başlat

> Not: Ürün id'leri uygulama içindeki id'lerle birebir aynı olmalı (yukarıdaki gibi). Fiyatlar
> uygulamada otomatik olarak App Store'dan (yerel para) çekilip gösterilir.

## 5) Derle & yükle (Xcode gerekir)
- [ ] Xcode'u kur (App Store'dan)
- [ ] `cd mobile/ios && pod install`  (gerekirse: `export SSL_CERT_FILE=/opt/homebrew/etc/ca-certificates/cert.pem` + `LANG/LC_ALL=en_US.UTF-8`)
- [ ] `open mobile/ios/Runner.xcworkspace` → Signing & Capabilities → **Team** seç, otomatik imzalama, bundle id `com.bilyadadus.app`
- [ ] Üretim derlemesi (prod URL'i göm):
  ```
  cd mobile
  flutter build ipa --release \
    --dart-define=API_BASE_URL=https://<domain> \
    --dart-define=WS_BASE_URL=wss://<domain>
  ```
- [ ] Çıktıyı **Transporter** ile (veya Xcode Organizer → Distribute) App Store Connect'e yükle

## 6) Test (sandbox)
- [ ] App Store Connect → Users and Access → **Sandbox Tester** oluştur
- [ ] Gerçek cihazda TestFlight ile altın paketi + Premium satın almayı dene (sandbox)

## 7) Mağaza sayfası & gönder
- [ ] Ekran görüntüleri (6.9"/6.7" iPhone) — `05_screenshots.md`
- [ ] Açıklama/anahtar kelime/kategori — `01_listing_metadata.md`
- [ ] **Privacy Policy URL** = `https://<domain>/legal/privacy`
- [ ] App Privacy (gizlilik etiketleri: izleme yok) — `04_privacy.md`
- [ ] App Review için **çalışan test hesabı** + not (e-posta/telefon girişli)
- [ ] IAP'leri bu sürümle birlikte incelemeye ekle → **Submit for Review**

---

### Özet: kod hazır; senin işin = Apple hesabı + finans sözleşmesi + IAP ürünlerini portalda
### oluşturma + shared secret + backend deploy + Xcode ile arşiv/yükleme.
