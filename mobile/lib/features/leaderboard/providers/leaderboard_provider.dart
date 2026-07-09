import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';

enum LeaderboardTab { daily, weekly, allTime, friends, season }

class LeaderboardState {
  const LeaderboardState({
    this.tab = LeaderboardTab.daily,
    this.entries = const [],
    this.myEntry,
    this.isLoading = false,
    this.error,
    this.seasonDaysLeft = 0,
    this.seasonSecondsLeft = 0,
    this.guestHidden = false,
  });

  final LeaderboardTab tab;
  final List<Map<String, dynamic>> entries;
  final Map<String, dynamic>? myEntry;
  final bool isLoading;
  final String? error;
  final int seasonDaysLeft;

  /// Sezon sekmesi için bitime kalan saniye (GET /api/leaderboard/season).
  final int seasonSecondsLeft;

  /// Backend guest_hidden=true döndürdü: misafir kullanıcı sıralamada
  /// LİSTELENMEZ ve my_entry gelmez — ekran "hesabını kaydet" daveti gösterir.
  final bool guestHidden;

  LeaderboardState copyWith({
    LeaderboardTab? tab,
    List<Map<String, dynamic>>? entries,
    Map<String, dynamic>? myEntry,
    bool clearMyEntry = false,
    bool? isLoading,
    String? error,
    int? seasonDaysLeft,
    int? seasonSecondsLeft,
    bool? guestHidden,
  }) => LeaderboardState(
    tab: tab ?? this.tab,
    entries: entries ?? this.entries,
    myEntry: clearMyEntry ? null : (myEntry ?? this.myEntry),
    isLoading: isLoading ?? this.isLoading,
    error: error,
    seasonDaysLeft: seasonDaysLeft ?? this.seasonDaysLeft,
    seasonSecondsLeft: seasonSecondsLeft ?? this.seasonSecondsLeft,
    guestHidden: guestHidden ?? this.guestHidden,
  );
}

class LeaderboardNotifier extends StateNotifier<LeaderboardState> {
  LeaderboardNotifier() : super(const LeaderboardState()) {
    load(LeaderboardTab.daily);
  }

  Future<void> load(LeaderboardTab tab) async {
    state = state.copyWith(tab: tab, isLoading: true, error: null);
    try {
      final typeMap = {
        LeaderboardTab.daily: 'daily',
        LeaderboardTab.weekly: 'weekly',
        LeaderboardTab.allTime: 'all_time',
        LeaderboardTab.friends: 'friends',
        LeaderboardTab.season: 'season',
      };
      final data = await ApiClient.instance
          .get('/api/leaderboard/${typeMap[tab]}', query: {'limit': 50});
      final rawEntries = (data['entries'] as List? ?? [])
          .whereType<Map<String, dynamic>>()
          .toList();
      final myEntry = data['my_entry'] as Map<String, dynamic>?;
      state = state.copyWith(
        isLoading: false,
        entries: rawEntries,
        myEntry: myEntry,
        clearMyEntry: myEntry == null,
        seasonDaysLeft: (data['season_days_left'] as num?)?.toInt() ?? 0,
        seasonSecondsLeft: (data['seconds_left'] as num?)?.toInt() ?? 0,
        // Misafir: my_entry yerine kayıt daveti kartı gösterilir.
        guestHidden: data['guest_hidden'] == true,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: 'Yüklenemedi');
    }
  }
}

final leaderboardProvider = StateNotifierProvider<LeaderboardNotifier, LeaderboardState>(
  (_) => LeaderboardNotifier(),
);
