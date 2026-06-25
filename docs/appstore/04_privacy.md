# 04 — App Privacy (Gizlilik Etiketleri) + Politika & EULA

İki parça:
1. **App Privacy "nutrition labels"** — App Store Connect > Uygulama > **App Privacy** anketi.
2. **Gizlilik Politikası + Kullanım Koşulları (EULA)** — yayında bir URL.

---

## 1) App Privacy — Veri toplama anketi

İlk soru: **"Do you or your third-party partners collect data from this app?"** → **Yes** (e-posta/telefon ile hesap var).

> ⚠️ **İZLEME (Tracking) YOK.** Hiçbir veri reklam/üçüncü taraf izleme için kullanılmaz. Anketin "Used to Track You" bölümünde **HİÇBİR şey işaretlenmemeli**. App Tracking Transparency (ATT) izni gerekmez.

### Toplanan veri türleri ve amaçları

| Veri türü (Apple kategorisi) | Toplanıyor mu? | Amaç (Purpose) | Kimliğe bağlı mı? (Linked) | İzleme için mi? |
|---|---|---|---|---|
| **Contact Info > Email Address** | Evet | App Functionality (hesap/giriş) | Linked to identity | Hayır |
| **Contact Info > Phone Number** (telefonla giriş kullanılıyorsa) | Evet | App Functionality (hesap/giriş) | Linked to identity | Hayır |
| **Identifiers > User ID** | Evet | App Functionality (oyun ilerlemesi, eşleşme, liderlik) | Linked to identity | Hayır |
| **User Content > Other (kullanıcı adı/profil)** | Evet | App Functionality | Linked to identity | Hayır |
| **Purchases > Purchase History** | Evet | App Functionality (IAP/abonelik durumu) | Linked to identity | Hayır |
| **Usage Data > Product Interaction** | Evet (uygulama içi olay/oyun istatistiği) | App Functionality (ve Analytics — yalnızca dahili kullanıyorsanız) | Linked to identity | Hayır |
| **Diagnostics > Crash / Performance Data** | Evet (varsa) | App Functionality | Not Linked (mümkünse) | Hayır |

> ⚠️ **Kod gerçeğini teyit edin:** Yukarıdaki liste, e-posta/telefon girişli, IAP'li, liderlik tablolu bir oyun için **muhafazakâr** bir varsayımdır. Backend'in topladığı alanları (`models/user.py`, `schemas/user.py`) gözden geçirin; toplanmayan kategoriyi anketten ÇIKARIN, ek toplanan varsa EKLEYİN. **Apple, beyan ile gerçek davranış uyuşmazlığında reddeder.**

### "Used to Track You" bölümü
- **Boş bırakın.** Hiçbir kategori burada işaretlenmez. Üçüncü taraf reklam/analitik SDK'sı yok.

### Telefon numarası notu
Telefonla giriş (OTP) aktif değilse "Phone Number" satırını çıkarın. Yalnızca e-posta varsa sadece Email + User ID kalır.

---

## 2) Gizlilik Politikası — ZORUNLU

App Store Connect > **App Privacy > Privacy Policy URL** alanı **zorunludur**. Ayrıca abonelik paywall'ında da bağlanmalı (bkz. `03_iap_setup.md` C maddesi).

