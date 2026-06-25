import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/constants/app_constants.dart';
import 'package:quizroyale/core/network/api_client.dart';
import 'package:quizroyale/core/network/ws_client.dart';

/// Oda (özel/arkadaşlarla) lobisinin durumu. Tekil [WsClient.instance] üzerinden
/// `/ws/room/{code}` soketini yönetir. Hızlı maç lobisi (lobby_provider) ile
/// AYNI tekil soketi kullandığımız için, oyuna geçerken/odadan çıkarken aboneliği
/// temizleyip onReconnect kancasını null'lamak ZORUNLUDUR; aksi halde oyun
/// mesajları bu handler'a sızar.
enum RoomStatus { idle, connecting, inRoom, starting, closed, error }

class RoomState {
  const RoomState({
    this.code,
    this.members = const [],
    this.isHost = false,
    this.hostUserId,
    this.status = RoomStatus.idle,
    this.gameId,
    this.error,
    this.closedReason,
  });

  /// 6 haneli oda kodu (server'dan gelir).
  final String? code;

  /// Üye listesi: her biri {user_id, username, display_name, avatar_id}.
  final List<Map<String, dynamic>> members;
  final bool isHost;
  final String? hostUserId;
  final RoomStatus status;

  /// `room_starting` geldiğinde set edilir → ekran /game'e geçer.
  final String? gameId;
  final String? error;

  /// `room_closed` sebebi (host ayrıldı vb.).
  final String? closedReason;

  RoomState copyWith({
    String? code,
    List<Map<String, dynamic>>? members,
    bool? isHost,
    String? hostUserId,
    RoomStatus? status,
    String? gameId,
    String? error,
    String? closedReason,
    bool clearError = false,
  }) {
    return RoomState(
      code: code ?? this.code,
      members: members ?? this.members,
      isHost: isHost ?? this.isHost,
      hostUserId: hostUserId ?? this.hostUserId,
      status: status ?? this.status,
      gameId: gameId ?? this.gameId,
      error: clearError ? null : (error ?? this.error),
      closedReason: closedReason ?? this.closedReason,
    );
  }
}

class RoomNotifier extends StateNotifier<RoomState> {
  RoomNotifier() : super(const RoomState());

  StreamSubscription? _sub;

  /// Host olarak yeni oda kur: `code="new"` ile bağlan.
  Future<void> createRoom() => _connect('new');

  /// Var olan odaya katıl: 6 haneli kod ile bağlan.
  Future<void> joinRoom(String code) => _connect(code.trim().toUpperCase());

  Future<void> _connect(String code) async {
    _sub?.cancel();
    state = const RoomState(status: RoomStatus.connecting);

    // WS açmadan önce TAZE token sağla (lobby_provider deseni). Aksi halde
    // süresi dolmuş access token ile "4001 / not upgraded" alınır.
    final token = await ApiClient.instance.ensureValidAccessToken();
    if (token == null) {
      state = state.copyWith(
        status: RoomStatus.error,
        error: 'Oturum süresi doldu. Lütfen tekrar giriş yapın.',
      );
      return;
    }

    final url = '${AppConstants.wsBaseUrl}/ws/room/$code?token=$token';
    await WsClient.instance.connect(url);
    _sub = WsClient.instance.messages.listen(
      _handleMessage,
      onError: (_) {},
      cancelOnError: false,
    );

    // Kopma sonrası otomatik yeniden bağlanmada özel bir "join" mesajı GEREKMEZ:
    // odaya katılım URL'deki kod ile handshake'te gerçekleşir. Yine de eski
    // kancanın bu bağlama sızmaması için açıkça null'la.
    WsClient.instance.onReconnect = null;
  }

  void _handleMessage(Map<String, dynamic> msg) {
    try {
      final type = msg['type'] as String?;
      switch (type) {
        case 'room_created':
          state = state.copyWith(
            code: msg['code'] as String?,
            members: _members(msg['members']),
            isHost: msg['is_host'] as bool? ?? true,
            hostUserId: _str(msg['host_user_id']),
            status: RoomStatus.inRoom,
          );
        case 'room_joined':
          state = state.copyWith(
            code: msg['code'] as String?,
            members: _members(msg['members']),
            isHost: msg['is_host'] as bool? ?? false,
            hostUserId: _str(msg['host_user_id']),
            status: RoomStatus.inRoom,
          );
        case 'member_joined':
          state = state.copyWith(members: _members(msg['members']));
        case 'member_left':
          // Server güncel listeyi yolluyor; yoksa user_id'yi düşür.
          if (msg['members'] != null) {
            state = state.copyWith(members: _members(msg['members']));
          } else {
            final leftId = _str(msg['user_id']);
            final updated = state.members
                .where((m) => _str(m['user_id']) != leftId)
                .toList();
            state = state.copyWith(members: updated);
          }
        case 'room_starting':
          // Oyuna geçiyoruz: oda aboneliğini iptal et ki oyun mesajları (aynı
          // tekil WsClient üzerinden gelen) bu handler'a SIZMASIN. Soketi
          // KAPATMA — oyun ekranı aynı soketi kullanacak. onReconnect'i null'la.
          WsClient.instance.onReconnect = null;
          _sub?.cancel();
          _sub = null;
          state = state.copyWith(
            status: RoomStatus.starting,
            gameId: _str(msg['game_id']),
          );
        case 'room_closed':
          WsClient.instance.onReconnect = null;
          WsClient.instance.disconnect();
          _sub?.cancel();
          _sub = null;
          state = state.copyWith(
            status: RoomStatus.closed,
            closedReason: _str(msg['reason']) ?? 'Oda kapatıldı.',
          );
        case 'error':
          state = state.copyWith(
            status: RoomStatus.error,
            error: _errorMessage(_str(msg['message'])),
          );
        case 'ws_error':
          state = state.copyWith(
            status: RoomStatus.error,
            error: 'Bağlantı hatası. Tekrar dene.',
          );
      }
    } catch (_) {
      // Parse hatalarını sessizce yut — akışı öldürme.
    }
  }

  /// Host → oyunu başlat.
  void start() {
    if (!state.isHost) return;
    WsClient.instance.send({'action': 'start'});
  }

  /// Odadan ayrıl: server'a bildir, soketi kapat, aboneliği temizle.
  void leave() {
    WsClient.instance.onReconnect = null;
    WsClient.instance.send({'action': 'leave'});
    WsClient.instance.disconnect();
    _sub?.cancel();
    _sub = null;
    state = const RoomState();
  }

  /// Oyuna geçildikten sonra ekran ayrılırken çağrılır: soketi KAPATMADAN
  /// yalnızca abonelik temizliği (oyun ekranı soketi devralır).
  void detach() {
    WsClient.instance.onReconnect = null;
    _sub?.cancel();
    _sub = null;
  }

  static List<Map<String, dynamic>> _members(dynamic raw) {
    if (raw is! List) return const [];
    return raw
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
  }

  static String? _str(dynamic v) => v?.toString();

  /// Server hata kodlarını kullanıcı dostu Türkçe mesaja çevir.
  static String _errorMessage(String? raw) {
    switch (raw) {
      case 'room_not_found':
        return 'Oda bulunamadı. Kodu kontrol et.';
      case 'room_full':
        return 'Oda dolu.';
      case null:
        return 'Bir hata oluştu. Tekrar dene.';
      default:
        return raw;
    }
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}

final roomProvider = StateNotifierProvider<RoomNotifier, RoomState>(
  (_) => RoomNotifier(),
);
