# 06 — Adım Adım İlk Gönderim Oyun Kitabı (Playbook)

Bil ya da Düş 1.0.0'ı sıfırdan App Store incelemesine göndermek için uçtan uca süreç. Her adımda **dikkat noktaları** ve **sık reddedilme tuzakları** vardır.

> ⚠️ **SIFIRINCI ADIM — Üretim backend deploy edilmeli.** Apple reviewer uygulamayı açar; backend erişilemezse açılış ekranından öteye geçemez → **Guideline 2.1 App Completeness** reddi kesindir. Önce `DEPLOY.md` ile Railway'e deploy edin, `https://<domain>/health` 200 dönsün, soru bankasını seed'leyin. Domaini Adım 6'da kullanacaksınız.

---

## Adım 1 — Apple Developer Program kaydı

1. https://developer.apple.com/programs/ → **Enroll**.
2. Apple ID ile giriş, kimlik doğrulama (iki faktör).
3. Bireysel veya Organization seç. **Organization** ise **D-U-N-S numarası** gerekir (1–14 gün sürebilir → erken başlatın).
4. 99 USD/yıl ödeme. Onay genelde 24–48 saat.

**Dikkat / tuzaklar:**
- Organization adı, banka/vergi adıyla uyuşmalı.
- Onay gelmeden App Store Connect'te uygulama oluşturamazsınız.

---

## Adım 2 — Developer Portal: App ID + capabilities

