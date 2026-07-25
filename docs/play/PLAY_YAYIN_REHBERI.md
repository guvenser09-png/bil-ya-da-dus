# 🤖 Google Play'e Yükleme — Adım Adım (Bilal'e anlatır gibi)

Her şey hazır: paket (AAB), ekran görüntüleri, görseller, metinler.
Sen sadece Play Console'a girip **kopyala-yapıştır** yapacaksın.

**Dosyaların yeri:** İndirilenler → `BilYaDaDus_Play` klasörü

---

## ⏱️ Gerçekçi takvim (önce bunu bil)

Google, **yeni bireysel hesaplarda** uygulamayı herkese açmadan önce
**12 kişilik kapalı testi 14 gün kesintisiz** yürütmeni şart koşuyor.

| Aşama | Süre |
|---|---|
| Hesap açılışı + onay | 1-2 gün |
| Uygulamayı yükleme + kapalı test başlatma | 1 gün |
| **Arkadaşların test linkiyle oynamaya başlar** | **~2-3 gün içinde** ✅ |
| 14 günlük kesintisiz test | 14 gün |
| Üretim başvurusu + Google incelemesi | 2-7 gün |
| 🌍 **Play Store'da herkese açık** | **~3 hafta** |

> APK'yı zaten arkadaşlarına attın — onlar oynamaya devam edebilir.
> Kapalı test, o kişileri "resmi testçi" yapıp 14 günlük sayacı başlatır.

---

## ADIM 1 — Hesabı aç (25 $, bir kez)

1. **play.google.com/console/signup** aç
2. Google hesabınla giriş yap
3. **"Kendim için" (Bireysel)** seç
4. Kimlik + adres bilgilerini gir
5. **25 $** öde (kredi kartı)
6. Onay 1-2 gün sürebilir — bu sırada Adım 2'yi yapabilirsin

---

## ADIM 2 — AdMob'da Android uygulaması aç (reklam geliri için)

1. **admob.google.com** → **Apps** → **Add app**
2. Platform: **Android** → "Uygulamam mağazada değil" seç → ad: **Bil ya da Düş**
3. Oluşunca **App ID**'yi kopyala (`ca-app-pub-1508388843514752~XXXX`)
4. Aynı uygulamada **Ad units** → **Add ad unit** → **Rewarded** → ad: `rewarded_gold`
5. Çıkan **birim kimliğini** kopyala (`ca-app-pub-1508388843514752/YYYY`)
6. **İkisini de Claude'a yolla** → koda gömülüp yeni paket üretilecek

*(Şu anki pakette Google'ın TEST reklam kimlikleri var: reklamlar çalışır ama
gelir getirmez. Gerçek kimlikler gelince değiştirilecek.)*

---

## ADIM 3 — Uygulamayı oluştur

Play Console → **Tüm uygulamalar** → **Uygulama oluştur**

| Alan | Değer |
|---|---|
| Uygulama adı | `Bil ya da Düş` |
| Varsayılan dil | `Türkçe (Türkiye)` |
| Uygulama mı oyun mu | **Oyun** |
| Ücretsiz mi ücretli mi | **Ücretsiz** |
| Beyanlar | İkisini de işaretle |

---

## ADIM 4 — Mağaza kaydı (kopyala-yapıştır)

Sol menü: **Büyüt → Mağaza varlığı → Ana mağaza girişi**

**Uygulama adı (30 karakter):**
```
Bil ya da Düş
```

**Kısa açıklama (80 karakter):**
```
12 kişi, 5 soru, tek şampiyon! Yanlış bilen kapaktan düşer. Canlı bilgi yarışması
```

**Tam açıklama:**
```
BİL YA DA DÜŞ — Türkiye'nin bilgi yarışması battle royale'i!

12 yarışmacı, 5 tur, tek şampiyon. Her turda soruyu doğru bilenler yola devam eder, yanlış bilenler kapaktan aşağı DÜŞER! Son turda en yakın tahmini yapan şampiyon olur.

KALKAN — Maç öncesi kalkanını hazırla: ilk yanlışında kalkanın kırılır ama oyunda kalırsın.

%50 JOKER — Zorlandığın soruda iki yanlış şıkkı ele. Ama dikkat: maç başına tek hak!

ZOR MOD — Zor sorular, 3 kat sezon puanı ve sabit ödül havuzu: 1.'ye 700, 2.'ye 300, 3.'ye 200 altın. Cesaretin var mı?

HAYALET MODU — Elendin mi? Bitmedi! İzlerken cevaplamaya devam et, doğru bildikçe altın kazan.

SIRALAMADA YÜKSEL — Her maç sezon puanı kazandırır. Sıralama her ay sıfırlanır; ay sonunda ilk 7 ödülleri toplar.

KARAKTERİNİ SEÇ — Kazandığın altınlarla robottan ejderhaya onlarca karakter aç, lobide tarzını göster.

90 SANİYEDE BİR MAÇ — Beklemek yok: bas, oyna, kazan (ya da düş), bir daha dene!

• Ücretsiz oyna — uygulama içi satın alma yok. İstersen ödüllü reklam izleyip altın kazan (isteğe bağlı)
• Misafir olarak anında oyna, istersen sonra hesabını kaydet
• Doğru/yanlış, çoktan seçmeli, görsel, karşılaştırma ve tahmin turları
• Arkadaşınla özel oda kur, davet kodunu paylaş, birebir kapış

Bil bakalım: düşecek misin, şampiyon mu olacaksın?
```

