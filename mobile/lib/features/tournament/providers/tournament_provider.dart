import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';

/// Turnuvaya giriş seçeneği (yalnızca altın).
class TournamentEntryOption {
  const TournamentEntryOption({
    required this.currency,
    required this.cost,
    required this.affordable,
  });

  /// "gold"
  final String currency;
  final int cost;
  final bool affordable;

  factory TournamentEntryOption.fromJson(Map<String, dynamic> j) =>
      TournamentEntryOption(
        currency: j['currency']?.toString() ?? 'gold',
        cost: (j['cost'] as num?)?.toInt() ?? 0,
        affordable: j['affordable'] as bool? ?? false,
      );

  String get icon => '🪙';
  String get currencyLabel => 'Altın';
}

/// Ödül vitrini satırı (sıra aralığına göre ödüller).
class TournamentRewardPreview {
  const TournamentRewardPreview({
    required this.rankRange,
    required this.title,
    required this.bonusGold,
    required this.cosmetics,
    required this.badge,
  });

  final String rankRange;
  final String title;
  final int bonusGold;
  final List<String> cosmetics;
  final String badge;

  factory TournamentRewardPreview.fromJson(Map<String, dynamic> j) =>
      TournamentRewardPreview(
        rankRange: j['rank_range']?.toString() ?? '',
        title: j['title']?.toString() ?? '',
        bonusGold: (j['bonus_gold'] as num?)?.toInt() ?? 0,
        cosmetics: (j['cosmetics'] as List? ?? const [])
            .map((e) => e.toString())
            .toList(),
        badge: j['badge']?.toString() ?? '🏆',
      );
}

class TournamentState {
  const TournamentState({
    this.loading = false,
    this.loaded = false,
    this.error,
    this.seasonId,
    this.secondsLeft = 0,
    this.pointMultiplier = 3,
    this.hardMode = true,
    this.description,
    this.entryOptions = const [],
    this.gold = 0,
    this.myRank,
    this.myScore,
    this.pointsToNext,
    this.rewards = const [],
    this.entering = false,
    this.entered = false,
  });

  final bool loading;
  final bool loaded;
  final String? error;

  final String? seasonId;

  /// Sezon bitişine kalan saniye (geri sayım için).
  final int secondsLeft;
  final int pointMultiplier;
  final bool hardMode;
  final String? description;
  final List<TournamentEntryOption> entryOptions;

  final int gold;

  /// Kendi turnuva sıram (my_entry). Henüz girmediyse null olabilir.
  final int? myRank;
  final int? myScore;
  final int? pointsToNext;

  final List<TournamentRewardPreview> rewards;

  /// POST /enter işlemi sürerken true.
  final bool entering;

  /// Başarılı giriş sonrası true → ekran maça bağlanmayı tetikler.
  final bool entered;

  TournamentState copyWith({
    bool? loading,
    bool? loaded,
    Object? error = _s,
    Object? seasonId = _s,
    int? secondsLeft,
    int? pointMultiplier,
    bool? hardMode,
    Object? description = _s,
    List<TournamentEntryOption>? entryOptions,
    int? gold,
    Object? myRank = _s,
    Object? myScore = _s,
    Object? pointsToNext = _s,
    List<TournamentRewardPreview>? rewards,
    bool? entering,
    bool? entered,
  }) =>
      TournamentState(
        loading: loading ?? this.loading,
        loaded: loaded ?? this.loaded,
        error: identical(error, _s) ? this.error : error as String?,
        seasonId: identical(seasonId, _s) ? this.seasonId : seasonId as String?,
        secondsLeft: secondsLeft ?? this.secondsLeft,
        pointMultiplier: pointMultiplier ?? this.pointMultiplier,
        hardMode: hardMode ?? this.hardMode,
        description:
            identical(description, _s) ? this.description : description as String?,
        entryOptions: entryOptions ?? this.entryOptions,
        gold: gold ?? this.gold,
        myRank: identical(myRank, _s) ? this.myRank : myRank as int?,
        myScore: identical(myScore, _s) ? this.myScore : myScore as int?,
        pointsToNext: identical(pointsToNext, _s)
            ? this.pointsToNext
            : pointsToNext as int?,
        rewards: rewards ?? this.rewards,
        entering: entering ?? this.entering,
        entered: entered ?? this.entered,
      );