1. https://developer.apple.com/account → **Certificates, Identifiers & Profiles > Identifiers > +**.
2. **App IDs > App** seç.
3. **Bundle ID (Explicit):** `com.bilyadadus.app` (Xcode'daki ile birebir aynı olmalı).
4. **Capabilities:** **In-App Purchase** işaretli olsun. (Push Notifications kullanılıyorsa onu da ekleyin — kullanılmıyorsa eklemeyin; gereksiz capability ret sebebi olabilir.)
5. Kaydet.

**Dikkat / tuzaklar:**
- Bundle ID sonradan değiştirilemez; yazımı bir harf bile şaşmasın: `com.bilyadadus.app`.
- IAP capability eksikse abonelik/satın alma çalışmaz, "Missing items" reddi gelir.

---

## Adım 3 — App Store Connect'te uygulama kaydı

1. https://appstoreconnect.apple.com → **Apps > + > New App**.
2. **Platform:** iOS. **Name:** `Bil ya da Düş`. **Primary Language:** Turkish (Türkçe).
3. **Bundle ID:** listeden `com.bilyadadus.app`. **SKU:** serbest benzersiz kod (örn. `bilyadadus-ios-001`).
4. Oluştur.
5. **Agreements, Tax, and Banking** tamamlanmış olduğunu doğrulayın (IAP için şart).

**Dikkat / tuzaklar:**
- Banka/vergi eksikse IAP'ler satılamaz, "Ready to Submit" olmaz.
- App Name App Store'da benzersiz olmalı; çakışırsa ufak varyant gerekebilir.

---

## Adım 4 — IAP + abonelik grubu oluştur

`03_iap_setup.md`'yi birebir uygulayın:
1. 4 **Consumable** altın paketi (`gold_small/medium/large/mega`), fiyat + tr lokalizasyon + her birine **review screenshot**.
2. **"Premium" abonelik grubu** → `premium_monthly` + `premium_yearly`, seviyeler (yearly = Level 1), tr lokalizasyon + yenileme metni + review screenshot.
3. **App-Specific Shared Secret** üret → backend'e (`APPLE_SHARED_SECRET`), `IAP_SANDBOX=false`.

**Dikkat / tuzaklar:**
- **İlk sürümde IAP'leri sürüme dahil etmeyi UNUTMAYIN** (binary gönderirken "In-App Purchases" bölümünden seçin) — yoksa incelenmezler.
- Her IAP'ye review screenshot zorunlu; eksikse "Missing Metadata".
- Abonelik paywall'ında 5 zorunlu madde (başlık/süre/fiyat/yenileme metni/gizlilik+EULA) yoksa Guideline 3.1.2 reddi.

---

## Adım 5 — Xcode kurulum, imzalama, pod install

1. Terminalde proje köküne gidin ve iOS bağımlılıklarını kurun:
   ```bash
   cd "/Users/guvenser/Bil ya da Düş/mobile"   # Flutter projesi kökü
   flutter pub get
   ```
2. **Xcode workspace'i açın:**
   ```bash
   open ios/Runner.xcworkspace
   ```
   > `Runner.xcodeproj`'i DEĞİL, **`Runner.xcworkspace`**'i açın (CocoaPods workspace gerektirir).
3. Xcode > **Runner target > Signing & Capabilities:**
   - **Team:** Apple Developer hesabınız.
   - **Automatically manage signing:** açık.
   - **Bundle Identifier:** `com.bilyadadus.app` (Portal'daki ile aynı).
   - **In-App Purchase** capability listede görünmeli.
4. **`pod install`** (gerekirse). CocoaPods sertifika/locale hataları için:
   ```bash
   cd "/Users/guvenser/Bil ya da Düş/mobile/ios"
   export LANG=en_US.UTF-8
   export LC_ALL=en_US.UTF-8
   export SSL_CERT_FILE=/opt/homebrew/etc/ca-certificates/cert.pem
   pod install --repo-update
   ```
   > `SSL_CERT_FILE` Homebrew OpenSSL'in sertifika paketini gösterir (SSL hatalarını çözer). UTF-8 locale, CocoaPods'un "invalid byte sequence" hatasını önler.

**Dikkat / tuzaklar:**
- Bundle ID Xcode ≠ Portal ise imzalama başarısız.
- `Runner.xcworkspace` yerine `.xcodeproj` açmak Pods'u görmez → build hatası.
- Apple ID Xcode > Settings > Accounts'ta ekli olmalı.

---

## Adım 6 — Release IPA build (production backend ile)

```bash
cd "/Users/guvenser/Bil ya da Düş/mobile"
flutter build ipa --release \
  --dart-define=API_BASE_URL=https://<prod-domain> \
  --dart-define=WS_BASE_URL=wss://<prod-domain>
```
- `<prod-domain>`: Adım 0'da aldığınız Railway HTTPS domaini (örn. `bilyadadus-production.up.railway.app`).
- WebSocket için **`wss://`** (TLS).
- Çıktı: `build/ios/ipa/*.ipa` ve Xcode archive.

**Dikkat / tuzaklar:**
- `--dart-define` UNUTULURSA uygulama localhost'a bağlanmaya çalışır → reviewer'da backend'e ulaşamaz → ret. **Domaini mutlaka geçin.**
- `http://`/`ws://` (TLS'siz) kullanmayın → ATS (App Transport Security) engeller, hem de güvensiz.
- Build numarası her yüklemede artmalı (aynı numara reddedilir/yüklenmez).
- Version 1.0.0, Build 1 ile başlayın.

---

## Adım 7 — Yükleme (Xcode Organizer veya Transporter)

**Seçenek A — Xcode Organizer:**
- `flutter build ipa` sonrası Xcode > **Window > Organizer > Archives** → archive seç → **Distribute App > App Store Connect > Upload**.

**Seçenek B — Transporter:**
- Mac App Store'dan **Transporter** kur → `.ipa`'yı sürükle → **Deliver**.

**Dikkat / tuzaklar:**
- İlk yüklemede Apple, dağıtım sertifikası/provisioning'i otomatik üretir (automatic signing açıksa).
- Yükleme sonrası App Store Connect'te işlenmesi 5–30 dk sürebilir (build "Processing" → "Ready").
- **Encryption uyumu:** `ITSAppUsesNonExemptEncryption` sorusu çıkar. Standart HTTPS/TLS dışında özel şifreleme yoksa **"No"** (veya Info.plist'te `ITSAppUsesNonExemptEncryption=false`). Bu, "Export Compliance" adımını hızlandırır.

---

## Adım 8 — TestFlight iç test

1. App Store Connect > Uygulama > **TestFlight** → işlenen build görünür.
2. **Internal Testing** grubu oluştur → kendinizi (ve ekip) ekle → build'i ata.
3. iPhone'da **TestFlight** uygulamasıyla yükleyip **uçtan uca test edin:**
   - Giriş (e-posta/telefon) çalışıyor mu?
   - Lobi + 20 kişilik maç (botlarla) başlıyor mu?
   - IAP **sandbox** satın alma çalışıyor mu? (Settings > App Store > Sandbox Account ile test).
   - Abonelik satın al/iptal akışı, paywall metinleri görünüyor mu?

**Dikkat / tuzaklar:**
- TestFlight'ta backend canlı olmalı (production domain).
- IAP'yi sandbox hesabıyla mutlaka test edin; gerçek satın alma yapmayın.
- Çökme/donma varsa düzeltmeden incelemeye GÖNDERMEYİN.

---

## Adım 9 — Metadata/gizlilik/ekran görüntüleri/IAP doldur ve incelemeye gönder

1. **Distribution** sekmesi:
   - `01_listing_metadata.md`'den: Name, Subtitle, Promo, Description, Keywords, Support/Marketing URL, Copyright, Kategoriler, Sürüm Notları.
   - `05_screenshots.md`'den ekran görüntüleri.
   - **Build** seç (Adım 7'de yüklenen).
2. **App Privacy:** `04_privacy.md` anketini doldur + Privacy Policy URL.
3. **In-App Purchases:** bu sürüme **dahil et** (4 consumable + 2 abonelik) — "Ready to Submit" olsun.
4. **App Review Information:** test hesabı (giriş zorunlu!), iletişim, review notes (`01_listing_metadata.md` sonundaki metin).
5. **Age Rating:** `02_age_rating.md`.
6. **Export Compliance** sorusunu yanıtla (Adım 7).
7. **Add for Review > Submit to App Review.**

**Dikkat / tuzaklar (en sık retler):**
- **2.1 App Completeness:** backend erişilemez / test hesabı çalışmıyor / OTP'de takılıyor.
- **3.1.2 Subscriptions:** paywall'da yenileme metni/gizlilik/EULA bağlantısı eksik.
- **3.1.1 In-App Purchase:** dijital içerik (altın/premium) Apple IAP dışı satılıyor görünüyor (sizde IAP içinde — sorun yok, ama "altın satın al" akışı yalnızca Apple IAP olmalı).
- **2.3 Accurate Metadata:** ekran görüntüsü uygulamayla uyuşmuyor / Android öğesi / yanıltıcı.
- **5.1.1 Privacy:** App Privacy beyanı gerçek toplamayla çelişiyor; Privacy Policy URL açılmıyor.
- **5.1.1(v) Account Deletion:** Hesap oluşturan uygulamalar **uygulama içinden hesap silme** sunmalı. Bil ya da Düş hesap oluşturduğundan, uygulamada "Hesabı sil" özelliği OLMALI; yoksa ret. (Kod tarafında teyit edin.)
- **4.0 Design / 2.1:** boş/placeholder ekran, kırık buton.

---

## İnceleme sonrası
- Onay: "Pending Developer Release" seçtiyseniz **manuel yayınlayın**; "Automatic" seçtiyseniz otomatik çıkar.
- Ret: Resolution Center'daki gerekçeyi okuyun, düzeltin, yeni build/metadata ile tekrar gönderin (genelde aynı gün tekrar incelemeye girer).