### Barındırma seçenekleri (önerilen sıra)
1. **Backend üzerinde statik sayfa:** `https://<uretim-domain>/legal/privacy` (FastAPI'de basit statik HTML route). Avantaj: tek alan adı, IAP yenileme metniyle aynı yerde.
2. **GitHub Pages:** `https://<kullanici>.github.io/bilyadadus/privacy.html` (backend'e bağımsız, ücretsiz).
3. **Notion / basit landing:** geçici çözüm.

> Backend henüz deploy edilmediği için (1) ancak deploy sonrası hazır olur. İnceleme tarihine kadar (2) GitHub Pages en hızlı garantili yoldur.

### Hazır metin taslağı — Gizlilik Politikası (Türkçe)

```
Gizlilik Politikası — Bil ya da Düş
Son güncelleme: <TARİH>

Bu politika, Bil ya da Düş mobil uygulamasının hangi verileri topladığını,
nasıl kullandığını ve haklarınızı açıklar.

1. Topladığımız veriler
- Hesap bilgisi: E-posta adresi ve/veya telefon numarası (giriş ve hesap doğrulama için).
- Profil ve oyun verisi: Kullanıcı adı, kullanıcı kimliği, oyun ilerlemesi, altın bakiyesi,
  liderlik/sezon istatistikleri.
- Satın alma bilgisi: Uygulama-içi satın alma ve abonelik durumu (Apple üzerinden doğrulanır).
- Teknik veri: Çökme ve performans bilgisi, uygulama içi etkileşim olayları (uygulamayı
  iyileştirmek için).

2. Verileri nasıl kullanıyoruz
Verileri yalnızca uygulamanın çalışması için kullanırız: hesabınızı yönetmek, sizi diğer
oyuncularla eşleştirmek, ilerlemenizi kaydetmek, satın almaları doğrulamak ve hizmeti
iyileştirmek. Verilerinizi reklam veya üçüncü taraf izleme amacıyla KULLANMAYIZ ve SATMAYIZ.

3. İzleme (tracking)
Uygulamamız sizi diğer şirketlerin uygulama/sitelerinde izlemez. Reklam yoktur, üçüncü taraf
izleme SDK'sı yoktur.

4. Üçüncü taraflar
Satın almalar Apple App Store üzerinden işlenir ve Apple'ın gizlilik politikasına tabidir.
Altyapı sağlayıcılarımız (sunucu/veritabanı barındırma) verileri yalnızca hizmeti sağlamak için
işler.

5. Verilerin saklanması ve silinmesi
Hesabınız aktif olduğu sürece verilerinizi saklarız. Hesabınızın ve verilerinizin silinmesini
istemek için <DESTEK E-POSTASI> adresine yazabilirsiniz. Talebinizi makul süre içinde yerine
getiririz.

6. Çocukların gizliliği
Uygulama 13 yaş altı çocuklara yönelik değildir.

7. Haklarınız
Verilerinize erişme, düzeltme ve silme hakkınız vardır. Talepler için: <DESTEK E-POSTASI>

8. İletişim
Sorularınız için: <DESTEK E-POSTASI>
```

---

## 3) Kullanım Koşulları (EULA)

Apple iki seçenek sunar:

### Seçenek A — Apple Standart EULA (önerilen, en hızlı)
- Hiçbir şey yapmanıza gerek yok. App Store Connect'te **License Agreement** alanını boş bırakırsanız Apple'ın standart EULA'sı (Licensed Application End User License Agreement) otomatik uygulanır.
- Paywall'da "Kullanım Koşulları" bağlantısı olarak Apple'ın standart EULA adresini kullanabilirsiniz:
  `https://www.apple.com/legal/internet-services/itunes/dev/stdeula/`

### Seçenek B — Kendi EULA'nız
Özel hükümler (oyun-içi altının geri ödenmezliği, hesap askıya alma, hile/bot yasağı vb.) istiyorsanız kendi EULA'nızı yazıp:
- App Store Connect > App Information > **License Agreement** alanına ekleyin, ve/veya
- Gizlilik politikasıyla aynı yerde yayınlayıp (örn. `/legal/terms`) paywall'da bağlayın.

### Hazır taslak — Kullanım Koşulları (kısa, Türkçe)
```
Kullanım Koşulları — Bil ya da Düş
Son güncelleme: <TARİH>

1. Hizmet: Bil ya da Düş, çevrimiçi canlı bir trivia oyunudur. Oynamak için internet gerekir.
2. Hesap: Doğru bilgilerle hesap oluşturmayı ve hesabınızın güvenliğini kabul edersiniz.
3. Oyun-içi para (Altın): Altın yalnızca oyun içinde kullanılır, gerçek paraya çevrilemez ve
   geri ödenmez. Karakterler oyun-içi altınla alınır.
4. Satın almalar ve abonelik: Uygulama-içi satın almalar ve Premium aboneliği Apple üzerinden
   işlenir. Abonelik dönem sonunda otomatik yenilenir; Ayarlar > Apple Kimliği > Abonelikler'den
   iptal edilebilir.
5. Adil oyun: Hile, bot, çoklu hesap ve oyunu manipüle etme yasaktır; ihlalde hesap askıya
   alınabilir.
6. İçerik: Sorular ve içerik sahibimize aittir; izinsiz çoğaltılamaz.
7. Sorumluluk: Hizmet "olduğu gibi" sunulur; kesintiler olabilir.
8. Değişiklikler: Bu koşulları güncelleyebiliriz; önemli değişiklikleri uygulama içinde
   duyururuz.
9. İletişim: <DESTEK E-POSTASI>
```

---

## Özet kontrol
- [ ] App Privacy anketi gerçek veri toplamayla uyumlu dolduruldu.
- [ ] "Used to Track You" boş (izleme yok, ATT yok).
- [ ] Privacy Policy URL yayında ve App Store Connect'e girildi.
- [ ] EULA: Apple standart (boş bırak) **veya** kendi EULA'nız License Agreement alanında.
- [ ] Paywall'da hem Privacy hem EULA bağlantısı görünür (Guideline 3.1.2).
