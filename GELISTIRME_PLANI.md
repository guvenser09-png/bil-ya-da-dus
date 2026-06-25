# QuizRoyale — Tam Geliştirme Planı

**Mevcut durum (Hafta 2 sonu):**
- 66 test geçiyor ✅
- Auth, profil, rate limiting tamamlandı ✅
- WebSocket iskeleti var, gerçek implementasyon bekleniyor

---

## MİNİMUM OYUNCU SORUNU — AUTOMATİK ADAPTASYON SİSTEMİ (AAS)

### Problem
Launch'ta 5 gerçek oyuncuyu aynı anda bulmak neredeyse imkânsız. Lobi iptal olursa kullanıcı uygulamayı siler.

### Çözüm: Concurrent Active Players (CAP) Tabanlı Eşik

**CAP** = Şu anda matchmaking kuyruğunda bekleyen gerçek oyuncu sayısı (Redis'te anlık).

| Level | CAP | Bekleme | Min Gerçek Oyuncu | Açıklama |
|-------|-----|---------|-------------------|----------|
| 0 | 0-4 | 20s | **1** | Launch fazı — tek gerçek oyuncuyla başla |
| 1 | 5-19 | 25s | **2** | Küçüme büyüme fazı |
| 2 | 20-49 | 23s | **3** | Orta büyüme |
| 3 | 50-99 | 21s | **4** | Olgunlaşma |
| 4 | 100+ | 20s | **5** | Hedef durum |

**Modifiye Kuralları:**

```
1. Gece modu (02:00–08:00 TRT):
   → CAP level -1 (daha hızlı bot doldurma)

2. Yeni oyuncu (total_games < 10):
   → min_real = 1 (ilk deneyim asla mahvedilmemeli)

3. Uzun bekleme (oyuncu >40 saniye bekledi):
   → min_real = max(1, min_real - 1)

4. Anti-tilt (son 3 oyun kaybedildi):
   → Bot dağılımını %80 Kolay'a kaydır (gizli)
```

### Altın Kural: Lobi asla iptal edilmez

`"Yeterli oyuncu bulunamadı"` mesajı **hiçbir zaman** gösterilmez.
Her oyun başlar — gerekirse 1 gerçek + 19 bot ile.

### Botların Doğal Gözükmesi (UX Trick)

Geri sayım sırasında botlar anında değil, **gerçekçi aralıklarla "katılır"**:

```python
# Örnek: 14 bot 20 saniyeye yayılır
bot_join_times = random_spread(count=14, window=18)  # son 2sn hariç
# Oyuncu: "7/20... 9/20... 12/20..." görür → gerçek sanır
```

Lobi sayacı "Oyuncu aranıyor... 12/20" gösterirken o 12'nin kaçının bot
olduğunu kullanıcı bilmez. Bu tasarım gereğidir.

---

## HAFTA 3 — WebSocket + Lobi + Matchmaking (Gerçek Implementasyon)

> Mevcut `ws/lobby.py` iskelet. Bu hafta gerçek mantık yazılacak.

### Backend

**ConnectionManager** (`ws/connection_manager.py`)
- Aktif WebSocket bağlantılarını `Dict[str, WebSocket]` olarak tut
- `connect()`, `disconnect()`, `send_personal()`, `broadcast_to_lobby()` metodları
- Bağlantı kopunca lobi güncelle, 10 saniyelik yeniden bağlanma penceresi (Redis'te `reconnect:{user_id}` key)

**Lobi State Machine** (`services/lobby_service.py`)
- Durumlar: `waiting → countdown → filling_bots → in_game`
- `cancelled` durumu yok — her lobi bir şekilde başlar
- Redis'te lobi state JSON olarak saklanır (TTL: 120s)

**CAP Tracker** (`services/cap_service.py`)
- Redis Sorted Set: `matchmaking:queue` — score = timestamp
- `get_cap()`: Son 120 saniyedeki aktif oyuncu sayısı
- `get_min_real_players(user)`: Yukarıdaki formülü uygula
- Her 30 saniyede bir eski kayıtları temizle

**Bot Zamanlama** (`services/bot_scheduler.py`)
- Geri sayım başladığında bot "katılma" takvimi oluştur
- `asyncio.create_task()` ile her bot için ayrı timer
- Son 2 saniyede bot katılımı yok (gerçekçilik)

**Yeniden Bağlanma** (`ws/reconnect.py`)
- Bağlantı kopunca: `reconnect:{user_id}` → lobi_id, 10s TTL
- Oyuncu 10s içinde bağlanırsa kaldığı yerden devam
- 10s geçerse: oyuncu elendi, slot bota devredilir

**Bekleme Odası Isınma Sorusu** (YENİ ÖZELLIK)
- Lobi geri sayımı başlayınca rastgele bir "hazırlık sorusu" gönderilir
- Skora etkisi yok, sadece meşguliyet
- `"Oyun başlarken... Türkiye'nin başkenti neresidir?"` tarzı
- WebSocket mesajı: `{ type: "warmup_question", question: {...} }`

**Testler**
- Lobi lifecycle (oluştur → doldur → başlat)
- CAP hesaplama
- Minimum eşik formülü (6 senaryo)
- Bot zamanlama dağılımı
- Yeniden bağlanma penceresi
- 50+ eşzamanlı bağlantı yük testi

---

## HAFTA 4 — Oyun Döngüsü WebSocket Entegrasyonu

### Backend

**Oyun Döngüsü WebSocket** (`ws/game.py`)
- Lobi başlayınca tüm bağlantılar `/ws/game/{game_id}` kanalına taşınır
- Her tur için ayrı asyncio task (timer)
- Tur sonu otomatik tetiklenir (süre dolunca)
- Oyuncu cevap göndermeden süre bitmişse yanlış sayılır

**Tur Akışı (Redis'te state):**
```
game:{game_id}:state = {
  round: 2,
  status: "answering",  # waiting | answering | revealing | between
  question_id: "q_00142",
  started_at: timestamp,
  answers: { user_id: { answer, time_remaining } },
  eliminated: [user_id, ...]
}
```

**Seyirci Modu** (YENİ ÖZELLIK)
- Elenen oyuncu WebSocket bağlantısını kesmiyor
- `{ type: "spectator_mode" }` mesajı alır
- Diğer oyuncuların cevaplarını CANLI görebilir (kendi cevabı gizli)
- Emoji reaksiyon göndermeye devam edebilir

**Günlük Meydan Okuma** (YENİ ÖZELLIK) — `services/daily_challenge_service.py`
- Her gün 00:00'da Celery görevi 5 soru seçer (tur tipine göre 1 tane)
- Tüm oyuncular aynı 5 soruyu cevaplar
- Ayrı leaderboard: `/api/leaderboard/daily-challenge`
- Skoru normal maça eklenmez, sadece DC tablosuna
- UI'da "Bugünkü Meydan Okuma" badge'i

**Anti-tilt Sistemi** (YENİ ÖZELLIK) — `services/player_analytics_service.py`
- Son 3 oyunun sonuçları Redis'te tutulur
- 3 üst üste kayıp → bot dağılımı `%80 Kolay, %15 Orta, %5 Zor` olarak ayarlanır (gizli)
- 5 üst üste kayıp → push notification: "Gel biraz antrenman yapalım!" (sonraki hafta)

**Testler**
- Tam 5 tur döngüsü WebSocket üzerinden
- Her tur tipi için eleme
- Seyirci modu
- Süre dolunca otomatik yanlış
- Yeniden bağlanma oyun ortasında
- Bot cevap simülasyonu zamanlaması

---

## HAFTA 5 — Soru Sistemi + AI Pipeline

### Backend

**AI Üretim Pipeline** — `services/question_pipeline.py`
```
1. Haiku ile toplu üretim (kategori + zorluk + format)
2. Sonnet ile doğrulama ("Bu cevap kesin doğru mu?")
3. Gömülü vektör benzerlik kontrolü (tekrar önleme, threshold: 0.85)
4. İnsan onay kuyruğuna eklenir
5. Onaylananlar canlı havuza geçer
```

**Soru Kalite Sistemi** — `services/question_quality_service.py`
- `correct_rate < 0.05` → otomatik askıya al
- `report_count >= 20` → otomatik askıya al
- `usage_count > 50` → `low_priority` işareti (çeşitlilik için)

**30 Gün Tekrar Önleme** — `services/question_dedup_service.py`
- `question_history` tablosunu kullan
- Her soru seçiminde `shown_at > 30 days ago` filtresi
- Redis cache: `user:{id}:recent_questions` (son 100 soru ID'si, TTL 30 gün)

**Oyun Sonu Soru Oylaması** (YENİ ÖZELLIK)
- Oyun bitince her soru için 👍/👎 göster (5 saniye süre)
- `question.user_rating` alanına yaz
- `user_rating < 3.0` olan sorular admin inceleme kuyruğuna düşer

**Hedef Başlangıç Havuzu**
- 200 onaylı çoktan seçmeli
- 100 görsel soru
- 100 doğru/yanlış
- 50 karşılaştırma
- 50 tahmin sorusu (slider)

**Günlük Meydan Okuma Celery Görevi**
- Her gece 00:00'da çalışır
- Bugün için 5 soru seçer (tur tiplerine göre 1'er)
- Redis'e yazar: `daily_challenge:{date}` → [q_id list]
- 30 günlük geçmiş korunur

**Testler**
- AI pipeline parsing + doğrulama
- Tekrar önleme mantığı
- Kalite otomatik askıya alma
- Günlük soru atama
- Rapor eşiği tetikleme

---

## HAFTA 6 — Flutter Proje Kurulumu + Temel UI

### Flutter

**Proje Kurulumu**
```yaml
dependencies:
  flutter_riverpod: ^2.x
  go_router: ^13.x
  web_socket_channel: ^2.x
  lottie: ^3.x
  google_mobile_ads: ^5.x
  firebase_messaging: ^15.x
  firebase_analytics: ^11.x
  hive_flutter: ^1.x
  cached_network_image: ^3.x
  haptic_feedback: ^0.x
```

**Design System** (`lib/core/theme/`)
- Renk paleti: Mor-mavi gradyan `#6C3CE1 → #3B82F6`, sarı `#FFCC00`, turuncu `#FF6B35`
- Tipografi: Poppins (başlık), Inter (body)
- Komponent kütüphanesi: Button, Card, Avatar, Badge, ProgressBar
- Animasyon süreleri sabitleri: `Duration kFast = 150ms`, `kNormal = 300ms`

**Navigasyon** (`lib/core/router/`)
- GoRouter ile named routes
- Auth guard (token yoksa login'e yönlendir)
- Bottom tab: Ana Menü | Leaderboard | Profil | Arkadaşlar

**Ekranlar**
- Splash screen (logo + yükleme animasyonu)
- Onboarding (3 slide — oyun anlatımı)
- Login / Register (e-posta, Google, Apple)
- Ana menü (Hızlı Maç butonu + istatistik kartları)
- Profil ekranı (avatar, istatistikler, rozetler)
- Ayarlar (ses, dil, bildirim, gizlilik)

---

## HAFTA 7 — Oyun Ekranları + WebSocket İstemcisi

### Flutter

**WebSocket İstemcisi** (`lib/core/ws/`)
- `GameWebSocketService` (Riverpod StateNotifier)
- Otomatik yeniden bağlanma (exponential backoff: 1s, 2s, 4s)
- Mesaj tiplerine göre event dispatch
- Bağlantı durumu UI'ya yansıtır (banner)

**Lobi Bekleme Ekranı** (`lib/features/lobby/`)
- Canlı sayaç animasyonu (1/20 → 7/20)
- Her oyuncu katılımında pop animasyonu + ses
- Bot "katılımları" doğal aralıklarla gelir
- Geri sayım timer (dairesel)
- Isınma sorusu widget'ı
- Oyuncu avatar listesi (küçük yuvarlaklar)

**Oyun Ekranı** (`lib/features/game/`)
- 5 farklı soru tipi için ayrı widget:
  - `TrueFalseWidget` — 2 büyük buton
  - `VisualQuestionWidget` — görsel + 4 şık
  - `ComparisonWidget` — 2 kart, sol/sağ seçim
  - `MultipleChoiceWidget` — 4 şık grid
  - `SliderWidget` — custom slider (haptic)
- Timer bar (yukarıdan aşağı sıvı dolum animasyonu)
- Oyuncu platformları (altta sıra)
- Canlı skor göstergesi

**Oyun State Yönetimi**
```dart
// Riverpod providers
gameStateProvider    // mevcut tur, soru, süre
playersProvider      // tüm oyuncular + durumları
myAnswerProvider     // kendi cevabım
eliminatedProvider   // elenenler listesi
```

---

## HAFTA 8 — Animasyonlar + Sonuç Ekranı + Reklamlar

### Flutter

**Eleme/Yükselme Animasyonları** (Lottie)
- Düşme: karakter sallanır → çığlık → aşağı kayar (1.5s)
- Yükselme: zıplar → parıltı → üst platforma (1.0s)
- Doğru cevap: yeşil halka + "+5 puan" yukarı uçar
- Yanlış cevap: kırmızı çarpı + ekran hafif sallanır

**Tur Geçiş Animasyonu**
- "TUR 2" yazısı büyük, tam ekran, 1 saniye
- Renk: her tur farklı (tur 1 mavi, tur 5 altın)

**Slider Final Ekranı**
- Haptic feedback sürüklerken (her 10 birimde bir tik)
- "Kilitle" butonu (öncelik için)
- Süre bitince herkesin tahmini bar üzerinde görünür
- Gerçek cevap animasyonlu belirir
- Kazanan parlama efekti

**Sonuç Ekranı**
- Konfeti (kazanırsa)
- Top 3 podyum (altın/gümüş/bronz)
- Tüm oyuncuların skoru liste halinde
- Kazanana alkış butonu
- "F" (saygı) butonu için elenenler
- Arkadaş ekle (oyun sonu)
- Soru oylaması (👍/👎 her soru için 5s)
- "Tekrar Oyna" / "Ana Menü"

**Yeniden Bağlanma UI**
- Bağlantı kopunca banner: "Yeniden bağlanılıyor... 9s"
- Başarılıysa game state restore edilir
- Başarısızsa: "Bağlantı kesildi" + sonuç ekranı

**AdMob Entegrasyonu**
- Interstitial: oyun sonu ekranından önce (atlanabilir 5s)
- Rewarded: "İzle ve 1 can hakkı kazan" (elenenler için)
- Banner: lobi bekleme ekranı altı

**Haptic Feedback**
- Doğru cevap: `HapticFeedback.lightImpact()`
- Yanlış cevap: `HapticFeedback.heavyImpact()`
- Eleme: `HapticFeedback.vibrate()` (uzun)
- Slider sürükleme: `HapticFeedback.selectionClick()` (her tik)

---

## HAFTA 9 — Leaderboard + Sosyal Özellikler

### Backend + Flutter

**Leaderboard Backend**
- Redis Sorted Set zaten var: `leaderboard:daily`, `leaderboard:weekly`, `leaderboard:seasonal`
- `ZREVRANK` ile kendi sıranı bul (O(log N))
- Sayfalamalı endpoint: `ZREVRANGE ... WITHSCORES LIMIT offset count`
- Arkadaşlar leaderboard'u: kullanıcının arkadaş ID listesiyle filtreli

**Leaderboard UI** (`lib/features/leaderboard/`)
- Tab bar: Günlük | Haftalık | Sezonluk | Arkadaşlar
- Top 3 podyum (animasyonlu, büyük avatar)
- Liste (sayfa sayfa yükleme, sonsuz scroll)
- Kendi sırası — ekranın altında sabit bar: "Sen: #847 | 1.240 puan"
- Motivasyon mesajı: "Bir üst sıraya 80 puan lazım! 🔥"
- Sezon geri sayımı: "Sezon bitmesine 12 gün"
- Profil tıklanabilir

**Arkadaşlık Sistemi**
- Backend: `POST /api/friends/request`, `POST /api/friends/accept`, `GET /api/friends`
- Oyun sonu arkadaş ekleme (bir tıkla)
- Kullanıcı adı arama
- QR kod ile ekleme
- Arkadaşlık seviyesi rozeti profilde görünür

**Davet Kodu Sistemi** (YENİ ÖZELLIK)
- Her kullanıcıya 6 haneli referans kodu (ör: `MERT42`)
- Davet edenin her kaydolan arkadaş için +50 coin
- Davet edilenin ilk kaydında +100 coin (onboarding'de göster)
- `referral_code` alanı `users` tablosuna eklenir

**Push Bildirimler** (FCM)
- "3 arkadaşın şu an oynuyor!" (günde max 2 kez)
- "Günlük Meydan Okuma hazır!" (her sabah 09:00)
- "Biri seni arkadaş listesine ekledi"
- "Leaderboard'da 5 sıra yükseldin!"

---

## HAFTA 10 — Hile Önleme + Ses + Polish + Yük Testi

### Backend — Hile Önleme

**Sunucu Taraflı Doğrulama**
- Tüm cevaplar sunucuya timestamp ile gelir
- `received_at - question_sent_at > round_duration` → geçersiz say
- İstemcinin saatine güvenme: sunucu zamanı kullan

**Davranış Analizi** (`services/anti_cheat_service.py`)
- Round 1-3'te %40 doğru yapan biri Round 5'te sihirli tahmin yaparsa → flag
- Slider'a hiç dokunmadan gerçek cevaba çok yakın değer → şüpheli
- 3 oyun üst üste mükemmel skor → manuel inceleme kuyruğu
- Mantıksız response time (< 200ms her zaman) → bot şüphesi

**Bağlantı Kesme = Eleme**
- WebSocket bağlantısı kesilince ve 10s pencere geçince → elendi olarak işle
- Bağlantı kopma istatistikleri kaydedilir (sürekli kopanlar flag)

### Flutter — Hile Önleme

- Android: `FLAG_SECURE` (screenshot engelleyin)
- iOS: `UITextField.isSecureTextEntry` benzeri overlay
- Split-screen: `setRequestedOrientation(PORTRAIT)` manifest

### Flutter — Ses Efektleri

```
assets/audio/
├── correct.mp3       # Kısa ding
├── wrong.mp3         # Kısa buzz
├── countdown.mp3     # Son 3 saniye tik-tak
├── elimination.mp3   # Çığlık + düşüş
├── win.mp3           # Konfeti patlaması
├── lobby_join.mp3    # Pop
├── round_start.mp3   # Vızıltı
└── lobby_bg.mp3      # Lobi ambiyans müziği (döngü)
```

### Yük Testi
- 50+ eşzamanlı WebSocket bağlantısı
- 10 paralel lobi
- Redis altında leaderboard query
- PostgreSQL bağlantı pool testi
- P95 latency hedefi: < 200ms

---

## HAFTA 11 — Kapalı Beta + Monitoring

**Beta Sürümü**
- 50 test kullanıcısı (güvenilir çevre)
- iOS TestFlight + Android APK dağıtımı
- Geri bildirim formu (Google Form)
- Kritik akışlar: kayıt → lobi → oyun → sonuç → leaderboard

**Monitoring Kurulumu**
- **Sentry**: Backend + Flutter crash raporlama
- **Firebase Analytics**: Özel event'ler:
  - `lobby_joined`, `game_started`, `round_answered`
  - `game_won`, `game_lost`, `ad_watched`
  - `friend_added`, `leaderboard_viewed`
- **Grafana**: QPS, WebSocket bağlantı sayısı, Redis memory, PG connections
- **Alerting**: Sentry'de P0 hatalar için Slack webhook

**Beta'dan Öğrenilecekler**
- Lobi bekleme süresi toleransı (kaç saniyede çıkıyorlar?)
- En çok eleme yapan tur hangisi? (zorluk dengesi)
- Bot fark ediliyor mu?
- Animasyon süresi uzun mu hissettiriyor?
- Crash hotspot'ları

---

## HAFTA 12 — Lansman

**App Store Hazırlığı**
- Metadata: başlık, açıklama (TR), keywords
- Ekran görüntüleri (6.7", 6.5", 12.9" iPad)
- Preview video (30s)
- Privacy policy (KVKK + GDPR uyumlu)
- Age rating: 4+
- Review notları: Bot sistemi, reklam açıklaması

**Play Store Hazırlığı**
- Feature graphic (1024x500)
- 8 ekran görüntüsü
- Kısa ve uzun açıklama
- İçerik derecelendirmesi formu

**Yumuşak Lansman (Türkiye)**
- İlk hafta: sadece Türkiye
- Kritik metrikleri izle: crash rate, D1 retention, lobi başarı oranı
- Crash rate > %1 → güncelleme yayınla
- D1 retention < %20 → onboarding revizyonu

**Post-Lansman İzleme (İlk 48 Saat)**
- Sentry dashboard 24/7
- Leaderboard manipülasyon tespiti
- Sunucu kaynak kullanımı
- Store yorumları yanıtlama

---

## BENIM EKLEDİKLERİM (Orijinal Planda Olmayan)

| Özellik | Hafta | Etki |
|---------|-------|------|
| **Adaptif Eşik Sistemi (AAS)** | 3 | Lobi asla iptal olmaz |
| **Bot doğal katılım zamanlaması** | 3 | Botlar fark edilmez |
| **Bekleme odası ısınma sorusu** | 3 | Bekleme sıkıcı değil |
| **Yeniden bağlanma penceresi** | 3-4 | Bağlantı kopmak = elenmek değil |
| **Seyirci modu** | 4 | Elenince kapanmıyor, izliyor |
| **Anti-tilt sistemi** | 4 | 3 kayıp sonrası gizli kolaylık |
| **Günlük Meydan Okuma** | 5 | Günlük geri dönüş sebebi |
| **Oyun sonu soru oylaması** | 5 | Kitle kaynaklı kalite kontrolü |
| **Davet kodu sistemi** | 9 | Viral büyüme mekanizması |
| **Motivasyon mesajları leaderboard** | 9 | Retention artışı |
| **Davranış analizi anti-cheat** | 10 | Leaderboard güvenilirliği |

---

## ÖZET TAKVİM

| Hafta | Konu | Çıktı |
|-------|------|-------|
| ~~1~~ | Proje kurulumu | 24 test ✅ |
| ~~2~~ | Auth + Profil | 66 test ✅ |
| **3** | WebSocket + Lobi + AAS | Gerçek eşleşme çalışıyor |
| **4** | Oyun döngüsü WS | Tam oyun oynanabilir |
| **5** | Soru sistemi + AI | 500+ soru havuzu |
| **6** | Flutter kurulum + temel UI | Auth + Ana menü çalışıyor |
| **7** | Oyun ekranları + WS istemci | Oynanabilir mobil |
| **8** | Animasyonlar + Reklam | Gösterilebilir ürün |
| **9** | Leaderboard + Sosyal | Tam sosyal döngü |
| **10** | Hile önleme + Polish + Test | Beta hazır |
| **11** | Kapalı beta + Monitoring | 50 gerçek kullanıcı |
| **12** | Lansman | App Store + Play Store |
