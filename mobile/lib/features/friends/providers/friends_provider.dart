import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';

/// Arkadaşlık sisteminin durumu.
///
/// Backend sözleşmesi (kullanıcı nesneleri `user_id`, `username`,
/// `display_name`, `avatar_id`, `level` ... alanlarını içerir):
///  - GET    /api/friends           → {friends:[...]}
///  - GET    /api/friends/requests  → {incoming:[...], outgoing:[...]}
///  - GET    /api/friends/search?q= → {users:[{..., status}]}
///  - POST   /api/friends/request   {user_id}
///  - POST   /api/friends/accept    {user_id}
///  - POST   /api/friends/reject    {user_id}
///  - DELETE /api/friends/{user_id}
class FriendsState {
  const FriendsState({
    this.friends = const [],
    this.incoming = const [],
    this.outgoing = const [],
    this.searchResults = const [],
    this.isLoading = false,
    this.isSearching = false,
    this.error,
  });

  /// Arkadaş listesi.
  final List<Map<String, dynamic>> friends;

  /// Bana gelen (kabul/reddet edebileceğim) istekler.
  final List<Map<String, dynamic>> incoming;

  /// Benim gönderdiğim, karşı tarafın yanıtını bekleyen istekler.
  final List<Map<String, dynamic>> outgoing;

  /// Arama sonuçları — her biri `status` alanı taşır:
  /// 'none' | 'friend' | 'incoming' | 'outgoing'.
  final List<Map<String, dynamic>> searchResults;

  final bool isLoading;
  final bool isSearching;
  final String? error;

  FriendsState copyWith({
    List<Map<String, dynamic>>? friends,
    List<Map<String, dynamic>>? incoming,
    List<Map<String, dynamic>>? outgoing,
    List<Map<String, dynamic>>? searchResults,
    bool? isLoading,
    bool? isSearching,
    String? error,
  }) =>
      FriendsState(
        friends: friends ?? this.friends,
        incoming: incoming ?? this.incoming,
        outgoing: outgoing ?? this.outgoing,
        searchResults: searchResults ?? this.searchResults,
        isLoading: isLoading ?? this.isLoading,
        isSearching: isSearching ?? this.isSearching,
        // error null'a sıfırlanabilmeli: her copyWith çağrısında açıkça aktar.
        error: error,
      );
}

class FriendsNotifier extends StateNotifier<FriendsState> {
  FriendsNotifier() : super(const FriendsState()) {
    // Açılışta arkadaşları ve istekleri birlikte yükle.
    loadFriends();
    loadRequests();
  }

  /// API yanıtındaki bir listeyi güvenli biçimde `Map<String, dynamic>`
  /// listesine çevirir (beklenmeyen/eksik alanlara karşı dayanıklı).
  List<Map<String, dynamic>> _castList(dynamic raw) {
    if (raw is! List) return const [];
    return raw
        .whereType<Map>()
        .map((e) => e.map((k, v) => MapEntry(k.toString(), v)))
        .toList();
  }

  Future<void> loadFriends() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final resp = await ApiClient.instance.get('/api/friends');
      state = state.copyWith(
        isLoading: false,
        friends: _castList(resp['friends']),
      );
    } catch (_) {
      state = state.copyWith(isLoading: false, error: 'Arkadaşlar yüklenemedi');
    }
  }

  Future<void> loadRequests() async {
    try {
      final resp = await ApiClient.instance.get('/api/friends/requests');
      state = state.copyWith(
        incoming: _castList(resp['incoming']),
        outgoing: _castList(resp['outgoing']),
      );
    } catch (_) {
      state = state.copyWith(error: 'İstekler yüklenemedi');
    }
  }

  Future<void> search(String query) async {
    final q = query.trim();
    if (q.length < 2) {
      // Çok kısa sorgu: sonuçları temizle, ağ isteği yapma.
      state = state.copyWith(searchResults: const [], isSearching: false);
      return;
    }
    state = state.copyWith(isSearching: true);
    try {
      final resp =
          await ApiClient.instance.get('/api/friends/search', query: {'q': q});
      state = state.copyWith(
        isSearching: false,
        searchResults: _castList(resp['users']),
      );
    } catch (_) {
      state = state.copyWith(isSearching: false, searchResults: const []);
    }
  }

  /// Arama sonucu satırının durumunu yerel olarak günceller (anında geri
  /// bildirim için). Listeler yeniden çekildiğinde gerçek durum gelir.
  void _patchSearchStatus(String userId, String status) {
    final updated = state.searchResults.map((u) {
      if (u['user_id'] == userId) {
        return {...u, 'status': status};
      }
      return u;
    }).toList();
    state = state.copyWith(searchResults: updated);
  }

  Future<void> sendRequest(String userId) async {
    try {
      await ApiClient.instance
          .post('/api/friends/request', body: {'user_id': userId});
      _patchSearchStatus(userId, 'outgoing');
      await loadRequests();
    } catch (_) {
      state = state.copyWith(error: 'İstek gönderilemedi');
    }
  }

  Future<void> accept(String userId) async {
    try {
      await ApiClient.instance
          .post('/api/friends/accept', body: {'user_id': userId});
      _patchSearchStatus(userId, 'friend');
      // Kabul edilince hem istek hem arkadaş listesi değişir.
      await Future.wait([loadRequests(), loadFriends()]);
    } catch (_) {
      state = state.copyWith(error: 'İstek kabul edilemedi');
    }
  }

  Future<void> reject(String userId) async {
    try {
      await ApiClient.instance
          .post('/api/friends/reject', body: {'user_id': userId});
      _patchSearchStatus(userId, 'none');
      await loadRequests();
    } catch (_) {
      state = state.copyWith(error: 'İstek reddedilemedi');
    }
  }

  Future<void> removeFriend(String userId) async {
    try {
      await ApiClient.instance.delete('/api/friends/$userId');
      _patchSearchStatus(userId, 'none');
      await loadFriends();
    } catch (_) {
      state = state.copyWith(error: 'Arkadaş silinemedi');
    }
  }
}

final friendsProvider = StateNotifierProvider<FriendsNotifier, FriendsState>(
  (_) => FriendsNotifier(),
);
