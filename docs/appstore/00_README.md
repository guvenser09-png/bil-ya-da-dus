# Bil ya da Düş — App Store Gönderim Paketi

Bu klasör, **Bil ya da Düş** uygulamasının Apple App Store'a ilk kez (sürüm 1.0.0) gönderilmesi için gereken **tüm metadata, IAP kurulum şartnamesi, gizlilik bildirimleri ve adım adım gönderim kılavuzunu** içerir.

> Bu dosyalar yalnızca **dokümantasyondur**. Kod veya konfigürasyon değiştirmez. App Store Connect ve Apple Developer portalındaki alanları doldururken referans olarak kullanın.

---

## Uygulama künyesi

| Alan | Değer |
|---|---|
| Uygulama adı | **Bil ya da Düş** |
| Tür | Fall Guys tarzı 20 kişilik canlı trivia battle-royale (Türkçe) |
| Bundle ID | **com.bilyadadus.app** |
| Birincil dil | Türkçe (tr-TR) |
| Birincil kategori | Games > Trivia |
| İkincil kategori | Games > Word |
| İlk sürüm | 1.0.0 |
| Para birimi | Oyun-içi **ALTIN** (tek birim). Gerçek para yalnızca IAP'ta. |
| Reklam | YOK |
| İzleme (tracking) | YOK |
| Kimlik doğrulama | E-posta / telefon |
| Kumar | YOK (turnuva beceri-temelli) |

---

## Bu klasördeki dosyalar (okuma sırası)

| # | Dosya | İçerik |
|---|---|---|
| 00 | `00_README.md` | Bu dosya — genel bakış, ön koşullar, indeks |
| 01 | `01_listing_metadata.md` | App Store listeleme metinleri (TR birincil, EN taslak) |
| 02 | `02_age_rating.md` | Yaş derecelendirme anketi cevapları + gerekçeler |
| 03 | `03_iap_setup.md` | Uygulama-içi satın alma (IAP) + abonelik kurulum şartnamesi |
| 04 | `04_privacy.md` | App Privacy etiketleri + gizlilik politikası / EULA |
| 05 | `05_screenshots.md` | Ekran görüntüsü boyutları, adet ve önerilen kareler |
| 06 | `06_submission_playbook.md` | Adım adım ilk gönderim oyun kitabı |
| 07 | `07_prelaunch_checklist.md` | Gönderim öncesi tek sayfalık kontrol listesi |

---

## KRİTİK ÖN KOŞUL — Üretim backend deploy edilmeli

> ⚠️ **Apple incelemesi (App Review), uygulamayı gerçek cihazda ÇALIŞTIRIR.** Bil ya da Düş canlı bir backend'e (FastAPI + Postgres + Redis + WebSocket) bağlanmadan açılış ekranından ileri gidemez. Üretim backend **HENÜZ DEPLOY EDİLMEDİ**.
>
> **Gönderimden önce mutlaka:** Backend'i Railway'e (veya Fly.io/Render) deploy edin ve public HTTPS domaini alın. Yöntem repo kökündeki **`DEPLOY.md`** dosyasında adım adım anlatılıyor.
>
> Deploy edilmiş domain alınmadan `flutter build ipa` yapılmamalıdır; çünkü API/WS URL'leri build sırasında `--dart-define` ile gömülür. Backend'siz gönderilen build, Apple tarafından **Guideline 2.1 — App Completeness** gerekçesiyle reddedilir.

Backend hazır olunca domaini şuralarda kullanacaksınız:
- `flutter build ipa --dart-define=API_BASE_URL=https://<domain> --dart-define=WS_BASE_URL=wss://<domain>`
- Gizlilik politikası ve EULA barındırma adresleri (bkz. `04_privacy.md`).

---

## Ön koşullar (gönderimden önce hazır olması gerekenler)

### Apple tarafı
- [ ] **Apple Developer Program üyeliği** (yıllık 99 USD). Kayıt: https://developer.apple.com/programs/
  - Bireysel veya Organization. Organization için D-U-N-S numarası gerekir (birkaç gün sürebilir).
- [ ] **App Store Connect erişimi** (Developer Program ile otomatik gelir): https://appstoreconnect.apple.com
- [ ] **Vergi & Banka (Agreements, Tax, and Banking)** bilgileri App Store Connect'te **tamamlanmış** olmalı. IAP geliri ve ücretli içerik için bu zorunludur; eksikse IAP'ler "Missing Metadata" / satılamaz durumda kalır.

### Geliştirme tarafı (Mac üzerinde)
- [ ] **macOS + Xcode** (App Store'dan güncel sürüm). İlk açılışta komut satırı araçları kurulur.
- [ ] **Apple ID ile Xcode'da oturum** (Settings > Accounts).
- [ ] **Flutter SDK** kurulu ve `flutter doctor` temiz.
- [ ] **CocoaPods** (`pod install` için). Sertifika/locale notları `06_submission_playbook.md` Adım 5'te.
- [ ] **Üretim backend domaini** (yukarıdaki kritik ön koşul).

### İçerik tarafı
- [ ] Ekran görüntüleri (bkz. `05_screenshots.md`).
- [ ] App ikonu (1024×1024 PNG, alfa kanalı YOK, köşe yuvarlatma YOK).
- [ ] Gizlilik Politikası + Kullanım Koşulları (EULA) yayında bir URL'de (bkz. `04_privacy.md`).
- [ ] IAP referans adları, fiyatları ve açıklamaları (bkz. `03_iap_setup.md`).

---

## Önerilen sıralama

1. **Backend'i deploy et** (`DEPLOY.md`) → domaini not al.
2. **Gizlilik & EULA URL'lerini yayına al** (`04_privacy.md`).
3. **App Store Connect'te uygulamayı oluştur** + IAP/abonelikleri tanımla (`03_iap_setup.md`).
4. **Metadata + ekran görüntülerini hazırla** (`01`, `05`).
5. **Build al + yükle + TestFlight + incelemeye gönder** (`06_submission_playbook.md`).
6. **Son kontrol** (`07_prelaunch_checklist.md`).
