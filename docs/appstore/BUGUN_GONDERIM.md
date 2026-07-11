# 🚀 BUGÜN APP STORE'A GÖNDERİM — Adım Adım

Her şey hazır. Aşağıdaki adımları sırayla yap; metinleri olduğu gibi kopyala-yapıştır.

---

## 0) Build hazır mı? (5 dk kontrol)
- Codemagic'te son build ("App Store gönderim paketi" mesajlı) YEŞİL bitmiş olmalı → TestFlight'a otomatik yüklenir.
- appstoreconnect.apple.com → My Apps → **Bil ya da Düş** → TestFlight sekmesi → en yüksek numaralı build "Ready to Test/Submit" olana kadar bekle (~10-15 dk "Processing").
- (İstersen önce telefonda bu son sürümü 5 dk test et — yeni ikon, sonuç ekranı, sesler.)

## 1) Ekran görüntülerini yükle
App Store sekmesi → sol menü **1.0 Prepare for Submission** → **App Previews and Screenshots** → **iPhone 6.5" Display**:
- `docs/appstore/screenshots_6.5inch/` klasöründeki 8 PNG'yi SIRAYLA sürükle (01→08).
- Başka boyut istemezse başka şey yükleme (6.5" seti tüm küçük boyutları kapsar).

## 2) Metin alanları (kopyala-yapıştır)

**Promotional Text (170):**
```
12 kişilik canlı bilgi yarışması! Yanlış cevap verirsen düşersin — kalkanın seni bir kez kurtarır. Tamamen ücretsiz, reklamsız!
```

**Description:**
```
BİL YA DA DÜŞ — Türkiye'nin bilgi yarışması battle royale'i!

12 yarışmacı, 5 tur, tek şampiyon. Her turda soruyu doğru bilenler yola devam eder, yanlış bilenler kapaktan aşağı DÜŞER! Son turda en yakın tahmini yapan şampiyon olur.

🛡️ KALKAN — Her maçta bir hakkın var: ilk yanlışında kalkanın kırılır ama oyunda kalırsın.

👻 HAYALET MODU — Elendin mi? Bitmedi! İzlerken cevaplamaya devam et, doğru bildikçe altın kazan. Şampiyonun kim olacağına dair bahis oyna, tutturursan ödülü kap.

🏆 SIRALAMADA YÜKSEL — Her maç sezon puanı kazandırır. Sıralama her ay sıfırlanır; ay sonunda ilk 7 ödülleri toplar.

🤖 KARAKTERİNİ SEÇ — Kazandığın altınlarla robottan ejderhaya onlarca karakter aç, lobide tarzını göster.

⚡ 90 SANİYEDE BİR MAÇ — Beklemek yok: bas, oyna, kazan (ya da düş), bir daha dene!

• Tamamen ücretsiz — satın alma yok, reklam yok
• Misafir olarak anında oyna, istersen sonra hesabını kaydet
• Doğru/yanlış, çoktan seçmeli, görsel, karşılaştırma ve tahmin turları
• Arkadaşınla özel oda kur, davet kodunu paylaş, birebir kapış

Bil bakalım: düşecek misin, şampiyon mu olacaksın?
```

**Keywords (100 karakter):**
```
bilgi,yarışma,quiz,trivia,genel kültür,canlı,arkadaş,eğlence,soru,oyun,battle royale,milyoner
```

**Support URL:** `https://bil-ya-da-dus-production.up.railway.app/legal/terms`
**Marketing URL (opsiyonel):** boş bırak
**Privacy Policy URL:** `https://bil-ya-da-dus-production.up.railway.app/legal/privacy`

## 3) Genel bilgiler
- **Category:** Games → alt kategori: **Trivia** (ikincil: Word yerine **Casual** olabilir)
- **Content Rights:** "No, it does not contain..." (üçüncü taraf içerik yok)
- **Age Rating** anketi: hepsine **None** işaretle; "Unrestricted Web Access" = No; "Gambling" = No → sonuç **4+** çıkar (hazır mesajlar sabit listeden olduğu için "user-generated content" saymana gerek yok; profil adları için istersen 'Infrequent/Mild' yerine None kalabilir — sorun olursa Apple anketi güncelletir).
- **Price:** Free. **In-App Purchases:** HİÇBİR ürün ekleme (yok).

## 4) App Privacy (veri anketi) — Data Collection
"Data Types" bölümünde şunları işaretle:
- **Contact Info → Email Address**: Collected, Linked to user, App Functionality (yalnız kayıtlı hesaplar için)
- **Identifiers → User ID**: Collected, Linked, App Functionality
- **Identifiers → Device ID**: Collected, Linked, App Functionality (misafir girişi)
- **User Content → Other User Content**: Collected, Linked, App Functionality (kullanıcı adı/profil)
- Tracking: **No** (izleme yok). Analytics/Advertising: hiçbirini işaretleme.

## 5) Build seç + Review bilgileri
- **Build** bölümü → (+) → en son TestFlight build'ini seç.
- **App Review Information**:
  - Contact: adın + guvenser09@gmail.com + telefonun
  - **Notes** kutusuna şunu yapıştır:
```
The app is free with no purchases or ads. No account is required: tap "MİSAFİR OLARAK OYNA" (Play as Guest) on the login screen to play instantly. Matches are live 12-player trivia battle royale; lobbies auto-fill so a match always starts within ~15 seconds. In-game quick messages are selected from a fixed predefined list (no free text). Account deletion is available in Profile → Hesap Ayarları → HESABI SİL.
```
  - Demo account alanı: boş bırakabilirsin (misafir girişi var) — istersen `testoyuncu` / `sifre1234` yaz.
- **Version Release:** "Automatically release this version" (onaylanınca kendiliğinden yayınlanır) — istersen "Manually" seç, kontrol sende olur.

## 6) GÖNDER 🎉
Sağ üst **Add for Review** → **Submit to App Review**.
- İnceleme genelde 24-48 saat sürer. Sonuç maili gelir.
- Ret gelirse panik yok: gerekçeyi bana yapıştır, düzeltir yeniden göndeririz.

---

### Bilgin olsun (yapman gerekmez)
- Uygulama ikonu build'in içinde (Codemagic build'i ile geldi) — ASC'ye ayrıca ikon yüklemek gerekmiyorsa dokunma; sorarsa `docs/appstore/app_icon_1024.png`.
- Yasal metinler canlıda güncel (IAP iddiaları temizlendi) — inceleme denetiminden geçti (KOŞULLU KABUL → koşul deploy'du, yapıldı).
- Backend sağlıklı: /health OK, 444 onaylı soru, misafirler sıralamada gizli.