**Görseller** (klasördeki dosyaları sürükle):
- **Uygulama simgesi:** `play_icon_512.png`
- **Öne çıkan grafik:** `feature_graphic_1024x500.png`
- **Telefon ekran görüntüleri:** `screenshots/` içindeki 6 PNG (sırayla)

---

## ADIM 5 — Zorunlu formlar (sol menü: "Uygulama içeriği")

### Gizlilik politikası
```
https://bil-ya-da-dus-production.up.railway.app/legal/privacy
```

### Reklamlar
→ **"Evet, uygulamamda reklam var"**

### İçerik derecelendirmesi (anket)
- Kategori: **Oyun**
- Şiddet/cinsellik/küfür/uyuşturucu: **Hayır** (hepsi)
- Kumar: **Hayır** *(altın gerçek parayla alınamaz, ödül gerçek para değil)*
- Kullanıcılar iletişim kurabilir mi: **Evet** (hazır mesajlar — sabit liste)
- Konum paylaşımı: **Hayır**
→ Sonuç: 3+ / PEGI 3 civarı

### Hedef kitle
- Yaş: **13-15, 16-17, 18+** (13 yaş altını İŞARETLEME — reklam kuralları sertleşir)
- Çocuklara yönelik mi: **Hayır**

### Veri güvenliği (App Store'daki gizlilik anketinin Play sürümü)
Toplanan veriler:

| Veri | Toplanıyor | Paylaşılıyor | Amaç |
|---|---|---|---|
| E-posta adresi | ✅ | ❌ | Hesap yönetimi |
| Kullanıcı kimlikleri | ✅ | ❌ | Hesap yönetimi, uygulama işlevi |
| Cihaz/reklam kimliği | ✅ | ✅ (AdMob) | Reklam, uygulama işlevi |
| Uygulama etkileşimleri | ✅ | ❌ | Analiz, uygulama işlevi |

- Aktarımda şifreleme: **Evet** (HTTPS)
- Kullanıcı silme isteyebilir mi: **Evet** → Profil → Hesap Ayarları → HESABI SİL

### Devlet uygulaması / finans / sağlık: **Hayır**

---

## ADIM 6 — Kapalı test başlat (asıl önemli adım)

Sol menü: **Test et ve yayınla → Test → Kapalı test**

1. **Yeni sürüm oluştur**
2. **Play uygulama imzalama**: kabul et (Google anahtarını yönetir — normal)
3. **App bundle yükle:** klasördeki **`BilYaDaDus-1.1.0.aab`** dosyasını sürükle
4. **Sürüm notu** (bu metni yapıştır):
```
İlk Android sürümü. 12 kişilik canlı bilgi yarışması, Zor Mod, %50 joker ve kalkan mekaniği.
```
5. **Testçiler** sekmesi → **E-posta listesi oluştur** → arkadaşlarının **Gmail adreslerini** ekle
   → **en az 12 kişi** (14 günlük sayaç için şart)
6. **Kaydet → İncele → Kapalı teste sun**
7. Onaylanınca (birkaç saat) **"Katılım bağlantısı"** çıkar → **linki arkadaşlarına at**

> Arkadaşların o linke Gmail hesabıyla girip "Testçi ol" der, sonra Play Store'dan
> normal şekilde indirir. Artık güncellemeler otomatik gelir — APK göndermeye son!

---

## ADIM 7 — 14 gün sonra: üretime çık

- 12+ testçi 14 gün boyunca kesintisiz kayıtlı kalmalı (kimseyi listeden çıkarma!)
- Süre dolunca Play Console'da **"Üretim erişimi için başvur"** butonu belirir
- Formu doldur (testten ne öğrendin, uygulamanın hazır olduğunu anlat)
- Google inceler (2-7 gün) → onaylanınca **Üretim** sekmesinden yayına alırsın 🎉

---

## ⚠️ Sık yapılan hatalar

| Hata | Sonuç |
|---|---|
| Testçi listesinden birini çıkarmak | 14 günlük sayaç **sıfırlanır** |
| 12'den az testçi | Üretim başvurusu açılmaz |
| APK yüklemeye çalışmak | Play yeni uygulamalarda **sadece AAB** kabul eder (bizde hazır) |
| Gizlilik politikası boş bırakmak | Uygulama reddedilir |

---

## 📦 Paket içeriği (İndirilenler → BilYaDaDus_Play)

```
BilYaDaDus-1.1.0.aab          → Play'e yüklenecek paket (49 MB)
play_icon_512.png             → Mağaza simgesi
feature_graphic_1024x500.png  → Öne çıkan grafik
screenshots/                  → 6 telefon ekran görüntüsü
PLAY_YAYIN_REHBERI.md         → Bu rehber
```
