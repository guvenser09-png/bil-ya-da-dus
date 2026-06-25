import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/friends/providers/friends_provider.dart';
import 'package:quizroyale/features/room/providers/room_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/player_avatar.dart';
import 'package:quizroyale/shared/widgets/profile_bottom_sheet.dart';

/// Arkadaşlar ekranı — 3 sekme: Arkadaşlar / İstekler / Ara.
/// Stitch tasarımı (BiladaBackground, GlassCard, ChunkyButton, geri butonu).
class FriendsScreen extends ConsumerStatefulWidget {
  const FriendsScreen({super.key});

  @override
  ConsumerState<FriendsScreen> createState() => _FriendsScreenState();
}

class _FriendsScreenState extends ConsumerState<FriendsScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tab = TabController(length: 3, vsync: this);

  @override
  void dispose() {
    _tab.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(friendsProvider);

    return Scaffold(
      body: Stack(
        children: [
          const Positioned.fill(child: BiladaBackground(showFloaters: false)),
          SafeArea(
            child: Column(
              children: [
                // Üst çubuk: geri butonu + başlık.
                Padding(
                  padding: const EdgeInsets.fromLTRB(8, 8, 16, 4),
                  child: Row(
                    children: [
                      IconButton(
                        icon: const Icon(Icons.arrow_back_rounded,
                            color: AppTheme.cOnSurface),
                        onPressed: () => context.go('/home'),
                      ),
                      Text('Arkadaşlar', style: BiladaText.headline(size: 24)),
                    ],
                  ),
                ),
                _Tabs(
                  controller: _tab,
                  incomingCount: state.incoming.length,
                ),
                Expanded(
                  child: TabBarView(
                    controller: _tab,
                    children: const [
                      _FriendsTab(),
                      _RequestsTab(),
                      _SearchTab(),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Sekme başlıkları — İstekler sekmesinde bekleyen istek rozeti.
class _Tabs extends StatelessWidget {
  const _Tabs({required this.controller, required this.incomingCount});
  final TabController controller;
  final int incomingCount;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: TabBar(
        controller: controller,
        labelColor: AppTheme.cPrimary,
        unselectedLabelColor: AppTheme.cOnSurfaceVariant,
        indicatorColor: AppTheme.cPrimary,
        indicatorSize: TabBarIndicatorSize.label,
        labelStyle: BiladaText.label(color: AppTheme.cPrimary, size: 13),
        unselectedLabelStyle:
            BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 13),
        tabs: [
          const Tab(text: 'Arkadaşlar'),
          Tab(
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('İstekler'),
                if (incomingCount > 0) ...[
                  const SizedBox(width: 6),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppTheme.cPrimaryContainer,
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      '$incomingCount',
                      style: BiladaText.label(
                          color: AppTheme.cOnPrimaryContainer, size: 11),
                    ),
                  ),
                ],
              ],
            ),
          ),
          const Tab(text: 'Ara'),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Sekme 1: Arkadaşlar
// ---------------------------------------------------------------------------

class _FriendsTab extends ConsumerWidget {
  const _FriendsTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(friendsProvider);

    if (state.isLoading && state.friends.isEmpty) {
      return const Center(
          child: CircularProgressIndicator(color: AppTheme.cPrimaryContainer));
    }

    if (state.friends.isEmpty) {
      return const _EmptyState(
        icon: Icons.group_outlined,
        message: 'Henüz arkadaşın yok.\nArama sekmesinden arkadaş ekleyebilirsin!',
      );
    }

    return RefreshIndicator(
      onRefresh: () => ref.read(friendsProvider.notifier).loadFriends(),
      color: AppTheme.cPrimaryContainer,
      backgroundColor: AppTheme.cSurfaceContainerHigh,
      child: ListView.builder(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
        itemCount: state.friends.length,
        itemBuilder: (_, i) => _FriendTile(friend: state.friends[i]),
      ),
    );
  }
}

class _FriendTile extends ConsumerWidget {
  const _FriendTile({required this.friend});
  final Map<String, dynamic> friend;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final username = friend['username'] as String? ?? '';
    final displayName = friend['display_name'] as String? ?? username;
    final userId = friend['user_id'] as String? ?? '';
    final avatarId = friend['avatar_id'] as String? ?? 'default_01';
    final level = friend['level'] as int? ?? 1;

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: GlassCard(
        onTap: () => showProfileSheet(context, username: username),
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            PlayerAvatar(avatarId: avatarId, username: username, size: 44),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(displayName, style: BiladaText.title(size: 14)),
                  Text('Seviye $level',
                      style:
                          BiladaText.label(color: AppTheme.cPrimary, size: 11)),
                ],
              ),
            ),
            IconButton(
              tooltip: 'Düelloya çağır',
              onPressed: () => _inviteToDuel(context, ref, displayName),
              icon: const Icon(Icons.sports_esports_rounded,
                  color: AppTheme.cPrimary, size: 26),
            ),
            IconButton(
              tooltip: 'Arkadaşlıktan çıkar',
              onPressed: () => _confirmRemove(context, ref, userId, displayName),
              icon: const Icon(Icons.person_remove_rounded,
                  color: AppTheme.cError, size: 24),
            ),
          ],
        ),
      ),
    );
  }

  /// Arkadaşı düelloya çağır: host olarak yeni bir oda aç ve lobiye geç.
  /// Otomatik bildirim yok — akış: oda aç → kodu arkadaşına gönder → katılsın.
  void _inviteToDuel(BuildContext context, WidgetRef ref, String name) {
    ref.read(roomProvider.notifier).createRoom();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Oda açılıyor — kodu $name ile paylaş!'),
        backgroundColor: AppTheme.cTertiary,
        duration: const Duration(seconds: 2),
      ),
    );
    context.go('/room/lobby');
  }

  Future<void> _confirmRemove(
      BuildContext context, WidgetRef ref, String userId, String name) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.cSurfaceContainerHigh,
        title: Text('Arkadaşlıktan çıkar', style: BiladaText.title(size: 18)),
        content: Text('$name arkadaş listenden çıkarılsın mı?',
            style: BiladaText.body(size: 14)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text('Vazgeç',
                style: BiladaText.label(color: AppTheme.cOnSurfaceVariant)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child:
                Text('Çıkar', style: BiladaText.label(color: AppTheme.cError)),
          ),
        ],
      ),
    );
    if (ok == true) {
      await ref.read(friendsProvider.notifier).removeFriend(userId);
    }
  }
}

