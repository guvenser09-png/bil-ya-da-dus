import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';

class ResultState {
  const ResultState({
    this.gameResult,
    this.isLoading = false,
    this.error,
    this.friendRequestsSent = const {},
    this.questionRatings = const {},
  });

  final Map<String, dynamic>? gameResult;
  final bool isLoading;
  final String? error;
  // Track which friend requests have been sent (userId set)
  final Set<String> friendRequestsSent;
  // Track question ratings (questionId -> rating 1/-1)
  final Map<String, int> questionRatings;

  ResultState copyWith({
    Map<String, dynamic>? gameResult,
    bool? isLoading,
    String? error,
    bool clearError = false,
    Set<String>? friendRequestsSent,
    Map<String, int>? questionRatings,
  }) {
    return ResultState(
      gameResult: gameResult ?? this.gameResult,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
      friendRequestsSent: friendRequestsSent ?? this.friendRequestsSent,
      questionRatings: questionRatings ?? this.questionRatings,
    );
  }
}

class ResultNotifier extends StateNotifier<ResultState> {
  ResultNotifier() : super(const ResultState());

  void setResult(Map<String, dynamic> result) {
    state = state.copyWith(gameResult: result, clearError: true);
  }

  /// Fetch game result from API by gameId. Skips if data already set (from WS).
  Future<void> fetchResult(String gameId) async {
    if (state.gameResult != null) return;
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final data = await ApiClient.instance.get('/api/games/$gameId/result');
      state = state.copyWith(isLoading: false, gameResult: data);
    } on DioException catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: ApiClient.friendlyError(e),
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Sonuç yüklenemedi.',
      );
    }
  }

  /// Fire-and-forget question rating. rating: 1 = thumbs up, -1 = thumbs down.
  Future<void> submitQuestionRating(String questionId, int rating) async {
    // Optimistically update local state
    final updated = Map<String, int>.from(state.questionRatings);
    updated[questionId] = rating;
    state = state.copyWith(questionRatings: updated);

    try {
      await ApiClient.instance.post(
        '/api/questions/$questionId/vote',
        body: {'vote': rating},
      );
    } catch (_) {
      // Fire and forget — ignore all errors silently
    }
  }

  /// Send a friend request to another player.
  Future<void> addFriend(String userId) async {
    // Optimistically mark as sent
    final updated = Set<String>.from(state.friendRequestsSent);
    updated.add(userId);
    state = state.copyWith(friendRequestsSent: updated);

    try {
      await ApiClient.instance.post(
        '/api/friends/request',
        body: {'user_id': userId},
      );
    } on DioException catch (e) {
      // Revert on error and surface message
      final reverted = Set<String>.from(state.friendRequestsSent);
      reverted.remove(userId);
      state = state.copyWith(
        friendRequestsSent: reverted,
        error: ApiClient.friendlyError(e),
      );
    } catch (_) {
      final reverted = Set<String>.from(state.friendRequestsSent);
      reverted.remove(userId);
      state = state.copyWith(
        friendRequestsSent: reverted,
        error: 'Arkadaşlık isteği gönderilemedi.',
      );
    }
  }

  /// Sonuç ekranından "arkadaş ekle" — elimizde user_id YOK.
  ///
  /// WS game_finished'in final_standings satırları yalnızca username/
  /// display_name taşır (user_id yok). Bu yüzden önce arama ucundan
  /// (`/api/friends/search`) tam eşleşen kullanıcıyı bulup user_id'sini
  /// çözer, sonra isteği göndeririz. Botlar zaten UI'da elenmiş olur
  /// (is_bot == false şartı) — arama yine de bulamazsa sessizce geri alınır.
  ///
  /// [friendRequestsSent] bu akışta USERNAME anahtarıyla kullanılır
  /// (sonuç verisindeki tek kararlı kimlik).
  Future<void> addFriendByUsername(String username) async {
    final key = username.trim();
    if (key.isEmpty || state.friendRequestsSent.contains(key)) return;

    // İyimser işaretle → buton anında "✓ İstek gönderildi"ye döner.
    state = state.copyWith(
      friendRequestsSent: {...state.friendRequestsSent, key},
    );

    try {
      final resp = await ApiClient.instance
          .get('/api/friends/search', query: {'q': key});
      final users = (resp['users'] as List?) ?? const [];
      Map<String, dynamic>? match;
      final lower = key.toLowerCase();
      for (final u in users) {
        if (u is! Map) continue;
        // Sonuç ekranındaki isim username DE display_name DE olabilir
        // (REST top_players display_name'i tercih eder) → ikisine de bak.
        final uname = u['username']?.toString().toLowerCase();
        final dname = u['display_name']?.toString().toLowerCase();
        if (uname == lower || dname == lower) {
          match = Map<String, dynamic>.from(u);
          break;
        }
      }
      final userId = match?['user_id']?.toString();
      if (userId == null || userId.isEmpty) {
        throw Exception('kullanıcı bulunamadı');
      }
      // Zaten arkadaş / istek beklemede ise tekrar POST etmeyiz; buton
      // "gönderildi"de kalır (kullanıcı açısından hedefe ulaşıldı).
      final status = match?['status']?.toString() ?? 'none';
      if (status == 'none' || status == 'incoming') {
        await ApiClient.instance.post(
          '/api/friends/request',
          body: {'user_id': userId},
        );
      }
    } on DioException catch (e) {
      state = state.copyWith(
        friendRequestsSent: {...state.friendRequestsSent}..remove(key),
        error: ApiClient.friendlyError(e),
      );
    } catch (_) {
      state = state.copyWith(
        friendRequestsSent: {...state.friendRequestsSent}..remove(key),
        error: 'Arkadaşlık isteği gönderilemedi.',
      );
    }
  }

  void clearError() => state = state.copyWith(clearError: true);
}

