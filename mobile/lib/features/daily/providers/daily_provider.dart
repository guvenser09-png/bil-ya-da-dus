import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';

/// Günlük ödül durumu — backend `GET /api/daily/status` yanıtını sarmalar.
class DailyState {
  const DailyState({
    this.canClaim = false,
    this.streak = 0,
    this.todayReward = 0,
    this.nextReward = 0,
    this.lastClaimAt,
    this.coins,
    this.loading = false,
    this.claiming = false,
    this.loaded = false,
    this.error,
  });

  /// Bugün ödül alınabilir mi?
  final bool canClaim;

  /// Kaç gün üst üste alındı (örn 3 → 🔥x3).
  final int streak;

  /// Bugün alınacak/alınmış coin miktarı.
  final int todayReward;

  /// Yarınki ödül (teşvik için gösterilir).
  final int nextReward;

  /// Son alım zamanı (ISO string), hiç alınmadıysa null.
  final String? lastClaimAt;

  /// claim sonrası dönen güncel coin bakiyesi (null → henüz bilinmiyor).
  final int? coins;

  final bool loading;
  final bool claiming;

  /// İlk yükleme tamamlandı mı? (rozeti yanlış göstermemek için)
  final bool loaded;

  final String? error;

  DailyState copyWith({
    bool? canClaim,
    int? streak,
    int? todayReward,
    int? nextReward,
    String? lastClaimAt,
    int? coins,
    bool? loading,
    bool? claiming,
    bool? loaded,
    Object? error = _sentinel,
  }) =>
      DailyState(
        canClaim: canClaim ?? this.canClaim,
        streak: streak ?? this.streak,
        todayReward: todayReward ?? this.todayReward,
        nextReward: nextReward ?? this.nextReward,
        lastClaimAt: lastClaimAt ?? this.lastClaimAt,
        coins: coins ?? this.coins,
        loading: loading ?? this.loading,
        claiming: claiming ?? this.claiming,
        loaded: loaded ?? this.loaded,
        error: identical(error, _sentinel) ? this.error : error as String?,
      );

  static const Object _sentinel = Object();
}

/// claim sonucu — UI animasyon/teşekkür için kullanır.
class ClaimResult {
  const ClaimResult({
    required this.claimed,
    required this.reward,
    required this.streak,
    required this.coins,
    this.alreadyClaimed = false,
  });

  /// Ödül bu çağrıda gerçekten alındı mı?
  final bool claimed;
  final int reward;
  final int streak;
  final int coins;

  /// claimed=false sebebi: bugün zaten alınmış.
  final bool alreadyClaimed;
}

class DailyNotifier extends StateNotifier<DailyState> {
  DailyNotifier() : super(const DailyState());

  /// Durumu backend'den çeker. Açılışta home_screen çağırır.
  Future<void> load() async {
    state = state.copyWith(loading: true, error: null);
    try {
      final r = await ApiClient.instance.get('/api/daily/status');
      state = state.copyWith(
        loading: false,
        loaded: true,
        canClaim: r['can_claim'] as bool? ?? false,
        streak: (r['streak'] as num?)?.toInt() ?? 0,
        todayReward: (r['today_reward'] as num?)?.toInt() ?? 0,
        nextReward: (r['next_reward'] as num?)?.toInt() ?? 0,
        lastClaimAt: r['last_claim_at'] as String?,
      );
    } catch (_) {
      // Sessizce geç: rozet gösterilmez, uygulama akışı bozulmaz.
      state = state.copyWith(loading: false, loaded: true, error: 'Günlük ödül yüklenemedi');
    }
  }

  /// Ödülü alır. Sonucu döndürür (UI animasyon için kullanır).
  Future<ClaimResult?> claim() async {
    if (state.claiming) return null;
    state = state.copyWith(claiming: true, error: null);
    try {
      final r = await ApiClient.instance.post('/api/daily/claim');
      final claimed = r['claimed'] as bool? ?? false;
      final reward = (r['reward'] as num?)?.toInt() ?? 0;
      final streak = (r['streak'] as num?)?.toInt() ?? state.streak;
      final coins = (r['coins'] as num?)?.toInt() ?? state.coins ?? 0;
      state = state.copyWith(
        claiming: false,
        // Alındıysa bir daha alınamaz.
        canClaim: claimed ? false : state.canClaim,
        streak: streak,
        coins: coins,
      );
      return ClaimResult(
        claimed: claimed,
        reward: reward,
        streak: streak,
        coins: coins,
        alreadyClaimed: !claimed,
      );
    } catch (_) {
      state = state.copyWith(claiming: false, error: 'Ödül alınamadı, tekrar deneyin');
      return null;
    }
  }
}

final dailyProvider =
    StateNotifierProvider<DailyNotifier, DailyState>((_) => DailyNotifier());