// ---------------------------------------------------------------------------
// Sekme 2: İstekler (gelen + giden)
// ---------------------------------------------------------------------------

class _RequestsTab extends ConsumerWidget {
  const _RequestsTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(friendsProvider);

    if (state.incoming.isEmpty && state.outgoing.isEmpty) {
      return const _EmptyState(
        icon: Icons.mail_outline_rounded,
        message: 'Bekleyen istek yok.',
      );
    }

    return RefreshIndicator(
      onRefresh: () => ref.read(friendsProvider.notifier).loadRequests(),
      color: AppTheme.cPrimaryContainer,
      backgroundColor: AppTheme.cSurfaceContainerHigh,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
        children: [
          if (state.incoming.isNotEmpty) ...[
            _sectionHeader('GELEN İSTEKLER'),
            for (final r in state.incoming) _IncomingTile(request: r),
          ],
          if (state.outgoing.isNotEmpty) ...[
            _sectionHeader('GÖNDERİLEN İSTEKLER'),
            for (final r in state.outgoing) _OutgoingTile(request: r),
          ],
        ],
      ),
    );
  }

  Widget _sectionHeader(String label) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 8, 4, 10),
        child: Text(label, style: BiladaText.label(color: AppTheme.cPrimary)),
      );
}

class _IncomingTile extends ConsumerWidget {
  const _IncomingTile({required this.request});
  final Map<String, dynamic> request;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final username = request['username'] as String? ?? '';
    final displayName = request['display_name'] as String? ?? username;
    final userId = request['user_id'] as String? ?? '';
    final avatarId = request['avatar_id'] as String? ?? 'default_01';

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: GlassCard(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            PlayerAvatar(avatarId: avatarId, username: username, size: 40),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(displayName, style: BiladaText.title(size: 14)),
                  Text('arkadaşlık isteği gönderdi',
                      style:
                          BiladaText.label(color: AppTheme.cOutline, size: 11)),
                ],
              ),
            ),
            IconButton(
              tooltip: 'Kabul et',
              onPressed: () =>
                  ref.read(friendsProvider.notifier).accept(userId),
              icon: const Icon(Icons.check_circle_rounded,
                  color: AppTheme.cTertiary, size: 30),
              padding: EdgeInsets.zero,
            ),
            IconButton(
              tooltip: 'Reddet',
              onPressed: () =>
                  ref.read(friendsProvider.notifier).reject(userId),
              icon: const Icon(Icons.cancel_rounded,
                  color: AppTheme.cError, size: 30),
              padding: EdgeInsets.zero,
            ),
          ],
        ),
      ),
    );
  }
}

class _OutgoingTile extends StatelessWidget {
  const _OutgoingTile({required this.request});
  final Map<String, dynamic> request;

