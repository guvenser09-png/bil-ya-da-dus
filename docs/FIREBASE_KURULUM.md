# Firebase / Push Bildirimi Kurulumu — Adım Adım

Bu rehber, "Bil ya da Düş" için push bildirimlerini AÇAR. Kod tarafı **hazır**;
eksik olan tek şey Firebase hesabı ve anahtarlar.

> **Şu an ne oluyor?** Firebase yapılandırması olmadan uygulama ve sunucu
> sorunsuz çalışır — push sessizce **devre dışıdır**. Kullanıcı token'ları bile
> toplanmaz (izin istenmez). Aşağıdaki adımları bitirdiğinizde push kendiliğinden
> devreye girer; kod değişikliği GEREKMEZ.

Toplam süre: ~30 dakika. Sırayı bozmayın.

---

## Adım 1 — Firebase projesi oluştur

1. <https://console.firebase.google.com> adresine Google hesabınla gir.
2. **"Proje ekle"** (Add project) tıkla.
3. Proje adı: `bil-ya-da-dus` yaz → **Devam**.
4. Google Analytics sorulursa: **kapatabilirsin** (gerekmiyor) → **Proje oluştur**.
5. Proje açılana kadar bekle → **Devam**.

---

## Adım 2 — iOS uygulamasını ekle

1. Proje ana sayfasında **iOS** simgesine (elma) tıkla.
2. **Apple bundle ID** kutusuna TAM OLARAK şunu yaz:

   ```
   com.bilyadadus.app
   ```

   > Tek bir harf bile farklı olursa bildirim ÇALIŞMAZ.

3. Takma ad (nickname): `Bil ya da Düş iOS` (istediğini yazabilirsin).
4. **Uygulamayı kaydet** → **GoogleService-Info.plist'i indir** butonuna bas.
5. Kalan adımları (SDK ekleme, kod yapıştırma) Firebase sana gösterecek —
   **HEPSİNİ ATLA**, "İleri → İleri → Konsola devam et" de. O işleri Flutter
   paketleri zaten yapıyor.

---

## Adım 3 — GoogleService-Info.plist dosyasını projeye koy

İndirdiğin dosyayı şu klasöre kopyala:

```
mobile/ios/Runner/GoogleService-Info.plist
```

Sonra **Xcode'da projeye tanıt** (bu adım şart — yoksa dosya uygulamanın içine
paketlenmez ve push çalışmaz):

1. `mobile/ios/Runner.xcworkspace` dosyasını Xcode ile aç.
2. Soldaki dosya ağacında **Runner** (sarı klasör) üzerine sağ tıkla →
   **Add Files to "Runner"…**
3. `GoogleService-Info.plist` dosyasını seç.
4. Açılan pencerede:
   - ✅ **Copy items if needed** işaretli olsun.
   - ✅ **Add to targets: Runner** işaretli olsun.
5. **Add** → Dosya artık sol ağaçta `Runner` altında görünüyor olmalı.

> **Gizli mi?** Hayır. Bu dosya Firebase'in resmî tavsiyesiyle repoya
> **commit edilebilir** (içinde gizli anahtar yok). Codemagic'in bulut
> derlemesinde IPA'nın içine girmesi için repoda OLMASI gerekir.

---

## Adım 4 — Xcode'da "Push Notifications" yeteneğini aç

Hâlâ Xcode'dayken:

1. Sol üstte **Runner** projesine tıkla → **TARGETS** altında **Runner** seç.
2. Üstteki sekmelerden **Signing & Capabilities**.
3. **+ Capability** butonuna bas → arama kutusuna `Push` yaz →
   **Push Notifications**'a çift tıkla.
4. Aynı şekilde **+ Capability** → `Background` yaz → **Background Modes** ekle →
   listede **Remote notifications** kutusunu işaretle.

> `Info.plist` içindeki `UIBackgroundModes` ayarı zaten kodda hazır; bu adım
> Xcode'un imza dosyasına (entitlements) da eklenmesini sağlar.

---

## Adım 5 — Apple'da APNs anahtarı (.p8) oluştur

Firebase'in Apple'a bildirim gönderebilmesi için bir anahtar gerekir.

1. <https://developer.apple.com/account> → **Certificates, Identifiers &
   Profiles** → soldan **Keys**.
2. Sağ üstteki **+** (mavi artı) butonuna bas.
3. Key Name: `Bil ya da Dus Push` yaz.
4. **Apple Push Notifications service (APNs)** kutusunu işaretle → **Continue**
   → **Register**.
5. **Download** de → `AuthKey_XXXXXXXXXX.p8` dosyası inecek.

> ⚠️ Bu dosya **BİR KEZ** indirilir. Kaybedersen yenisini oluşturman gerekir.
> Güvenli bir yere kaydet, repoya **KOYMA**.

Aynı sayfada iki bilgiyi not et:

- **Key ID**: dosya adındaki 10 haneli kod (ör. `ABC123DEFG`).
- **Team ID**: Apple Developer hesabının sağ üst köşesinde yazan 10 haneli kod.

---

## Adım 6 — .p8 anahtarını Firebase'e yükle

1. Firebase Console → sol üstteki **dişli** ⚙️ → **Proje ayarları**.
2. **Cloud Messaging** sekmesi.
3. **Apple app configuration** bölümünde **APNs Authentication Key** →
   **Upload** butonuna bas.
4. Az önce indirdiğin `.p8` dosyasını seç.
5. **Key ID** ve **Team ID** alanlarını Adım 5'te not ettiğin değerlerle doldur.
6. **Upload**.

✅ Artık Firebase, Apple'a bildirim gönderebiliyor.

---

## Adım 7 — Sunucu anahtarını (service account JSON) indir

