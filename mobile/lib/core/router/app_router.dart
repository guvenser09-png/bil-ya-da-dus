import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/storage/secure_storage.dart';
import 'package:quizroyale/features/auth/screens/splash_screen.dart';
import 'package:quizroyale/features/auth/screens/onboarding_screen.dart';
import 'package:quizroyale/features/auth/screens/login_screen.dart';
import 'package:quizroyale/features/auth/screens/register_screen.dart';
import 'package:quizroyale/features/auth/screens/forgot_password_screen.dart';
import 'package:quizroyale/features/auth/screens/reset_password_screen.dart';
import 'package:quizroyale/features/account/screens/account_settings_screen.dart';
import 'package:quizroyale/features/legal/screens/legal_viewer_screen.dart';
import 'package:quizroyale/features/cosmetics/screens/cosmetics_screen.dart';
import 'package:quizroyale/features/room/screens/room_entry_screen.dart';
import 'package:quizroyale/features/room/screens/room_screen.dart';
import 'package:quizroyale/features/season/screens/season_screen.dart';
import 'package:quizroyale/features/tournament/screens/tournament_screen.dart';
import 'package:quizroyale/features/inventory/screens/inventory_screen.dart';
import 'package:quizroyale/features/home/screens/home_screen.dart';
import 'package:quizroyale/features/lobby/screens/lobby_screen.dart';
import 'package:quizroyale/features/game/screens/game_screen.dart';
import 'package:quizroyale/features/result/screens/result_screen.dart';
import 'package:quizroyale/features/leaderboard/screens/leaderboard_screen.dart';
import 'package:quizroyale/features/profile/screens/profile_screen.dart';
import 'package:quizroyale/features/profile/screens/edit_profile_screen.dart';
import 'package:quizroyale/features/friends/screens/friends_screen.dart';
import 'package:quizroyale/features/settings/screens/settings_screen.dart';
import 'package:quizroyale/features/store/screens/store_screen.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>();
final _shellNavigatorKey = GlobalKey<NavigatorState>();

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/',
    redirect: (context, state) async {
      bool isLoggedIn = false;
      try {
        isLoggedIn = await SecureStorage.instance.isLoggedIn();
      } catch (_) {}

      final loc = state.matchedLocation;
      final isAuthRoute = loc == '/login' || loc == '/register' ||
          loc == '/' || loc == '/onboarding' ||
          loc == '/forgot-password' || loc == '/reset-password' ||
          loc == '/legal/privacy' || loc == '/legal/terms';

      if (!isLoggedIn && !isAuthRoute) return '/login';
      return null;
    },
    routes: [
      GoRoute(path: '/', builder: (_, __) => const SplashScreen()),
      GoRoute(path: '/onboarding', builder: (_, __) => const OnboardingScreen()),
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
      GoRoute(path: '/register', builder: (_, __) => const RegisterScreen()),
      GoRoute(path: '/forgot-password', builder: (_, __) => const ForgotPasswordScreen()),
      GoRoute(
        path: '/reset-password',
        builder: (_, state) => ResetPasswordScreen(initialToken: state.extra as String?),
      ),

      // Shell with bottom nav
      ShellRoute(
        navigatorKey: _shellNavigatorKey,
        builder: (context, state, child) => AppShell(child: child),
        routes: [
          GoRoute(path: '/home', builder: (_, __) => const HomeScreen()),
          GoRoute(path: '/leaderboard', builder: (_, __) => const LeaderboardScreen()),
          GoRoute(path: '/store', builder: (_, __) => const StoreScreen()),
          GoRoute(path: '/profile', builder: (_, __) => const ProfileScreen()),
        ],
      ),

      // Full-screen routes (outside shell)
      GoRoute(path: '/friends', builder: (_, __) => const FriendsScreen()),
      GoRoute(
        path: '/lobby',
        // extra olarak mode iletilebilir (ör. "tournament"); yoksa normal maç.
        builder: (_, state) => LobbyScreen(mode: state.extra as String?),
      ),
      GoRoute(
        path: '/game/:gameId',
        builder: (_, state) => GameScreen(gameId: state.pathParameters['gameId']!),
      ),
      GoRoute(
        path: '/result/:gameId',
        builder: (_, state) => ResultScreen(gameId: state.pathParameters['gameId']!),
      ),
      GoRoute(path: '/edit-profile', builder: (_, __) => const EditProfileScreen()),
      GoRoute(path: '/settings', builder: (_, __) => const SettingsScreen()),
      GoRoute(path: '/account-settings', builder: (_, __) => const AccountSettingsScreen()),
      GoRoute(path: '/cosmetics', builder: (_, __) => const CosmeticsScreen()),
      GoRoute(path: '/room', builder: (_, __) => const RoomEntryScreen()),
      GoRoute(path: '/room/lobby', builder: (_, __) => const RoomScreen()),
      GoRoute(path: '/season', builder: (_, __) => const SeasonScreen()),
      GoRoute(path: '/tournament', builder: (_, __) => const TournamentScreen()),
      GoRoute(path: '/inventory', builder: (_, __) => const InventoryScreen()),
      GoRoute(
        path: '/legal/privacy',
        builder: (_, __) => const LegalViewerScreen(
            assetPath: 'assets/legal/privacy_policy.md', title: 'Gizlilik Politikası'),
      ),
      GoRoute(
        path: '/legal/terms',
        builder: (_, __) => const LegalViewerScreen(
            assetPath: 'assets/legal/terms_of_service.md', title: 'Kullanım Şartları'),
      ),
    ],
  );
});

class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.child});
  final Widget child;

  static const _tabs = ['/home', '/leaderboard', '/store', '/profile'];

  int _indexFor(String location) {
    final i = _tabs.indexWhere((t) => location.startsWith(t));
    return i < 0 ? 0 : i;
  }

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;
    final index = _indexFor(location);
    return Scaffold(
      extendBody: true,
      body: child,
      bottomNavigationBar: BiladaBottomNav(
        currentIndex: index,
        onTap: (i) => context.go(_tabs[i]),
      ),
    );
  }
}
