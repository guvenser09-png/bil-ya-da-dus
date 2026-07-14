import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';

/// Günlük 3 Görev — her gün TRT gece yarısı sıfırlanır.
///
/// Backend uçları:
/// - `GET  /api/quests/today`        → 3 görev + ilerleme + ödül durumu
/// - `POST /api/quests/{id}/claim`   → tamamlanan görevin altınını al (idempotent)
class Quest {
  const Quest({
    required this.id,
    required this.title,
    required this.emoji,
    required this.target,
    required this.reward,
    required this.progress,
    required this.completed,
    required this.claimed,
    required this.claimable,
  });

  final String id;
  final String title;
  final String emoji;

  /// İlerleme hedefi (ör. "3 maç oyna" → 3).
  final int target;

  /// Tamamlanınca alınabilecek altın.
  final int reward;

  /// Mevcut ilerleme (0..target).
  final int progress;

  final bool completed;

  /// Ödül alındı mı?
  final bool claimed;

  /// "AL" butonu aktif mi? (tamamlandı ve henüz alınmadı)
  final bool claimable;

  factory Quest.fromJson(Map<String, dynamic> j) => Quest(
        id: (j['id'] ?? '').toString(),
        title: (j['title'] ?? '').toString(),
        emoji: (j['emoji'] ?? '🎯').toString(),
        target: (j['target'] as num?)?.toInt() ?? 1,
        reward: (j['reward'] as num?)?.toInt() ?? 0,
        progress: (j['progress'] as num?)?.toInt() ?? 0,
        completed: j['completed'] as bool? ?? false,
        claimed: j['claimed'] as bool? ?? false,
        claimable: j['claimable'] as bool? ?? false,
      );

  /// 0..1 — ilerleme çubuğu için.
  double get ratio => target <= 0 ? 0 : (progress / target).clamp(0.0, 1.0);
}

class QuestsState {
  const QuestsState({
    this.quests = const [],
    this.loading = false,
    this.loaded = false,
    this.claimingId,
    this.error,
  });

  final List<Quest> quests;
  final bool loading;
  final bool loaded;

  /// Şu an ödülü alınmakta olan görevin id'si (çift dokunuşu engeller).
  final String? claimingId;

  final String? error;

  /// Kaç görevin ödülü alınmayı bekliyor? (kartta kırmızı rozet)
  int get claimableCount => quests.where((q) => q.claimable).length;
  int get completedCount => quests.where((q) => q.completed).length;

  QuestsState copyWith({
    List<Quest>? quests,
    bool? loading,
    bool? loaded,
    Object? claimingId = _sentinel,
    Object? error = _sentinel,
  }) =>
      QuestsState(
        quests: quests ?? this.quests,
        loading: loading ?? this.loading,
        loaded: loaded ?? this.loaded,
        claimingId:
            identical(claimingId, _sentinel) ? this.claimingId : claimingId as String?,
        error: identical(error, _sentinel) ? this.error : error as String?,
      );

  static const Object _sentinel = Object();
}

class QuestsNotifier extends StateNotifier<QuestsState> {
  QuestsNotifier() : super(const QuestsState());

  Future<void> load() async {
    if (state.loading) return;
    state = state.copyWith(loading: true, error: null);
    try {
      final r = await ApiClient.instance.get('/api/quests/today');
      final list = ((r['quests'] as List?) ?? const [])
          .map((e) => Quest.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
      state = state.copyWith(loading: false, loaded: true, quests: list);
    } catch (_) {
      // Sessizce geç: kart gizlenir, ana ekran akışı bozulmaz.
      state = state.copyWith(loading: false, loaded: true, error: 'Görevler yüklenemedi');
    }
  }

  /// Görevin altınını alır. Sunucu idempotenttir (ikinci kez altın vermez).
  ///
  /// Returns: kazanılan altın (0 → alınamadı/zaten alınmış).
  Future<int> claim(String questId) async {
    if (state.claimingId != null) return 0;
    state = state.copyWith(claimingId: questId, error: null);
    try {
      final r = await ApiClient.instance.post('/api/quests/$questId/claim');
      final claimed = r['claimed'] as bool? ?? false;
      final reward = (r['reward'] as num?)?.toInt() ?? 0;
      state = state.copyWith(claimingId: null);
      // Durumu sunucudan tazele (tek gerçek kaynak).
      await load();
      return claimed ? reward : 0;
    } catch (_) {
      state = state.copyWith(claimingId: null, error: 'Ödül alınamadı');
      return 0;
    }
  }
}

final questsProvider =
    StateNotifierProvider<QuestsNotifier, QuestsState>((_) => QuestsNotifier());