Backend'in Firebase'e "şu kullanıcıya bildirim gönder" diyebilmesi için gerekir.

1. Firebase Console → ⚙️ **Proje ayarları** → **Hizmet hesapları**
   (Service accounts) sekmesi.
2. **Yeni özel anahtar oluştur** (Generate new private key) → **Anahtar oluştur**.
3. Bir `.json` dosyası inecek (ör. `bil-ya-da-dus-firebase-adminsdk-xxxx.json`).

> ⚠️ Bu dosya **PAROLA GİBİDİR**. Repoya **ASLA** commit etme. Sadece Railway'e
> yapıştıracağız.

---

## Adım 8 — JSON'u Railway'e ekle

1. <https://railway.app> → projeni aç → **backend servisine** tıkla.
2. Üstten **Variables** sekmesi → **+ New Variable**.
3. **Name** kutusuna:

   ```
   FIREBASE_SERVICE_ACCOUNT_JSON
   ```

4. **Value** kutusuna: Adım 7'de indirdiğin JSON dosyasını bir metin editörüyle
   aç, **içindeki her şeyi** (`{` ile başlayıp `}` ile biten TÜM metin) kopyala
   ve buraya yapıştır.
5. **Add** → Railway servisi otomatik yeniden başlatır.

> **Çok satırlı yapıştırma sorun çıkarırsa:** JSON'u base64'e çevirip öyle de
> yapıştırabilirsin, kod ikisini de anlar:
>
> ```bash
> base64 -i ~/Downloads/bil-ya-da-dus-firebase-adminsdk-xxxx.json | pbcopy
> ```

---

## Adım 9 — Uygulamayı yeniden derle

Firebase paketleri (`firebase_core`, `firebase_messaging`) `pubspec.yaml`'a zaten
eklendi. Şimdi iOS bağımlılıklarını kur ve yeni sürümü çıkar:

```bash
cd mobile
flutter clean
flutter pub get
cd ios && pod install && cd ..
# Sonra her zamanki gibi TestFlight/Codemagic derlemesi
```

---

## Kontrol listesi — "Çalışıyor mu?"

- [ ] **Backend açık mı?** Railway loglarında hata yok, `/health` 200 dönüyor.
- [ ] **Token geliyor mu?** Uygulamada bir maç oyna, bitince **bildirim izni
      penceresi** çıkmalı. "İzin Ver" de.
- [ ] **DB'ye yazıldı mı?** `device_tokens` tablosunda 1 satır olmalı:

  ```bash
  railway run python -c "print('ok')"   # bağlantı testi
  ```

- [ ] **Test gönderimi:** Backend dizininde önce kuru çalıştır (gönderim yok):

  ```bash
  railway run python backend/scripts/send_push_campaign.py --campaign comeback --dry-run
  ```

  Hedef listesi görünüyorsa gerçek gönderim:

  ```bash
  railway run python backend/scripts/send_push_campaign.py --campaign comeback --limit 1
  ```

---

## Kampanyaları zamanla (opsiyonel ama tavsiye edilir)

Railway'de **Cron** servisi ekleyip şu komutları kur (saatler **UTC**):

| Kampanya   | Cron        | TRT saati        | Kime gider                                  |
|------------|-------------|------------------|---------------------------------------------|
| `daily`    | `0 9 * * *` | 12:00 her gün    | Bugün Günün Sorusu'nu oynamamış aktifler    |
| `streak`   | `0 17 * * *`| 20:00 her gün    | Günlük ödül serisi bu gece bozulacak olanlar|
| `comeback` | `0 15 * * 6`| 18:00 Cumartesi  | 3+ gündür dönmeyenler                       |

Komut:

```
python backend/scripts/send_push_campaign.py --campaign daily
```

**Otomatik korumalar (kodda hazır, elle bir şey yapmana gerek yok):**

- 23:00–10:00 TRT arası **hiçbir bildirim gitmez** (sessiz saat).
- Bir kullanıcıya **günde en fazla 1 bildirim** gider (kampanyalar çakışsa bile).
- Geçersiz/ölü token'lar gönderim sırasında **otomatik silinir**.

---

## Sorun giderme

| Belirti | Sebep / Çözüm |
|---|---|
| Maç sonunda izin penceresi çıkmıyor | `GoogleService-Info.plist` Xcode'da **Runner target**'ına eklenmemiş (Adım 3.4). Ya da izin daha önce reddedilmiş → iPhone Ayarlar → Bil ya da Düş → Bildirimler'den aç. |
| Script "Push devre dışı" diyor | Railway'de `FIREBASE_SERVICE_ACCOUNT_JSON` yok veya bozuk (Adım 8). |
| Bildirim gitti ama telefona ulaşmadı | APNs anahtarı yüklenmemiş (Adım 6) ya da Key ID/Team ID yanlış. |
| Simülatörde bildirim gelmiyor | Normal — iOS simülatörü APNs token vermez. **Gerçek cihazda** test et. |
| "Script hedef bulamadı" | Henüz kimse izin vermemiş → `device_tokens` boş. Kendi cihazınla bir maç oynayıp izin ver. |

---

## Gizlilik notu (yapıldı ✅)

Gizlilik politikası, push bildirimlerini kapsayacak şekilde güncellendi
(`mobile/assets/legal/privacy_policy.md` ve `/legal/privacy` sayfası):
bildirim token'ının saklandığı, **yalnızca oyun bildirimi** için kullanıldığı,
reklam/izleme amacı taşımadığı ve cihazdan kapatılabildiği yazıyor.

App Store Connect → **App Privacy** anketinde ek bir değişiklik gerekmez;
"Device ID / Identifiers" zaten **"App Functionality"** amacıyla beyan edilmiş
durumda (bildirim token'ı bu kapsama girer, izleme amaçlı DEĞİL).
