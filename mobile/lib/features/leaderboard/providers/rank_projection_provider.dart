import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';

/// "Bu puanla kaçıncı olurdun?" — misafirin GÖRÜNMEYEN sırası.
///
/// Misafirler liderlik tablolarında gizli olduğundan puanları birikir ama
/// hiçbir yerde görünmez. Backend (GET /api/leaderboard/projection) bu kaybı
/// somut bir sayıya çevirir: "bu puanla bugün 7. sıradaydın".
class RankProjection {
  const RankProjection({
    required this.period,
    required this.score,
    required this.wouldBeRank,
    required this.rankedTotal,
  });

  factory RankProjection.fromJson(Map<String, dynamic> json) => RankProjection(
        period: json['period'] as String? ?? 'daily',
        score: (json['score'] as num?)?.toInt() ?? 0,
        wouldBeRank: (json['would_be_rank'] as num?)?.toInt(),
        rankedTotal: (json['ranked_total'] as num?)?.toInt() ?? 0,
      );

  final String period;

  /// Tahminde kullanılan puan (dönem puanı; 0 ise tahmin üretilmez).
  final int score;

  /// Sıralamaya girseydi kaçıncı olurdu. null → tahmin yok (puan 0, Redis
  /// erişilemedi vb.) → ekranlar sade davet metnine düşer.
  final int? wouldBeRank;

  /// O dönemde sıralamada görünen oyuncu sayısı (bağlam metni için).
  final int rankedTotal;

  bool get hasRank => wouldBeRank != null && wouldBeRank! > 0;
}

/// Dönem: 'daily' | 'weekly' | 'all_time'. Hata olursa null döner — sıra
/// tahmini bir SÜS'tür; yoksa davet sade metinle gösterilir, akış bozulmaz.
final rankProjectionProvider =
    FutureProvider.autoDispose.family<RankProjection?, String>((ref, period) async {
  try {
    final data = await ApiClient.instance
        .get('/api/leaderboard/projection', query: {'period': period});
    return RankProjection.fromJson(data);
  } catch (_) {
    return null;
  }
});
