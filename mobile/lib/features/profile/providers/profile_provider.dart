import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';

class ProfileState {
  const ProfileState({
    this.profile,
    this.stats,
    this.isLoading = false,
    this.isSaving = false,
    this.error,
  });

  final Map<String, dynamic>? profile;
  // Detaylı istatistikler (/api/users/me/stats): games_played, games_won,
  // win_rate, best_rank, accuracy_rate, best_streak vb. Profil ekranı bunları
  // kullanır; /users/me bu alanları iç "stats" nesnesi olarak DÖNDÜRMEZ.
  final Map<String, dynamic>? stats;
  final bool isLoading;
  final bool isSaving;
  final String? error;

  ProfileState copyWith({
    Map<String, dynamic>? profile,
    Map<String, dynamic>? stats,
    bool? isLoading,
    bool? isSaving,
    String? error,
  }) => ProfileState(
    profile: profile ?? this.profile,
    stats: stats ?? this.stats,
    isLoading: isLoading ?? this.isLoading,
    isSaving: isSaving ?? this.isSaving,
    error: error,
  );
}

class ProfileNotifier extends StateNotifier<ProfileState> {
  ProfileNotifier() : super(const ProfileState()) {
    load();
  }

  Future<void> load({String? username}) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final endpoint = username != null ? '/api/users/$username' : '/api/users/me';
      final resp = await ApiClient.instance.get(endpoint);
      state = state.copyWith(isLoading: false, profile: resp);
    } catch (_) {
      state = state.copyWith(isLoading: false, error: 'Profil yüklenemedi');
    }
    // İstatistikleri ayrı uçtan çek (profil yüklenmişse bile dene). Hata
    // sessiz yutulur — profil yine de gösterilir.
    await _loadStats(username: username);
  }

  /// Detaylı istatistikleri /api/users/me/stats (veya /{id}/stats) çağrısıyla
  /// alır ve state.stats'a yazar. Profil ekranı istatistik kartları bunu okur.
  Future<void> _loadStats({String? username}) async {
    try {
      final endpoint =
          username != null ? '/api/users/$username/stats' : '/api/users/me/stats';
      final resp = await ApiClient.instance.get(endpoint);
      state = state.copyWith(stats: Map<String, dynamic>.from(resp));
    } catch (_) {
      // Sessiz yut — istatistik gelmezse kartlar 0 gösterir.
    }
  }

  Future<bool> update({String? bio, String? avatarId, List<String>? interests}) async {
    state = state.copyWith(isSaving: true, error: null);
    try {
      final body = <String, dynamic>{};
      if (bio != null) body['bio'] = bio;
      if (avatarId != null) body['avatar_id'] = avatarId;
      if (interests != null) body['interests'] = interests;
      final resp = await ApiClient.instance.patch('/api/users/me', body: body);
      state = state.copyWith(isSaving: false, profile: resp);
      return true;
    } catch (_) {
      state = state.copyWith(isSaving: false, error: 'Kaydedilemedi');
      return false;
    }
  }
}

final profileProvider = StateNotifierProvider<ProfileNotifier, ProfileState>(
  (_) => ProfileNotifier(),
);

// For viewing other users' profiles
final otherProfileProvider = StateNotifierProvider.family<ProfileNotifier, ProfileState, String>(
  (_, username) => ProfileNotifier()..load(username: username),
);
