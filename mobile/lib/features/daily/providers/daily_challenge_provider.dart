import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';

/// Günün 5 Sorusu — herkese AYNI 5 soru, günde bir kez, eleme YOK.
///
/// Backend uçları:
/// - `GET  /api/games/daily-challenge/status` → oynandı mı + seri + sonuç
/// - `GET  /api/games/daily-challenge`        → bugünün 5 sorusu (403: oynandı)
/// - `POST /api/games/daily-challenge/score`  → cevapları gönder, coin + sonuç al
class DailyChallengeResult {
  const DailyChallengeResult({
    required this.correctCount,
    required this.questionCount,
    required this.results,
    required this.coinsEarned,
    required this.rank,
    required this.totalPlayers,
    required this.percentile,
    required this.streak,
    required this.shareText,
    required this.score,
  });

  /// Kaç doğru (0-5).
  final int correctCount;
  final int questionCount;

  /// Soru sırasıyla doğru/yanlış — 🟩🟥 ızgarası bundan çizilir.
  final List<bool> results;

  /// Bu turdan kazanılan altın (taban 100 + doğru başına 20, maks 200).
  final int coinsEarned;

  /// Günün sıralamasındaki yer + toplam oyuncu + "en iyi %X".
  final int rank;
  final int totalPlayers;
  final int percentile;

  /// Kaç gün üst üste oynandı.
  final int streak;

  /// Paylaşım kartının hazır metni (sunucu üretir, cevap SIZDIRMAZ).
  final String shareText;

  final int score;

  factory DailyChallengeResult.fromJson(Map<String, dynamic> j) {
    return DailyChallengeResult(
      correctCount: (j['correct_count'] as num?)?.toInt() ?? 0,
      questionCount: (j['question_count'] as num?)?.toInt() ?? 5,
      results: ((j['results'] as List?) ?? const [])
          .map((e) => e == true)
          .toList(growable: false),
      coinsEarned: (j['coins_earned'] as num?)?.toInt() ?? 0,
      rank: (j['rank'] as num?)?.toInt() ?? 0,
      totalPlayers: (j['total_players'] as num?)?.toInt() ?? 0,
      percentile: (j['percentile'] as num?)?.toInt() ?? 0,
      streak: (j['streak'] as num?)?.toInt() ?? 0,
      shareText: (j['share_text'] as String?) ?? '',
      score: (j['score'] as num?)?.toInt() ?? 0,
    );
  }

  /// 🟩🟩🟥🟩🟥 — sonuç ekranındaki ızgara ve paylaşım metni aynı diziden.
  String get grid => results.map((ok) => ok ? '🟩' : '🟥').join();
}

class DailyChallengeState {
  const DailyChallengeState({
    this.loading = false,
    this.loaded = false,
    this.playedToday = false,
    this.streak = 0,
    this.maxReward = 200,
    this.result,
    this.error,
  });

  final bool loading;

  /// İlk yükleme bitti mi? (kartı erken/yanlış göstermemek için)
  final bool loaded;

  /// Bugün oynandı mı? (true → kart sonucu gösterir, "yarın tekrar gel")
  final bool playedToday;
  final int streak;
  final int maxReward;

  /// Bugün oynandıysa sonucu (48 saat sunucuda saklanır).
  final DailyChallengeResult? result;

  final String? error;

  DailyChallengeState copyWith({
    bool? loading,
    bool? loaded,
    bool? playedToday,
    int? streak,
    int? maxReward,
    DailyChallengeResult? result,
    Object? error = _sentinel,
  }) =>
      DailyChallengeState(
        loading: loading ?? this.loading,
        loaded: loaded ?? this.loaded,
        playedToday: playedToday ?? this.playedToday,
        streak: streak ?? this.streak,
        maxReward: maxReward ?? this.maxReward,
        result: result ?? this.result,
        error: identical(error, _sentinel) ? this.error : error as String?,
      );

  static const Object _sentinel = Object();
}

class DailyChallengeNotifier extends StateNotifier<DailyChallengeState> {
  DailyChallengeNotifier() : super(const DailyChallengeState());

  /// Ana ekran kartı için durum çeker (açılışta home_screen çağırır).
  Future<void> load() async {
    if (state.loading) return;
    state = state.copyWith(loading: true, error: null);
    try {
      final r = await ApiClient.instance.get('/api/games/daily-challenge/status');
      final raw = r['result'];
      state = state.copyWith(
        loading: false,
        loaded: true,
        playedToday: r['played_today'] as bool? ?? false,
        streak: (r['streak'] as num?)?.toInt() ?? 0,
        maxReward: (r['max_reward'] as num?)?.toInt() ?? 200,
        result: raw is Map<String, dynamic>
            ? DailyChallengeResult.fromJson(raw)
            : null,
      );
    } catch (_) {
      // Sessizce geç: kart "yüklenemedi" durumuna düşer, akış bozulmaz.
      state = state.copyWith(loading: false, loaded: true, error: 'Günün soruları yüklenemedi');
    }
  }

  /// Bugünün 5 sorusunu getirir. Zaten oynandıysa (403) null döner.
  Future<List<Map<String, dynamic>>?> fetchQuestions() async {
    try {
      final r = await ApiClient.instance.get('/api/games/daily-challenge');
      final list = (r['questions'] as List?) ?? const [];
      return list.cast<Map<String, dynamic>>();
    } catch (_) {
      return null;
    }
  }

  /// Cevapları gönderir; sunucu değerlendirir, coin verir, sonucu döner.
  ///
  /// [answers]: soru sırasıyla cevaplar (şıklarda index, tahminde sayı; boş → null).
  /// [score]: istemcinin hız bonuslu skoru (sıralama için; doğruluk sunucuda).
  Future<DailyChallengeResult?> submit({
    required List<dynamic> answers,
    required int score,
  }) async {
    try {
      final r = await ApiClient.instance.post(
        '/api/games/daily-challenge/score',
        body: {'score': score, 'answers': answers},
      );
      final result = DailyChallengeResult.fromJson(r);
      state = state.copyWith(
        playedToday: true,
        streak: result.streak,
        result: result,
        loaded: true,
      );
      return result;
    } catch (_) {
      state = state.copyWith(error: 'Sonuç gönderilemedi');
      return null;
    }
  }
}

final dailyChallengeProvider =
    StateNotifierProvider<DailyChallengeNotifier, DailyChallengeState>(
  (_) => DailyChallengeNotifier(),
);
