class AppConstants {
  AppConstants._();

  // Ortam-yapılandırılabilir API adresleri.
  //
  // UYARI (App Store / release): Aşağıdaki localhost varsayılanları YALNIZCA
  // yerel geliştirme içindir. Release (App Store) derlemesinde localhost'a
  // ASLA gönderim yapılmamalıdır; bu durumda uygulama hiçbir sunucuya
  // bağlanamaz ve App Store incelemesinde reddedilir.
  //
  // Release derlemesinde MUTLAKA üretim HTTPS/WSS adresleri --dart-define ile
  // verilmelidir, ör.:
  //   flutter build ipa --release \
  //     --dart-define=API_BASE_URL=https://api.bilyadadus.com \
  //     --dart-define=WS_BASE_URL=wss://api.bilyadadus.com
  //
  // Not: Default'lar bilerek silinmedi; debug/dev akışını bozmamak için
  // korunuyor. iOS ATS varsayılan (güvenli) olduğundan release'te yalnızca
  // https:// / wss:// adresleri çalışır.
  static const String baseUrl =
      String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000');
  static const String wsBaseUrl =
      String.fromEnvironment('WS_BASE_URL', defaultValue: 'ws://localhost:8000');
  static const String appName = 'Bil ya da Düş';

  // Sunucu ile birebir aynı değerler (settings.MAX_PLAYERS=12,
  // settings.LOBBY_TIMEOUT_SECONDS=15). Sunucudan gelen countdown/oyuncu
  // sayısı her zaman OTORİTERDİR; bunlar yalnızca ilk çizim ve üst sınırdır.
  static const int maxPlayers = 12;
  static const int lobbyTimeoutSeconds = 15;
  static const int reconnectWindowSeconds = 10;
  static const int reconnectMaxAttempts = 3;

  static const List<String> allowedEmojis = [
    '👏', '😂', '😱', '🔥', '💀', '❤️', '👍', '😎',
  ];

  // Hazır maç içi mesajlar (💬) — SABİT liste, serbest metin YOK.
  // id sunucuya gönderilir; metin SUNUCU tarafındaki izin listesinden çözülür
  // (backend ws/game.py QUICK_MESSAGES ile birebir aynı tutulmalı).
  static const Map<String, String> quickMessages = {
    'qm_gl': 'İyi şanslar! 🍀',
    'qm_wp': 'Helal! 👏',
    'qm_gg': 'GG 🔥',
    'qm_ah': 'Ah be! 😅',
    'qm_wow': 'Vay canına! 😱',
  };

  static const List<String> interestTags = [
    'Spor', 'Müzik', 'Film', 'Dizi', 'Teknoloji', 'Bilim',
    'Tarih', 'Coğrafya', 'Sanat', 'Yemek', 'Moda', 'Oyun',
    'Seyahat', 'Doğa', 'Edebiyat', 'Astronomi', 'Otomobil',
    'Haberler', 'Ekonomi', 'Sağlık',
  ];

  static const Map<String, String> roundTypeLabels = {
    'dogru_yanlis': 'Doğru / Yanlış',
    'gorsel': 'Görsel Soru',
    'karsilastirma': 'Karşılaştırma',
    'coktan_secmeli': 'Çoktan Seçmeli',
    'tahmin': 'Tahmin Sorusu',
  };

  static const Map<String, String> friendshipLevelLabels = {
    'TANIDIK': 'Tanıdık',
    'DOST': 'Dost',
    'SIKI_DOST': 'Sıkı Dost',
    'YOLDAS': 'Yoldaş',
  };
}