  static const Object _s = Object();
}

class TournamentNotifier extends StateNotifier<TournamentState> {
  TournamentNotifier() : super(const TournamentState()) {
    load();
  }

  Timer? _ticker;

  Future<void> load() async {
    state = state.copyWith(loading: true, error: null);
    try {
      final r = await ApiClient.instance.get('/api/tournament');
      state = _applyResponse(r).copyWith(loading: false, loaded: true);
      _startTicker();
    } catch (_) {
      state = state.copyWith(
        loading: false,
        loaded: true,
        error: 'Turnuva bilgisi yüklenemedi.',
      );
    }
  }

  /// Turnuvaya altınla girer. Başarıda [entered]=true olur ve bakiye
  /// güncellenir; çağıran ekran maça bağlanır.
  /// Yetersiz bakiyede (400) hata mesajı state'e yazılır, false döner.
  Future<bool> enter() async {
    if (state.entering) return false;
    state = state.copyWith(entering: true, error: null);
    try {
      final r = await ApiClient.instance
          .post('/api/tournament/enter', body: {'currency': 'gold'});
      state = state.copyWith(
        entering: false,
        entered: true,
        gold: (r['gold'] as num?)?.toInt() ?? state.gold,
      );
      return true;
    } catch (e) {
      state = state.copyWith(entering: false, error: _errorText(e));
      return false;
    }
  }

  /// `entered` bayrağını tüketildikten sonra temizler (tekrar tetiklenmesin).
  void clearEntered() => state = state.copyWith(entered: false);

  void clearError() => state = state.copyWith(error: null);

  void _startTicker() {
    _ticker?.cancel();
    if (state.secondsLeft <= 0) return;
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
      final left = state.secondsLeft - 1;
      if (left <= 0) {
        state = state.copyWith(secondsLeft: 0);
        _ticker?.cancel();
      } else {
        state = state.copyWith(secondsLeft: left);
      }
    });
  }

  TournamentState _applyResponse(Map<String, dynamic> r) {
    final optionsRaw = r['entry_options'] as List? ?? const [];
    final options = optionsRaw
        .whereType<Map<String, dynamic>>()
        .map(TournamentEntryOption.fromJson)
        .toList();

    final rewardsRaw = r['rewards_preview'] as List? ?? const [];
    final rewards = rewardsRaw
        .whereType<Map<String, dynamic>>()
        .map(TournamentRewardPreview.fromJson)
        .toList();

    final balances = r['balances'] as Map<String, dynamic>? ?? const {};
    final myEntry = r['my_entry'] as Map<String, dynamic>?;

    return state.copyWith(
      seasonId: r['season_id']?.toString(),
      secondsLeft: (r['seconds_left'] as num?)?.toInt() ?? 0,
      pointMultiplier: (r['point_multiplier'] as num?)?.toInt() ?? 3,
      hardMode: r['hard_mode'] as bool? ?? true,
      description: r['description']?.toString(),
      entryOptions: options,
      gold: (balances['gold'] as num?)?.toInt() ?? 0,
      myRank: (myEntry?['rank'] as num?)?.toInt(),
      myScore: (myEntry?['score'] as num?)?.toInt(),
      pointsToNext: (myEntry?['points_to_next'] as num?)?.toInt(),
      rewards: rewards,
    );
  }

  String _errorText(Object e) {
    // Backend 400'de Türkçe detail mesajı döndürüyor ("Yetersiz altın." vb.) —
    // varsa onu kullan; yoksa genel mesaj üret.
    if (e is DioException) {
      final data = e.response?.data;
      if (data is Map && data['detail'] != null) {
        return data['detail'].toString();
      }
      if (e.response?.statusCode == 400) {
        return 'Yetersiz altın.';
      }
    }
    return 'Turnuvaya girilemedi, tekrar deneyin.';
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }
}

final tournamentProvider =
    StateNotifierProvider<TournamentNotifier, TournamentState>(
  (_) => TournamentNotifier(),
);
