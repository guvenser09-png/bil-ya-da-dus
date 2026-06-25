import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';

/// Sezon ödül objesi: coins / cosmetic.
class SeasonReward {
  const SeasonReward({required this.type, this.amount, this.cosmeticId, this.cosmeticName});

  /// 'coins' | 'cosmetic'
  final String type;
  final int? amount;
  final String? cosmeticId;
  final String? cosmeticName;

  static SeasonReward? fromJson(Map<String, dynamic>? j) {
    if (j == null) return null;
    return SeasonReward(
      type: j['type']?.toString() ?? 'coins',
      amount: (j['amount'] as num?)?.toInt(),
      cosmeticId: j['cosmetic_id']?.toString(),
      cosmeticName: j['cosmetic_name']?.toString() ?? j['name']?.toString(),
    );
  }

  /// Ödül tipine göre ikon emojisi.
  String get icon {
    switch (type) {
      case 'cosmetic':
        return '🎨';
      case 'coins':
      default:
        return '🪙';
    }
  }

  /// Kart üzerinde gösterilecek kısa etiket.
  String get label {
    switch (type) {
      case 'cosmetic':
        return cosmeticName ?? 'Kozmetik';
      case 'coins':
      default:
        return amount != null ? '$amount' : '?';
    }
  }
}

/// Tek bir sezon kademesi (tier) — TEK ücretsiz ödül hattı.
///
/// Battle Pass / premium hat tamamen kaldırıldı: artık her kademenin yalnızca
/// oynayarak (sezon puanı) açılan tek ödülü var.
class SeasonTier {
  const SeasonTier({
    required this.tier,
    required this.pointsRequired,
    this.reward,
    this.claimed = false,
    this.claimable = false,
  });

  final int tier;
  final int pointsRequired;
  final SeasonReward? reward;
  final bool claimed;
  final bool claimable;

  factory SeasonTier.fromJson(Map<String, dynamic> j) => SeasonTier(
        tier: (j['tier'] as num?)?.toInt() ?? 0,
        pointsRequired: (j['points_required'] as num?)?.toInt() ?? 0,
        // Ücretsiz hat tek ödül kaynağıdır; eski payload'larda `reward` da
        // gelebilir, `free_reward` da — ikisini de tolere et.
        reward: SeasonReward.fromJson(
          (j['reward'] ?? j['free_reward']) as Map<String, dynamic>?,
        ),
        claimed: (j['claimed'] ?? j['free_claimed']) as bool? ?? false,
        claimable: (j['claimable'] ?? j['free_claimable']) as bool? ?? false,
      );
}

class SeasonState {
  const SeasonState({
    this.seasonId,
    this.endsInDays = 0,
    this.myPoints = 0,
    this.myTier = 0,
    this.tiers = const [],
    this.loading = false,
    this.busyKey,
    this.loaded = false,
    this.error,
  });

  final String? seasonId;
  final int endsInDays;
  final int myPoints;
  final int myTier;
  final List<SeasonTier> tiers;
  final bool loading;

  /// İşlemde olan buton anahtarı ("claim_3_free" vb.) — spinner için.
  final String? busyKey;
  final bool loaded;
  final String? error;

  SeasonState copyWith({
    Object? seasonId = _s,
    int? endsInDays,
    int? myPoints,
    int? myTier,
    List<SeasonTier>? tiers,
    bool? loading,
    Object? busyKey = _s,
    bool? loaded,
    Object? error = _s,
  }) =>
      SeasonState(
        seasonId: identical(seasonId, _s) ? this.seasonId : seasonId as String?,
        endsInDays: endsInDays ?? this.endsInDays,
        myPoints: myPoints ?? this.myPoints,
        myTier: myTier ?? this.myTier,
        tiers: tiers ?? this.tiers,
        loading: loading ?? this.loading,
        busyKey: identical(busyKey, _s) ? this.busyKey : busyKey as String?,
        loaded: loaded ?? this.loaded,
        error: identical(error, _s) ? this.error : error as String?,
      );

  static const Object _s = Object();

  /// Bir sonraki tier'a göre ilerleme bilgileri.
  /// Kalan tier yoksa (hepsi tamam) [progress] = 1 döner.
  ({int prevPoints, int nextPoints, double progress, SeasonTier? next}) get progressInfo {
    if (tiers.isEmpty) return (prevPoints: 0, nextPoints: 0, progress: 0, next: null);
    final sorted = [...tiers]..sort((a, b) => a.pointsRequired.compareTo(b.pointsRequired));
    SeasonTier? next;
    var prevPoints = 0;
    for (final t in sorted) {
      if (myPoints < t.pointsRequired) {
        next = t;
        break;
      }
      prevPoints = t.pointsRequired;
    }
    if (next == null) {
      return (prevPoints: prevPoints, nextPoints: prevPoints, progress: 1, next: null);
    }
    final span = next.pointsRequired - prevPoints;
    final into = myPoints - prevPoints;
    final progress = span <= 0 ? 1.0 : (into / span).clamp(0.0, 1.0);
    return (prevPoints: prevPoints, nextPoints: next.pointsRequired, progress: progress, next: next);
  }
}

class SeasonNotifier extends StateNotifier<SeasonState> {
  SeasonNotifier() : super(const SeasonState()) {
    load();
  }

  Future<void> load() async {
    state = state.copyWith(loading: true, error: null);
    try {
      final r = await ApiClient.instance.get('/api/season');
      state = _applyResponse(r).copyWith(loading: false, loaded: true);
    } catch (_) {
      state = state.copyWith(loading: false, loaded: true, error: 'Sezon bilgisi yüklenemedi.');
    }
  }

  /// Bir kademe ödülünü alır. Başarıda true.
  ///
  /// Tek ücretsiz hat olduğundan track parametresi kaldırıldı; backend
  /// sözleşmesi korunsun diye istek gövdesinde sabit `track: 'free'` gönderilir.
  Future<bool> claim(int tier) async {
    state = state.copyWith(busyKey: 'claim_$tier', error: null);
    try {
      await ApiClient.instance.post('/api/season/claim', body: {'tier': tier, 'track': 'free'});
      // Sunucu tarafı durum değişikliklerini (claimed bayrakları, bakiye) tazele.
      await load();
      return true;
    } catch (e) {
      state = state.copyWith(busyKey: null, error: _errorText(e));
      return false;
    }
  }

  SeasonState _applyResponse(Map<String, dynamic> r) {
    final tiersRaw = r['tiers'] as List? ?? [];
    final tiers = tiersRaw.whereType<Map<String, dynamic>>().map(SeasonTier.fromJson).toList();
    return state.copyWith(
      seasonId: r['season_id']?.toString(),
      endsInDays: (r['ends_in_days'] as num?)?.toInt() ?? 0,
      myPoints: (r['my_points'] as num?)?.toInt() ?? 0,
      myTier: (r['my_tier'] as num?)?.toInt() ?? 0,
      // has_battle_pass backend hâlâ dönebilir → BİLEREK yok sayılıyor.
      tiers: tiers,
      busyKey: null,
    );
  }

  String _errorText(Object e) {
    final s = e.toString();
    if (s.contains('400')) return 'İşlem yapılamadı (uygun değil ya da bakiye yetersiz).';
    return 'Bir hata oluştu, tekrar deneyin.';
  }
}

final seasonProvider =
    StateNotifierProvider<SeasonNotifier, SeasonState>((_) => SeasonNotifier());
