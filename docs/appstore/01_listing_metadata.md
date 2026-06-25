# 01 — App Store Listeleme Metinleri

App Store Connect > Uygulama > **Distribution** sekmesinde doldurulacak alanlar. Birincil dil **Türkçe (tr-TR)**; İngilizce (en-US) opsiyonel taslak da aşağıda verilmiştir.

> Karakter limitleri Apple'ın zorunlu kıldığı üst sınırlardır. Limit AŞILMAMALI; aşan metinler kaydedilemez.

---

## Türkçe (tr-TR) — BİRİNCİL

### App Adı (Name) — ≤ 30 karakter
```
Bil ya da Düş
```
> 13 karakter. Uygun.

### Alt Başlık (Subtitle) — ≤ 30 karakter
```
20 kişilik canlı bilgi savaşı
```
> 29 karakter. Uygun. (Alternatif: `Canlı trivia battle royale` — 26 karakter.)

### Promosyon Metni (Promotional Text) — ≤ 170 karakter
> İnceleme olmadan güncellenebilir; kampanya/duyuru için idealdir.
```
20 oyuncu, tek arena, tek kazanan! Yanlış cevap verirsen elenirsin. Arkadaşlarını davet et, sezon ödüllerini topla ve bilgi tahtının tepesine çık.
```
> 152 karakter. Uygun.

### Açıklama (Description) — ≤ 4000 karakter
```
Bil ya da Düş, 20 oyuncunun aynı anda yarıştığı, Türkçe canlı bir bilgi yarışması battle-royale'idir. Her soru bir eleme turudur: doğru bilirsen kalırsın, yanlış yaparsan ya da süreyi kaçırırsan düşersin. Son ayakta kalan kazanır!

Hızlı, heyecanlı ve tamamen beceriye dayalı. Şans değil, bilgi konuşur.

OYNANIŞ
• 20 kişilik canlı arena: Gerçek oyuncularla eş zamanlı yarış.
• Eleme mantığı: Her turda yanlış cevap verenler oyundan düşer.
• Geniş soru havuzu: Tarih, bilim, spor, sanat, coğrafya, popüler kültür ve daha fazlası.
• Geri sayım baskısı: Saniyeler içinde karar ver, tereddüt edersen elenirsin.
• Anlık sıralama: Kim kaldı, kim düştü, canlı olarak gör.

İLERLEME VE ÖDÜLLER
• ALTIN topla: Kazandıkça oyun-içi altın kazan.
• Karakterler: Altınla yeni karakterler aç, arenada kendini ifade et.
• Sezonlar: Her sezon yeni hedefler, yeni ödüller.
• Liderlik tablosu: Arkadaşlarınla ve tüm Türkiye'yle yarış.

TURNUVALAR
• Beceri temelli turnuvalar: Şansa değil, bilgine güven.
• Sıralı (ranked) modda gerçek rakiplerle kapış.

PREMIUM (opsiyonel abonelik)
• Reklamsız deneyim (zaten reklam yok — premium ile her şey daha akıcı).
• Günlük altın bonusu.
• 2 kat sezon puanı.
• Özel premium çerçeve.
Premium hiçbir zaman doğru cevabı göstermez veya avantaj sağlamaz — oyun adil kalır, kazanan her zaman en çok bilendir.

NEDEN BİL YA DA DÜŞ?
• Tamamen Türkçe içerik ve arayüz.
• Reklam yok, takip yok.
• Hızlı maçlar — birkaç dakikada bir tur.
• Arkadaşlarınla oynamak için ideal.

Bilgine güveniyor musun? Arenaya gir, son ayakta kalan sen ol.

Not: Bil ya da Düş çevrimiçi bir oyundur ve oynamak için internet bağlantısı gerektirir.
```
> ~1500 karakter. Limit dahilinde, genişletmeye açık.

### Anahtar Kelimeler (Keywords) — ≤ 100 karakter, virgülle ayrılmış
> Boşluk kullanmayın (boşluk karakter sayar). App adı ve kategorilerdeki kelimeleri TEKRAR ETMEYİN (gereksiz; algoritma zaten dahil eder).
```
bilgi,yarışma,trivia,quiz,soru,battle,royale,eleme,turnuva,canlı,çok oyunculu,zeka,test
```
> 84 karakter. Uygun. (Türkçe karakterler tek karakter sayılır.)