  @override
  Widget build(BuildContext context) {
    final username = request['username'] as String? ?? '';
    final displayName = request['display_name'] as String? ?? username;
    final avatarId = request['avatar_id'] as String? ?? 'default_01';

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: GlassCard(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            PlayerAvatar(avatarId: avatarId, username: username, size: 40),
            const SizedBox(width: 12),
            Expanded(child: Text(displayName, style: BiladaText.title(size: 14))),
            Text('Bekliyor',
                style: BiladaText.label(color: AppTheme.cOutline, size: 12)),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Sekme 3: Ara
// ---------------------------------------------------------------------------

class _SearchTab extends ConsumerStatefulWidget {
  const _SearchTab();

  @override
  ConsumerState<_SearchTab> createState() => _SearchTabState();
}

class _SearchTabState extends ConsumerState<_SearchTab> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(friendsProvider);

    return Column(
      children: [
        // Arama kutusu.
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
          child: GlassCard(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
            child: Row(
              children: [
                const Icon(Icons.search_rounded,
                    color: AppTheme.cOnSurfaceVariant),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: _controller,
                    style: BiladaText.body(),
                    decoration: const InputDecoration(
                      hintText: 'Kullanıcı adı ara...',
                      border: InputBorder.none,
                      filled: false,
                      isCollapsed: true,
                      contentPadding: EdgeInsets.symmetric(vertical: 16),
                    ),
                    textInputAction: TextInputAction.search,
                    onChanged: (q) =>
                        ref.read(friendsProvider.notifier).search(q),
                  ),
                ),
                if (_controller.text.isNotEmpty)
                  IconButton(
                    icon: const Icon(Icons.close_rounded,
                        color: AppTheme.cOnSurfaceVariant, size: 20),
                    onPressed: () {
                      _controller.clear();
                      ref.read(friendsProvider.notifier).search('');
                      setState(() {});
                    },
                  ),
              ],
            ),
          ),
        ),
        Expanded(child: _buildResults(state)),
      ],
    );
  }

  Widget _buildResults(FriendsState state) {
    if (state.isSearching) {
      return const Center(
          child: CircularProgressIndicator(color: AppTheme.cPrimaryContainer));
    }
    if (_controller.text.trim().length < 2) {
      return const _EmptyState(
        icon: Icons.person_search_outlined,
        message: 'Arkadaş eklemek için\nkullanıcı adı yaz (en az 2 harf).',
      );
    }
    if (state.searchResults.isEmpty) {
      return const _EmptyState(
        icon: Icons.search_off_rounded,
        message: 'Kullanıcı bulunamadı.',
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(20, 4, 20, 32),
      itemCount: state.searchResults.length,
      itemBuilder: (_, i) => _SearchTile(user: state.searchResults[i]),
    );
  }
}

class _SearchTile extends ConsumerWidget {
  const _SearchTile({required this.user});
  final Map<String, dynamic> user;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final username = user['username'] as String? ?? '';
    final displayName = user['display_name'] as String? ?? username;
    final userId = user['user_id'] as String? ?? '';
    final avatarId = user['avatar_id'] as String? ?? 'default_01';
    final status = user['status'] as String? ?? 'none';
    final notifier = ref.read(friendsProvider.notifier);

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: GlassCard(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            PlayerAvatar(avatarId: avatarId, username: username, size: 40),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(displayName, style: BiladaText.title(size: 14)),
                  Text('@$username',
                      style:
                          BiladaText.label(color: AppTheme.cOutline, size: 11)),
                ],
              ),
            ),
            const SizedBox(width: 8),
            _actionFor(status, userId, notifier),
          ],
        ),
      ),
    );
  }

  /// Duruma göre buton:
  ///  - none     → "Ekle" (istek gönder)
  ///  - outgoing → "Bekliyor" (pasif)
  ///  - incoming → "Kabul Et" (gelen isteği kabul)
  ///  - friend   → "Arkadaş" (pasif, onay)
  Widget _actionFor(String status, String userId, FriendsNotifier notifier) {
    switch (status) {
      case 'friend':
        return Text('Arkadaş ✓',
            style: BiladaText.label(color: AppTheme.cTertiary, size: 12));
      case 'outgoing':
        return Text('Bekliyor',
            style: BiladaText.label(color: AppTheme.cOutline, size: 12));
      case 'incoming':
        return SizedBox(
          width: 110,
          child: ChunkyButton(
            height: 40,
            depth: 4,
            color: AppTheme.cTertiary,
            shadowColor: AppTheme.cTertiaryShadow,
            onPressed: () => notifier.accept(userId),
            child: const Text('KABUL ET', style: TextStyle(fontSize: 13)),
          ),
        );
      case 'none':
      default:
        return SizedBox(
          width: 90,
          child: ChunkyButton(
            height: 40,
            depth: 4,
            onPressed: () => notifier.sendRequest(userId),
            child: const Text('EKLE', style: TextStyle(fontSize: 14)),
          ),
        );
    }
  }
}

// ---------------------------------------------------------------------------
// Ortak boş durum bileşeni.
// ---------------------------------------------------------------------------

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.icon, required this.message});
  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 56, color: AppTheme.cOutline),
          const SizedBox(height: 16),
          Text(
            message,
            textAlign: TextAlign.center,
            style: BiladaText.body(color: AppTheme.cOutline),
          ),
        ],
      ),
    );
  }
}
