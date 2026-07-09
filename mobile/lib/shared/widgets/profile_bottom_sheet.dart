import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/friends/providers/friends_provider.dart';
import 'package:quizroyale/features/profile/providers/profile_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/player_avatar.dart';

Future<void> showProfileSheet(BuildContext context, {required String username}) {
  return showModalBottomSheet(
    context: context,
    backgroundColor: Colors.transparent,
    isScrollControlled: true,
    builder: (_) => ProviderScope(child: _ProfileSheet(username: username)),
  );
}

class _ProfileSheet extends ConsumerWidget {
  const _ProfileSheet({required this.username});
  final String username;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(otherProfileProvider(username));
    final friendsState = ref.watch(friendsProvider);
    final isFriend = friendsState.friends.any((f) => f['username'] == username);

    return DraggableScrollableSheet(
      initialChildSize: 0.55,
      minChildSize: 0.4,
      maxChildSize: 0.85,
      builder: (_, controller) => Container(
        decoration: const BoxDecoration(
          color: AppTheme.cSurfaceContainerLow,
          borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
        ),
        child: Column(
          children: [
            const SizedBox(height: 12),
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(color: AppTheme.cOutlineVariant, borderRadius: BorderRadius.circular(2)),
            ),
            Expanded(
              child: state.isLoading
                  ? const Center(child: CircularProgressIndicator(color: AppTheme.cPrimaryContainer))
                  : state.profile == null
                      ? Center(child: Text('Profil yüklenemedi', style: BiladaText.body(color: AppTheme.cOutline)))
                      : _SheetContent(
                          scrollController: controller,
                          profile: state.profile!,
                          isFriend: isFriend,
                          onAddFriend: () {
                            ref.read(friendsProvider.notifier).sendRequest(username);
                            Navigator.of(context).pop();
                          },
                          onClose: () => Navigator.of(context).pop(),
                        ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SheetContent extends StatelessWidget {
  const _SheetContent({
    required this.scrollController,
    required this.profile,
    required this.isFriend,
    required this.onAddFriend,
    required this.onClose,
  });

  final ScrollController scrollController;
  final Map<String, dynamic> profile;
  final bool isFriend;
  final VoidCallback onAddFriend;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    final username = profile['username'] as String? ?? '';
    final avatarId = profile['avatar_id'] as String? ?? 'default_01';
    final bio = profile['bio'] as String? ?? '';
    final level = profile['level'] as int? ?? 1;
    // İstatistikler public profil yanıtında ÜST SEVİYE alanlardır
    // (games_played/games_won/win_rate); iç 'stats' nesnesi hiç dönmez.
    final stats = <String, dynamic>{
      'games_played': profile['games_played'] ?? 0,
      'games_won': profile['games_won'] ?? 0,
      'win_rate': (profile['win_rate'] as num?)?.round() ?? 0,
    };
    final badges = (profile['badges'] as List? ?? []).cast<String>();

    return SingleChildScrollView(
      controller: scrollController,
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(3),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: AppTheme.cPrimaryContainer, width: 3),
            ),
            child: PlayerAvatar(avatarId: avatarId, username: username, size: 72),
          ),
          const SizedBox(height: 12),
          Text(username, style: BiladaText.headline(size: 22)),
          const SizedBox(height: 6),
          PillBadge('SEVİYE $level', color: AppTheme.cPrimaryContainer, fg: AppTheme.cOnPrimaryContainer),
          if (bio.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(bio, textAlign: TextAlign.center, style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 13)),
          ],
          const SizedBox(height: 20),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _MiniStat(label: 'Oyun', value: '${stats['games_played'] ?? 0}'),
              _MiniStat(label: 'Galibiyet', value: '${stats['games_won'] ?? 0}'),
              _MiniStat(label: 'Kazanma %', value: '${stats['win_rate'] ?? 0}%'),
            ],
          ),
          if (badges.isNotEmpty) ...[
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: badges
                  .take(5)
                  .map((b) => GlassCard(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        child: Text(b, style: BiladaText.body(size: 12)),
                      ))
                  .toList(),
            ),
          ],
          const SizedBox(height: 24),
          Row(
            children: [
              Expanded(
                child: ChunkyButton(
                  height: 48,
                  depth: 4,
                  color: AppTheme.cSurfaceContainerHigh,
                  foreground: AppTheme.cOnSurface,
                  shadowColor: AppTheme.cSurfaceContainerLowest,
                  onPressed: onClose,
                  child: const Text('KAPAT', style: TextStyle(fontSize: 15)),
                ),
              ),
              if (!isFriend) ...[
                const SizedBox(width: 12),
                Expanded(
                  child: ChunkyButton(
                    height: 48,
                    depth: 4,
                    onPressed: onAddFriend,
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [Icon(Icons.person_add_rounded, size: 16), SizedBox(width: 6), Text('EKLE', style: TextStyle(fontSize: 15))],
                    ),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  const _MiniStat({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(value, style: BiladaText.headline(size: 20)),
        Text(label, style: BiladaText.label(color: AppTheme.cOutline, size: 11)),
      ],
    );
  }
}