### Destek URL'i (Support URL) — ZORUNLU
```
https://<uretim-domain>/support
```
> Yer tutucu. Backend deploy edildikten sonra gerçek domaini koyun. Basit bir destek/iletişim sayfası yeterli (e-posta adresi içerebilir). Alternatif: GitHub Pages veya bir Notion sayfası.

### Pazarlama URL'i (Marketing URL) — OPSİYONEL
```
https://<uretim-domain>/
```
> Yer tutucu. Tanıtım sitesi yoksa boş bırakılabilir.

### Telif (Copyright)
```
2026 Bil ya da Düş
```
> Tüzel kişi/şahıs adınızla güncelleyin (örn. `2026 Serdar Güven`).

### Kategoriler
| Alan | Değer |
|---|---|
| Birincil Kategori | **Games > Trivia** |
| İkincil Kategori | **Games > Word** (alternatif: Games > Family) |

### Sürüm Notları (What's New / Version 1.0.0)
> İlk sürümde "What's New" yerine ilk yayın notu istenir.
```
Bil ya da Düş'ün ilk sürümü yayında! 20 kişilik canlı bilgi savaşına katıl, doğru cevapla hayatta kal, altın topla ve liderlik tablosunda yüksel. Bol şans!
```

---

## English (en-US) — OPSİYONEL TASLAK

> Türkiye dışına açılmayacaksa eklemeyin. Eklerseniz aşağıdaki taslağı kullanın.

- **Name (≤30):** `Know or Fall`
- **Subtitle (≤30):** `20-player live trivia battle`
- **Promotional Text (≤170):** `20 players, one arena, one winner! Answer wrong and you're out. Invite friends, collect season rewards, and climb to the top of the knowledge throne.`
- **Keywords (≤100):** `trivia,quiz,battle,royale,knowledge,multiplayer,live,elimination,tournament,brain,question,test`
- **Description (≤4000):**
```
Know or Fall is a live 20-player trivia battle royale. Every question is an elimination round: answer correctly to survive, get it wrong (or run out of time) and you fall. The last one standing wins!

Fast, intense, and 100% skill-based — knowledge wins, not luck.

GAMEPLAY
• 20-player live arena against real players.
• Elimination format: wrong answers are out each round.
• Huge question pool: history, science, sports, art, geography, pop culture and more.
• Countdown pressure: decide in seconds.
• Live standings: see who survives and who falls in real time.

PROGRESSION & REWARDS
• Earn GOLD as you win.
• Unlock characters with gold.
• Seasons with fresh goals and rewards.
• Compete on the leaderboard.

TOURNAMENTS
• Skill-based tournaments — no gambling, no luck.
• Ranked mode against real opponents.

PREMIUM (optional subscription)
• Ad-free experience.
• Daily gold bonus.
• 2x season points.
• Exclusive premium frame.
Premium never reveals answers or gives a competitive edge — the game stays fair.

Note: Know or Fall is an online game and requires an internet connection.
```
- **Version notes (1.0.0):** `First release of Know or Fall! Join the live 20-player trivia battle, survive each round, collect gold, and climb the leaderboard. Good luck!`

---

## App Review için ek metadata (Distribution > App Review Information)

- **Sign-in required:** EVET. Apple'a **test hesabı** sağlayın:
  - E-posta/telefon ile giriş olduğundan, önceden oluşturulmuş bir **demo hesabı** (kullanıcı adı + şifre veya doğrulanmış telefon/OTP akışı açıklaması) verin.
  - OTP/telefon doğrulaması varsa, reviewer'ın takılmaması için **sabit/atlanabilir doğrulama kodu** içeren bir test hesabı veya açık talimat ekleyin.
- **Notes (Review Notes) önerisi:**
```
Bil ya da Düş, 20 kişilik canlı (gerçek zamanlı) bir trivia battle-royale'dir. Tek başına test için botlarla dolu bir maç başlatılabilir; eşleşme birkaç saniye sürebilir.

Test hesabı: <e-posta> / <şifre>  (veya telefon: <numara>, OTP: <kod/talimat>)

Tüm IAP'ler oyun-içi ALTIN veya Premium abonelik içindir. Karakterler GERÇEK PARA ile DEĞİL, oyun-içi altınla alınır. Reklam ve kullanıcı takibi (tracking) yoktur. Turnuvalar beceri temellidir; kumar/şans oyunu yoktur.

Backend: https://<uretim-domain>  (canlı ve erişilebilir)
```
- **Contact info:** Ad, soyad, telefon, e-posta (size ulaşılabilir bir adres).