// Computed convenience getters via extension
extension ResultStateX on ResultState {
  Map<String, dynamic>? get result => gameResult;
  bool get isWinner => gameResult?['my_result']?['is_winner'] == true;

  /// Oyuncu maç boyunca HAYATTA mı kaldı (hiç elenmedi mi)?
  ///
  /// KRİTİK ayrım: "elendin" yalnızca gerçekten ELENEN oyuncuya gösterilmeli.
  /// Battle-royale'de bir oyuncu tüm turlara dayanıp yine de şampiyon
  /// olmayabilir (birden çok hayatta kalan → en yüksek skor kazanır). Bu
  /// oyuncu ELENMEDİ; ona "elendin" demek yanlıştı (asıl bug).
  ///
  /// Kaynak önceliği:
  /// 1) my_result.survived bayrağı (varsa, en güvenilir).
  /// 2) eliminated_at_round null/0 → hiç elenmedi.
  /// 3) final_round >= total_rounds → son tura dek dayandı = hayatta.
  /// Kazanan her zaman hayattadır.
  bool get survived {
    final my = gameResult?['my_result'] as Map?;
    if (my == null) return isWinner;
    if (my['survived'] is bool) return my['survived'] as bool;
    final elimRound = my['eliminated_at_round'];
    if (elimRound is num) return elimRound <= 0;
    final finalRound = (my['final_round'] as num?)?.toInt() ?? 0;
    final totalRounds = (my['total_rounds'] as num?)?.toInt() ?? 0;
    if (totalRounds > 0 && finalRound >= totalRounds) return true;
    return isWinner;
  }

  /// Maç özeti — oynanan turların soru/cevap listesi. Backend (WS
  /// `game_finished` veya `/api/games/{id}/result`) `questions` döndürür.
  /// Eski maçlarda / payload eksikse boş liste (savunmacı parse).
  List<Map<String, dynamic>> get questions {
    final raw = gameResult?['questions'];
    if (raw is! List) return const [];
    return raw
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
  }
}

// DİKKAT: BİLEREK autoDispose DEĞİL.
// Sonuç verisi (game_finished payload'u) GameScreen'de, ResultScreen daha
// MOUNT olmadan ÖNCE `ref.read(resultProvider(gameId).notifier).setResult(...)`
// ile doldurulur (WS hızlı yolu). autoDispose yapılırsa o anda provider'ı
// dinleyen olmadığı için notifier hemen dispose edilir ve WS'den gelen sonuç
// KAYBOLUR → ResultScreen boş/yanlış açılır. family olduğu için her gameId
// ayrı tutulur; gameId path'e gömülü olduğundan eski sonuçlar çakışmaz.
final resultProvider = StateNotifierProvider.family<ResultNotifier, ResultState, String>(
  (_, __) => ResultNotifier(),
);
