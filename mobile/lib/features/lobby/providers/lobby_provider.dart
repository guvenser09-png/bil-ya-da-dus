import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/constants/app_constants.dart';
import 'package:quizroyale/core/network/api_client.dart';
import 'package:quizroyale/core/network/ws_client.dart';
import 'package:quizroyale/core/storage/secure_storage.dart';

class LobbyState {
  const LobbyState({
    this.lobbyId,
    this.players = const [],
    this.countdown = AppConstants.lobbyTimeoutSeconds,
    this.initialCountdown = AppConstants.lobbyTimeoutSeconds,
    this.isConnecting = false,
    this.isConnected = false,
    this.error,
    this.gameId,
  });

  final String? lobbyId;
  final List<Map<String, dynamic>> players;
  final int countdown;

  /// Sayacın başladığı değer — SUNUCUDAN gelen ilk countdown otoriterdir
  /// (lobby_joined.countdown_seconds). CountdownRing dolum oranı buna göre
  /// hesaplanır; böylece sabit 15 ile sunucu değeri ayrışırsa halka şaşmaz.
  final int initialCountdown;

  final bool isConnecting;
  final bool isConnected;
  final String? error;
  final String? gameId; // set when game_starting received

  LobbyState copyWith({
    String? lobbyId,
    List<Map<String, dynamic>>? players,
    int? countdown,
    int? initialCountdown,
    bool? isConnecting,
    bool? isConnected,
    String? error,
    String? gameId,
    bool clearError = false,
    bool clearGame = false,
  }) {
    return LobbyState(
      lobbyId: lobbyId ?? this.lobbyId,
      players: players ?? this.players,
      countdown: countdown ?? this.countdown,
      initialCountdown: initialCountdown ?? this.initialCountdown,
      isConnecting: isConnecting ?? this.isConnecting,
      isConnected: isConnected ?? this.isConnected,
      error: clearError ? null : (error ?? this.error),
      gameId: clearGame ? null : (gameId ?? this.gameId),
    );
  }
}

class LobbyNotifier extends StateNotifier<LobbyState> {
  LobbyNotifier() : super(const LobbyState());

  StreamSubscription? _sub;
  String _avatarId = 'robot';
  String? _mode;

  /// [mode] verilirse (ör. "tournament") join mesajına eklenir; verilmezse
  /// normal "Hızlı Maç" akışı çalışır (alan gönderilmez).
  Future<void> connect({String avatarId = 'robot', String? mode}) async {
    _avatarId = avatarId;
    _mode = mode;
    _sub?.cancel();
    state = const LobbyState(isConnecting: true);
    // WS açmadan önce TAZE token sağla (30 dk'lık access token süresi dolmuşsa
    // refresh ile yenilenir). Yoksa "not upgraded to websocket / 4001" alınır.
    final token = await ApiClient.instance.ensureValidAccessToken();
    if (token == null) {
      state = state.copyWith(
        isConnecting: false,
        error: 'Oturum süresi doldu. Lütfen tekrar giriş yapın.',
      );
      return;
    }
    final url = '${AppConstants.wsBaseUrl}/ws/lobby?token=$token';
    await WsClient.instance.connect(url);
    _sub = WsClient.instance.messages.listen(
      _handleMessage,
      onError: (_) {},
      cancelOnError: false,
    );
    state = state.copyWith(isConnecting: false, isConnected: true);

    // Send join action
    final username = await SecureStorage.instance.getUsername() ?? 'oyuncu';
    void sendJoin() {
      WsClient.instance.send({
        'action': 'join',
        'username': username,
        'display_name': username,
        'avatar_id': _avatarId,
        // Turnuva maçı için mode iletilir; normal maçta alan eklenmez.
        if (_mode != null) 'mode': _mode,
      });
    }

    // Bağlantı koparsa (ör. sunucu yeniden başladı) otomatik yeniden bağlanınca
    // join'i TEKRAR gönder — yoksa lobi donar (sayaç/oyuncu gelmez).
    WsClient.instance.onReconnect = sendJoin;
    sendJoin();
  }

