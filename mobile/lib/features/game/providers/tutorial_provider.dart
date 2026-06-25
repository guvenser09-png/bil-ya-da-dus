import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// İlk-maç mini tutorial durumu.
///
/// `tutorial_seen` bayrağı SharedPreferences'ta tutulur. İlk maç boyunca her
/// YENİ tur tipi ilk kez geldiğinde kısa bir ipucu balonu gösterilir; maç
/// bitince (veya kullanıcı yeterince ipucu gördükten sonra) bayrak true olur ve
/// bir daha hiçbir ipucu gösterilmez.
class TutorialState {
  const TutorialState({
    this.seen = true, // güvenli varsayılan: yükleninceye kadar gösterme
    this.loaded = false,
    this.shownTypes = const <String>{},
  });

  /// Tutorial daha önce tamamlandı/görüldü mü (kalıcı bayrak).
  final bool seen;

  /// SharedPreferences'tan bayrak okundu mu.
  final bool loaded;

  /// Bu maç oturumunda ipucu gösterilmiş tur tipleri (tekrar gösterme).
  final Set<String> shownTypes;

  bool get active => loaded && !seen;

  TutorialState copyWith({
    bool? seen,
    bool? loaded,
    Set<String>? shownTypes,
  }) =>
      TutorialState(
        seen: seen ?? this.seen,
        loaded: loaded ?? this.loaded,
        shownTypes: shownTypes ?? this.shownTypes,
      );
}

class TutorialNotifier extends StateNotifier<TutorialState> {
  TutorialNotifier() : super(const TutorialState()) {
    _load();
  }

  static const _key = 'tutorial_seen';

  Future<void> _load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final seen = prefs.getBool(_key) ?? false;
      state = state.copyWith(seen: seen, loaded: true);
    } catch (_) {
      // Okunamazsa güvenli tarafta kal: gösterme.
      state = state.copyWith(seen: true, loaded: true);
    }
  }

  /// Verilen tur tipi için ipucu gösterilmeli mi? (tutorial aktif + bu tip
  /// bu oturumda daha önce gösterilmedi). Gösterilecekse tipi işaretler.
  bool shouldShow(String type) {
    if (!state.active || type.isEmpty) return false;
    if (state.shownTypes.contains(type)) return false;
    state = state.copyWith(shownTypes: {...state.shownTypes, type});
    return true;
  }

  /// Maç bitince çağrılır — bayrağı kalıcı olarak true yapar.
  Future<void> markSeen() async {
    if (state.seen) return;
    state = state.copyWith(seen: true);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_key, true);
    } catch (_) {
      // Yazılamazsa sessizce geç; en kötü ihtimalle bir maç daha gösterilir.
    }
  }
}

final tutorialProvider =
    StateNotifierProvider<TutorialNotifier, TutorialState>(
        (_) => TutorialNotifier());
