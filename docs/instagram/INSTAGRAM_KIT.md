# 📱 Instagram Organik Açılış Kiti — Bil ya da Düş

Her şey hazır: profil fotoğrafı, 5 paylaşıma hazır soru kartı, açıklama metinleri,
Reels senaryoları ve 7 günlük plan. Sadece hesabı aç ve sırayla paylaş.

---

## 1) Hesap kurulumu (5 dk)

- **Kullanıcı adı:** `bilyadadus` (doluysa: `bilyadadusoyun` / `bilyadadus.app`)
- **Ad:** Bil ya da Düş 🔥
- **Kategori:** Oyun/eğlence → "Video Game" seç
- **Profil fotoğrafı:** `docs/instagram/profil_foto_320.png` (hazır)
- **Bio (kopyala-yapıştır):**
  ```
  🔥 12 kişi. 5 soru. Tek şampiyon.
  🧠 Türkiye'nin bilgi yarışması battle royale'i
  🏆 Yanlış bilen KAPAKTAN DÜŞER
  👇 App Store'dan ücretsiz indir
  ```
- **Bio linki:** App Store uygulama linkin (App Store Connect → App Information →
  "View on App Store" URL'i). İleride Android gelince Linktree'ye çevirirsin.
- Hesabı **profesyonel hesaba** çevir (Ayarlar → Hesap türü) → istatistikleri görürsün.

## 2) İlk hafta planı (günde 1 paylaşım, akşam 20:00-21:30 arası)

| Gün | İçerik | Dosya/senaryo |
|---|---|---|
| 1 | Soru kartı (feed) | `kartlar/kart1_sezen.png` |
| 2 | Reels #1: Oynanış | aşağıda senaryo R1 |
| 3 | Soru kartı | `kartlar/kart3_bolivya.png` |
| 4 | Reels #2: Düşme anı | senaryo R2 |
| 5 | Soru kartı | `kartlar/kart2_vitamin.png` |
| 6 | Reels #3: Zor Mod | senaryo R3 |
| 7 | Soru kartı + hafta özeti story | `kartlar/kart4_matbaa.png` |

(`kart5_kane.png` yedek — 2. haftada kullan.)

## 3) Soru kartı açıklama şablonu (her kartta değiştirerek kullan)

```
Bu soruyu maçta 12 kişiden sadece 3'ü bildi 👀
Sen bilir miydin? Cevabını yorumlara yaz 👇
(Cevap yarın story'de!)

🔥 Bil ya da Düş — canlı bilgi yarışması battle royale
📲 App Store'da ücretsiz — link profilde

#bilgiyarışması #quiz #trivia #genelkültür #bilgi #yarışma
#mobiloyun #oyun #türkiye #kimmilyonerolmakister #eğlence #keşfet
```

**Kural:** Cevabı görselde/açıklamada ASLA verme → yorum gelir → keşfete düşersin.
Ertesi gün story'de cevabı açıkla + doğru bilenlerden birine "🏆 tebrikler" yaz.

## 4) Reels senaryoları (telefondan 2 dakikada çekilir)

Hepsi için: iPhone **ekran kaydı** (Kontrol Merkezi → kayıt), sonra Instagram'da
kes-birleştir. Müzik: IG'nin önerdiği trend seslerden birini seç (erişimi artırır).
Süre hedefi: **7-15 saniye** (kısa = tekrar izlenir = keşfet).

**R1 — "Sen olsan bilir miydin?"**
- Ekran kaydı: bir maçta soru geliyor → süre işliyor → cevap seçiliyor → DOĞRU.
- Üstüne yazı (IG metin aracı): "12 kişilik canlı yarışmada bu soru geldi 😳"
- Son kare: "Sen bilir miydin? 👇"
- Açıklama: soru kartı şablonunun aynısı.

**R2 — "Kapaktan düşüş" (en viral potansiyelli)**
- Ekran kaydı: yanlış cevap → kırmızı YANLIŞ! flaşı → oyuncunun kapaktan düşme animasyonu.
- Yazı: "Yanlış bilirsen böyle olur 💀" → son kare: "Bil ya da Düş 🔥"
- Bu formatı farklı sorularla AYDA 4-5 kez tekrar kullanabilirsin — en çok tutan format buysa ona yüklen.

**R3 — "Zor Mod'a girmeye cesaretin var mı?"**
- Ekran kaydı: Zor Mod ekranı (CESARETİN VAR MI? kartı) → GİR → zor soru → 10 sn sayaç baskısı.
- Yazı: "100 altın yatırdım... 🥵" → sonuç ne olursa olsun paylaş (kaybetmek de içerik!).
- Son kare: "1.'ye 700 altın 🏆 Sen dener miydin?"

**R4 (bonus) — "Joker anı"**
- 4 şıklı zor soru → ½ joker basılıyor → 2 şık siliniyor → doğru cevap.
- Yazı: "Son joker hakkımı buna harcadım 😅"

## 5) Story rutini (günlük, 1 dk)
- Dün paylaşılan sorunun **cevabını** açıkla (anket çıkartması ile: "Bilmiş miydin? ✅/❌")
- Arada bir: o günkü maçtan ilginç bir an, "şu an 12 kişi yarışıyor" ekranı.

## 6) İlk 2 hafta beklentisi (gerçekçi)
- Takipçi sayısına takılma — hedef **keşfete düşen 1-2 Reels**. 
- Yorum gelen kartlara cevap yaz (her yorum erişimi büyütür).
- Hangi format tutarsa (izlenme ≥ 2-3x diğerleri) o formatı haftada 2-3 kez tekrarla.
- Bu içerikler ileride Meta reklamının hazır kreatifleri olacak — hiçbir emek boşa gitmez.

## 7) Yeni kart üretimi
Yeni soru kartları gerektiğinde Claude'a "5 yeni Instagram soru kartı üret" demen
yeterli — şablon `kartlar/*.html` içinde, sorular prod havuzundan seçilip
otomatik render ediliyor (1080×1350 PNG).
