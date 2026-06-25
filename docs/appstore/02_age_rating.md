# 02 — Yaş Derecelendirme (Age Rating)

App Store Connect > Uygulama > **General > Age Rating > Edit** altında doldurulacak ankettir. Apple 2025 sonrası anketi "Content Rights / Content Descriptions" başlığı altında günceller; aşağıdaki cevaplar mantıksal kategorilere göredir.

> Sonuç tahmini: **9+** (kullanıcılar arası iletişim / sosyal özellikler nedeniyle) — sohbet/emoji yoksa **4+** mümkün. Aşağıda her iki senaryo için talimat var.

---

## Anket cevapları

| Soru kategorisi | Cevap | Gerekçe |
|---|---|---|
| Cartoon or Fantasy Violence (Çizgi/fantezi şiddet) | **None / Yok** | Şiddet içeriği yok; bilgi yarışması. |
| Realistic Violence (Gerçekçi şiddet) | **None / Yok** | — |
| Prolonged Graphic/Sadistic Violence | **None / Yok** | — |
| Sexual Content or Nudity (Cinsellik/çıplaklık) | **None / Yok** | — |
| Profanity or Crude Humor (Küfür/kaba mizah) | **None / Yok** | Sorular küratörlü; küfür yok. |
| Horror/Fear Themes | **None / Yok** | — |
| Mature/Suggestive Themes | **None / Yok** | — |
| Medical/Treatment Information | **None / Yok** | — |
| Alcohol, Tobacco, or Drug Use or References | **None / Yok** | — |
| **Simulated Gambling (Simüle kumar)** | **None / Yok** | Turnuvalar **beceri temellidir**; şans/bahis/kumar mekaniği yoktur. Oyun-içi altın gerçek paraya çevrilemez. |
| Contests (Yarışmalar) | **None / Yok** (oyun-içi yarışma kumar değildir) | Trivia eleme yarışması; ödüller oyun-içi. |
| Unrestricted Web Access (Sınırsız web erişimi) | **No / Hayır** | Uygulama içinde serbest tarayıcı yok. |
| **User-Generated Content (Kullanıcı üretimi içerik)** | Aşağıdaki "Sosyal özellikler" notuna bakın | — |

---

## Sosyal / kullanıcı arası iletişim (KRİTİK karar noktası)

Apple, **kullanıcılar arasında iletişim** (sohbet, mesajlaşma, isim/avatar paylaşımı, emoji gönderme) içeren oyunları genelde **9+** veya üstüne çeker ve bazı bölgelerde bu özellik **moderasyon + bildirme/engelleme** mekanizması gerektirir.

### Durum tespiti
Bil ya da Düş'te oyuncular:
- Kullanıcı adı + (altınla alınan) karakter ile arenada görünür.
- Liderlik tablosunda görünür.
- **Arkadaş (friends) sistemi** vardır.

Soru: **Oyuncular arası serbest metin sohbet veya mesaj var mı?**

#### Senaryo A — Serbest sohbet/mesaj YOK (yalnızca kullanıcı adı + hazır emoji/tepki)
- "Does your app contain user-generated content?" → İçerik küratörlü ise ve serbest metin yoksa **No** veya en hafif seviye.
- Olası sonuç: **4+** (en iyi durum) ya da temkinli **9+**.

#### Senaryo B — Oyuncular arası serbest metin sohbet/mesaj VAR
- "User-Generated Content" → **Yes**, ve
- Apple'ın istediği şartları SAĞLAMALISINIZ:
  - Uygunsuz içeriği filtreleme (küfür/spam),
  - Kullanıcıyı **bildirme (report)** mekanizması,
  - Kullanıcıyı **engelleme (block)** mekanizması,
  - Kötüye kullananı 24 saat içinde değerlendirip kaldırma taahhüdü (Guideline 1.2).
- Olası sonuç: **9+** veya **12+**.

> **Öneri:** İlk sürümde serbest metin sohbeti KAPALI tutun (yalnızca hazır emoji/tepki veya hiç iletişim). Bu, derecelendirmeyi düşük tutar (4+/9+) ve Guideline 1.2 moderasyon yükümlülüğünden kaçınır. Sohbeti sonraki sürümde, report/block ile birlikte eklersiniz.

---

## Doğrulanması gereken kod gerçeği

> Bu doküman koda dokunmaz; ancak doğru cevap vermek için aşağıdakini **siz** teyit edin:
> - `friends.py` arkadaş sistemi serbest metin mesajlaşma içeriyor mu, yoksa yalnızca arkadaş ekleme/sıralama mı?
> - Arena/lobi (`lobby.py`) oyuncular arası serbest sohbet içeriyor mu?
>
> İçermiyorsa **Senaryo A** (4+/9+), içeriyorsa **Senaryo B** (9+ ve moderasyon zorunlu) cevaplarını uygulayın.

---

## Özet

- Şiddet / cinsellik / küfür / madde / kumar: **YOK**.
- Beklenen derecelendirme: **4+** (sohbet yoksa) veya **9+** (kullanıcılar arası iletişim varsa).
- Eğer serbest sohbet eklenecekse: report + block + filtreleme **şarttır** (yoksa Guideline 1.2'den ret).