  void _handleMessage(Map<String, dynamic> msg) {
    try {
      final type = msg['type'] as String?;
      switch (type) {
        case 'lobby_joined':
          // Sunucudan gelen ilk countdown OTORİTER: hem sayaç hem de halka
          // dolum oranının paydası (initialCountdown) buradan beslenir.
          final serverCountdown =
              (msg['countdown_seconds'] as num?)?.toInt() ?? AppConstants.lobbyTimeoutSeconds;
          state = state.copyWith(
            lobbyId: msg['lobby_id'] as String?,
            players: List<Map<String, dynamic>>.from(msg['players'] ?? []),
            countdown: serverCountdown,
            initialCountdown: serverCountdown,
          );
        case 'player_joined':
          final newUsername = msg['username'];
          // Aynı username zaten listedeyse TEKRAR ekleme (çift sayma koruması):
          // lobby_joined kendimizi zaten eklemiş olabilir, backend de
          // player_joined yayınlayabilir. Username'e göre dedupe et.
          final alreadyPresent =
              state.players.any((p) => p['username'] == newUsername);
          if (!alreadyPresent) {
            // 12 slot üst sınırını aşma: gösterilen liste asla MAX'ı geçmesin.
            if (state.players.length < AppConstants.maxPlayers) {
              final updated = [
                ...state.players,
                {
                  'username': newUsername,
                  'display_name': msg['display_name'],
                  'avatar_id': msg['avatar_id'],
                },
              ];
              state = state.copyWith(players: updated);
            }
          }
        case 'player_left':
          final updated = state.players
              .where((p) => p['username'] != msg['username'])
              .toList();
          state = state.copyWith(players: updated);
        case 'countdown':
          final remaining = msg['remaining'];
          final countdown = remaining is int ? remaining : (remaining as num?)?.toInt() ?? state.countdown;
          state = state.copyWith(
            countdown: countdown,
            // Savunmacı: sunucu sayacı bilinen başlangıcın ÜZERİNDE tikliyorsa
            // (örn. lobby_joined kaçtı) paydayı da yükselt ki oran taşmasın.
            initialCountdown:
                countdown > state.initialCountdown ? countdown : null,
          );
        case 'game_starting':
          // Oyuna geçiyoruz. Oyun ekranı ARTIK KENDİ bağımsız WsClient
          // örneğiyle ayrı bir OYUN soketi açacak (lobi tekilini paylaşmaz).
          // Bu yüzden lobi soketini tamamen kapatıyoruz: aboneliği iptal et,
          // reconnect kancasını null'la ve soketi kapat. Böylece lobi soketi
          // arka planda canlı kalıp oyun soketiyle çakışmaz ve sunucuda aynı
          // kullanıcı için iki açık bağlantı kalmaz.
          final gid = msg['game_id'] as String?;
          WsClient.instance.onReconnect = null;
          _sub?.cancel();
          _sub = null;
          WsClient.instance.disconnect();
          state = state.copyWith(gameId: gid);
        case 'lobby_cancelled':
          state = state.copyWith(error: 'Lobi iptal edildi. Tekrar dene.');
        case 'ws_error':
          state = state.copyWith(error: 'Bağlantı hatası. Tekrar dene.');
      }
    } catch (_) {
      // Silently ignore parse errors — don't kill the stream
    }
  }

  void sendEmoji(String emoji) {
    if (!AppConstants.allowedEmojis.contains(emoji)) return;
    WsClient.instance.send({'action': 'emoji', 'emoji': emoji});
  }

  void disconnect() {
    WsClient.instance.onReconnect = null;
    WsClient.instance.send({'action': 'leave'});
    WsClient.instance.disconnect();
    _sub?.cancel();
    state = const LobbyState();
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}

final lobbyProvider = StateNotifierProvider<LobbyNotifier, LobbyState>(
  (_) => LobbyNotifier(),
);
