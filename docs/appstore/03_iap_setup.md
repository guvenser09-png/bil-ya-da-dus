# 03 — Uygulama-İçi Satın Alma (IAP) Kurulum Şartnamesi

App Store Connect > Uygulama > **Monetization > In-App Purchases** ve **Subscriptions** altında oluşturulacak ürünlerin tam şartnamesi.

> ⚠️ **Apple kuralı:** Bir uygulamanın **ilk sürümü**, içerdiği IAP'lerle birlikte incelemeye gönderilmelidir. IAP'leri ürün listesinde oluşturup, sürüm gönderirken **"In-App Purchases" bölümünden bu sürüme dahil edin** (her IAP'nin durumu "Ready to Submit" olmalı). Aksi halde IAP'ler ya hiç incelenmez ya da binary "Missing items" ile reddedilir.

> ⚠️ **Ön koşul:** Agreements, Tax, and Banking (Anlaşmalar/Vergi/Banka) tamamlanmadan IAP'ler satılamaz / "Missing Metadata" durumunda kalır.

> 💰 **Fiyatlar:** Aşağıda ₺ değerleri hedef fiyatlardır. App Store Connect'te artık ülke bazlı fiyat **tier** yerine "Türkiye için base price" seçersiniz; Apple en yakın fiyat noktasına yuvarlar (₺X,99 noktaları mevcuttur). Listelenen ₺ değerine **en yakın Apple fiyat noktasını** seçin; diğer ülkeler otomatik dönüştürülür.

---

## A) Consumable — ALTIN Paketleri (4 adet)

> **Consumable** (tüketilebilir): satın alınınca oyun-içi altın hesaba eklenir, tekrar tekrar alınabilir, geri yüklenmez (restore yok).

| # | Referans Adı (Reference Name) | Product ID | Tip | Hedef Fiyat | Altın |
|---|---|---|---|---|---|
| 1 | Gold Small Pack | `com.bilyadadus.gold_small` | Consumable | ₺29,99 | 4.000 |
| 2 | Gold Medium Pack | `com.bilyadadus.gold_medium` | Consumable | ₺59,99 | 9.000 |
| 3 | Gold Large Pack | `com.bilyadadus.gold_large` | Consumable | ₺119,99 | 20.000 |
| 4 | Gold Mega Pack | `com.bilyadadus.gold_mega` | Consumable | ₺499,99 | 90.000 |

### Her ALTIN paketi için lokalizasyon (Türkçe — tr)
**Görünen Ad (Display Name) ≤ 30 karakter** ve **Açıklama (Description) ≤ 45 karakter**:

| Product ID | Display Name (tr) | Description (tr) |
|---|---|---|
| `com.bilyadadus.gold_small` | `4.000 Altın` | `Küçük altın paketi — hızlı başlangıç.` |
| `com.bilyadadus.gold_medium` | `9.000 Altın` | `Orta altın paketi — bonus altın dahil.` |
| `com.bilyadadus.gold_large` | `20.000 Altın` | `Büyük altın paketi — en avantajlı seçim.` |
| `com.bilyadadus.gold_mega` | `90.000 Altın` | `Mega altın paketi — en yüksek bonus.` |

> Açıklama 45 karakter sınırını aşmamalı; yukarıdakiler sınır içindedir.

### ALTIN paketleri için inceleme (Review) bilgileri
- **Review Notes (her paket için aynı):**
```
Tüketilebilir oyun-içi para birimi (ALTIN). Satın alma sonrası altın anında oyuncu hesabına eklenir ve karakter açma / oyun-içi öğelerde harcanır. Gerçek paraya çevrilemez, kumar değildir. Test için sandbox hesabıyla satın alma sunucu tarafında doğrulanır (Apple shared secret ile).
```
- **Review Screenshot:** Mağaza ekranında bu paketin göründüğü 1 ekran görüntüsü (zorunlu — her IAP için bir görsel gerekir; simülatör/cihaz görüntüsü uygundur).

---

## B) Auto-Renewable Subscription — Premium (tek grup, 2 süre)

> İki ürün de **TEK abonelik grubu** ("Premium") içinde olmalı. Aynı grup içindeki ürünler arasında kullanıcı yükseltme/düşürme/çapraz geçiş yapar ve aynı anda yalnızca birine abone olabilir.

### Abonelik Grubu
| Alan | Değer |
|---|---|
| Subscription Group Reference Name | `Premium` |
| Group Display Name (tr) | `Premium` |

### Grup içindeki ürünler

| Referans Adı | Product ID | Süre | Hedef Fiyat |
|---|---|---|---|
| Premium Monthly | `com.bilyadadus.premium_monthly` | 1 Ay (Monthly) | ₺79,99 / ay |
| Premium Yearly | `com.bilyadadus.premium_yearly` | 1 Yıl (Yearly) | ₺199,99 / yıl |

### Yükseltme / Düşürme seviyeleri (Subscription Levels / Ranking)
> Apple, grup içindeki ürünlere **seviye (level)** atamanızı ister; düşük seviye = daha üst paket (upgrade). Buradaki iki ürün **aynı premium içeriği** sunduğundan farklılık yalnızca süredir.
- **Level 1 (en üst):** `com.bilyadadus.premium_yearly` (yıllık = daha iyi değer → upgrade sayılır)
- **Level 2:** `com.bilyadadus.premium_monthly`

Sonuç: Aylıktan yıllığa geçiş **upgrade** (anında etkin), yıllıktan aylığa geçiş **downgrade** (dönem sonunda etkin) olur. Bu, App Store Connect'te grup düzenleme ekranında ürünleri sürükleyerek ayarlanır.

### Premium lokalizasyonu (tr) — her iki ürün için

**Görünen Ad (Display Name) ≤ 30 karakter:**
| Product ID | Display Name (tr) |
|---|---|
| `com.bilyadadus.premium_monthly` | `Premium — Aylık` |
| `com.bilyadadus.premium_yearly` | `Premium — Yıllık` |

**Açıklama (Description) ≤ 45 karakter:**
| Product ID | Description (tr) |
|---|---|
| `com.bilyadadus.premium_monthly` | `Reklamsız, günlük altın, 2x sezon puanı.` |
| `com.bilyadadus.premium_yearly` | `Yıllık premium — en avantajlı, 2x puan.` |

### Premium avantajları (pazarlama/uygulama içi paywall metni)
- Reklamsız deneyim (uygulamada zaten reklam yok).
- Günlük altın bonusu.
- 2x sezon puanı.
- Özel premium çerçeve.
- **PAY-TO-WIN YOK:** Premium doğru cevabı göstermez, ekstra süre/can vermez, eleme avantajı sağlamaz. Oyun adil kalır.

### Abonelik için inceleme (Review) bilgileri
- **Review Notes:**
```
Premium otomatik yenilenen abonelik (aylık/yıllık, aynı grup). Avantajlar: reklamsız, günlük altın bonusu, 2x sezon puanı, premium çerçeve. Rekabet avantajı (pay-to-win) YOKTUR — doğru cevabı göstermez. Abonelik sunucuda Apple shared secret ile doğrulanır. Test: sandbox hesabıyla satın alınabilir.
```
- **Review Screenshot:** Uygulama içi paywall/abonelik ekranının görüntüsü (zorunlu).

---

## C) Abonelik için Apple'ın ZORUNLU kıldığı metinler ve bağlantılar

Apple, otomatik yenilenen abonelikler için (Guideline 3.1.2) hem **App Store Connect'te abonelik metadatasında** hem de **uygulama içi paywall ekranında** şunların bulunmasını ister:

1. **Abonelik başlığı** ve **süresi** (Premium — Aylık / Yıllık).
2. **Fiyat** ve **birim başına fiyat** (₺79,99/ay; ₺199,99/yıl).
3. **Otomatik yenileme açıklaması:** "Abonelik, dönem bitiminden 24 saat önce iptal edilmezse otomatik yenilenir. Ödeme, satın alma onayında Apple Kimliği hesabınızdan tahsil edilir. Aboneliği Ayarlar > Apple Kimliği > Abonelikler üzerinden yönetebilir veya iptal edebilirsiniz."
4. **Gizlilik Politikası bağlantısı** (bkz. `04_privacy.md`).
5. **Kullanım Koşulları (EULA) bağlantısı** (Apple standart EULA veya kendi EULA'nız — bkz. `04_privacy.md`).

> Bu 5 madde paywall ekranında görünür olmalı; eksikse Guideline 3.1.2'den reddedilir. **App Store Connect'te ayrıca App > General > App Information altındaki "License Agreement" alanına EULA'yı bağlayın** (boş bırakılırsa Apple standart EULA uygulanır).

---

## D) App-Specific Shared Secret (sunucu doğrulaması)

Backend, satın almaları Apple'a doğrulatır (`DEPLOY.md`'deki `APPLE_SHARED_SECRET`). App Store Connect:
**Uygulama > Monetization > In-App Purchases (veya App Information) > App-Specific Shared Secret > Generate.**
- Üretilen değeri backend ortam değişkeni `APPLE_SHARED_SECRET` olarak girin.
- Üretimde `IAP_SANDBOX=false` olmalı (bkz. `DEPLOY.md`).

---

## Kontrol listesi (IAP)

- [ ] 4 Consumable ürün oluşturuldu (doğru product_id, fiyat, lokalizasyon, review screenshot).
- [ ] "Premium" abonelik grubu oluşturuldu.
- [ ] 2 abonelik ürünü gruba eklendi, seviyeler (yearly=Level 1) ayarlandı.
- [ ] Abonelik lokalizasyonu + yenileme metni girildi.
- [ ] Paywall ekranında 5 zorunlu madde (başlık, süre, fiyat, yenileme metni, gizlilik+EULA bağlantısı) görünüyor.
- [ ] App-Specific Shared Secret üretildi → backend'e girildi → `IAP_SANDBOX=false`.
- [ ] Agreements, Tax & Banking tamamlandı.
- [ ] Tüm IAP'ler 1.0.0 sürümüne **dahil edildi** (ilk sürümle birlikte incelemeye giriyor).
