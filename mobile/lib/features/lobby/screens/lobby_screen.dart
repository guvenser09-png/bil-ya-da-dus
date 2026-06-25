import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/constants/app_constants.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/cosmetics/providers/cosmetics_provider.dart';
import 'package:quizroyale/features/lobby/providers/lobby_provider.dart';
import 'package:quizroyale/shared/characters.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/player_avatar.dart';

class LobbyScreen extends ConsumerStatefulWidget {
  const LobbyScreen({super.key, this.mode});

  /// Maç modu. "tournament" verilirse turnuva lobisine bağlanılır; null ise
  /// normal "Hızlı Maç" akışı çalışır.
  final String? mode;

  @override
  ConsumerState<LobbyScreen> createState() => _LobbyScreenState();
}

class _LobbyScreenState extends ConsumerState<LobbyScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final saved = ref.read(authProvider).user?['avatar_id'] as String?;
      final avatarId = (saved != null && isCatalogCharacter(saved)) ? saved : 'robot';
      ref.read(lobbyProvider.notifier).connect(avatarId: avatarId, mode: widget.mode);
    });
  }

  void _leave() {
    ref.read(lobbyProvider.notifier).disconnect();
    context.go('/home');
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(lobbyProvider);

    ref.listen(lobbyProvider, (_, next) {
      if (next.gameId != null) {
        context.go('/game/${next.gameId}');
      }
      if (next.error != null && next.error!.contains('iptal')) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(next.error!), backgroundColor: AppTheme.danger),
        );
        context.go('/home');
      }
    });

    final progress = (state.countdown / AppConstants.lobbyTimeoutSeconds).clamp(0.0, 1.0);
    final urgent = state.countdown <= 5;
    final ringColor = urgent ? AppTheme.cPrimaryContainer : AppTheme.cTertiary;

    return WillPopScope(
      onWillPop: () async {
        ref.read(lobbyProvider.notifier).disconnect();
        return true;
      },
      child: Scaffold(
        body: Stack(
          children: [
            const Positioned.fill(child: BiladaBackground(gradient: AppTheme.epicGradient)),
            SafeArea(
              child: Column(
                children: [
                  // Header
                  Padding(
                    padding: const EdgeInsets.fromLTRB(8, 8, 20, 0),
                    child: Row(
                      children: [
                        IconButton(
                          onPressed: _leave,
                          icon: const Icon(Icons.close_rounded, color: AppTheme.cOnSurfaceVariant),
                        ),
                        const Spacer(),
                        const BiladaLogo(fontSize: 22),
                        const Spacer(),
                        const SizedBox(width: 48),
                      ],
                    ),
                  ),
                  Expanded(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      child: Column(
                        children: [
                          const SizedBox(height: 8),
                          Text('Maç başlıyor...', style: BiladaText.headline(color: AppTheme.cPrimary, size: 26)),
                          const SizedBox(height: 4),
                          Text(
                            '${state.players.length.clamp(0, AppConstants.maxPlayers)} yarışmacı kapışmaya hazır',
                            style: BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 12),
                          ),
                          const SizedBox(height: 24),
                          CountdownRing(
                            progress: progress,
                            label: '${state.countdown}',
                            sublabel: 'Saniye',
                            color: ringColor,
                            size: 176,
                            stroke: 12,
                          ),
                          const SizedBox(height: 24),
                          _playerBar(
                            state.players.length.clamp(0, AppConstants.maxPlayers),
                          ),
                          const SizedBox(height: 20),
                          _playerGrid(state.players),
                          const SizedBox(height: 28),
                          SizedBox(
                            width: 180,
                            child: ChunkyButton(
                              height: 52,
                              depth: 4,
                              color: AppTheme.cSurfaceContainerHigh,
                              foreground: AppTheme.cOnSurface,
                              shadowColor: AppTheme.cSurfaceContainerLowest,
                              onPressed: _leave,
                              child: const Text('İPTAL', style: TextStyle(fontSize: 18)),
                            ),
                          ),
                          const SizedBox(height: 24),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _playerBar(int count) {
    final ratio = (count / AppConstants.maxPlayers).clamp(0.0, 1.0);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: AppTheme.cSurfaceContainerHigh,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
      ),
      child: Row(
        children: [
          const Icon(Icons.group_rounded, color: AppTheme.cTertiary, size: 20),
          const SizedBox(width: 8),
          Text('$count/${AppConstants.maxPlayers} Oyuncu', style: BiladaText.title(size: 16)),
          const Spacer(),
          SizedBox(
            width: 120,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: ratio,
                minHeight: 8,
                backgroundColor: AppTheme.cSurfaceVariant,
                valueColor: const AlwaysStoppedAnimation(AppTheme.cTertiary),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _playerGrid(List<Map<String, dynamic>> players) {
    // Kozmetik vitrini: kendi kuşandığımız çerçeveyi kendi slotumuza giydir.
    // (Backend diğer oyuncuların çerçevesini henüz göndermiyor; geldiğinde
    // `p['frame']` üzerinden otomatik render edilir.)
    final myUsername = ref.read(authProvider).user?['username'] as String?;
    final myFrame = frameKeyFromId(ref.watch(cosmeticsProvider).equippedFrame);

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 5,
        mainAxisSpacing: 12,
        crossAxisSpacing: 12,
        childAspectRatio: 0.72,
      ),
      itemCount: AppConstants.maxPlayers,
      itemBuilder: (_, i) {
        if (i < players.length) {
          final p = players[i];
          final username = p['username'] as String? ?? '?';
          return _PlayerSlot(
            username: username,
            avatarId: p['avatar_id'] as String? ?? 'default_01',
            frame: (username == myUsername)
                ? myFrame
                : frameKeyFromId(p['frame'] as String?),
          );
        }
        return const _EmptySlot();
      },
    );
  }
}

class _PlayerSlot extends StatefulWidget {
  const _PlayerSlot({required this.username, required this.avatarId, this.frame});
  final String username;
  final String avatarId;

  /// Kuşanılmış çerçeve anahtarı (varsa). PlayerAvatar bilinmeyen anahtarda
  /// çerçeve çizmez → güvenli.
  final String? frame;

  @override
  State<_PlayerSlot> createState() => _PlayerSlotState();
}

class _PlayerSlotState extends State<_PlayerSlot> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 350))..forward();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ScaleTransition(
      scale: CurvedAnimation(parent: _c, curve: Curves.elasticOut),
      child: Column(
        children: [
          Stack(
            clipBehavior: Clip.none,
            children: [
              // Çerçeve kuşanılmışsa PlayerAvatar kendi gradyan halkasını çizer
              // (vitrin hissi); yoksa nötr ince çerçeveye düşeriz.
              Container(
                padding: const EdgeInsets.all(2),
                decoration: widget.frame == null
                    ? BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(color: AppTheme.cPrimaryContainer, width: 2),
                      )
                    : null,
                child: PlayerAvatar(
                  avatarId: widget.avatarId,
                  username: widget.username,
                  size: 44,
                  frame: widget.frame,
                ),
              ),
              Positioned(
                bottom: -2,
                right: -2,
                child: Container(
                  width: 18,
                  height: 18,
                  decoration: BoxDecoration(
                    color: AppTheme.cTertiary,
                    shape: BoxShape.circle,
                    border: Border.all(color: AppTheme.cSurfaceContainerHigh, width: 2),
                  ),
                  child: const Icon(Icons.check, size: 10, color: AppTheme.cOnTertiary),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            widget.username.length > 7 ? '${widget.username.substring(0, 6)}…' : widget.username,
            style: BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 10),
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

class _EmptySlot extends StatelessWidget {
  const _EmptySlot();

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: 0.3,
      child: Column(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: AppTheme.cSurfaceContainerLow,
              shape: BoxShape.circle,
              border: Border.all(color: AppTheme.cOutlineVariant, width: 1.5, style: BorderStyle.solid),
            ),
            child: const Icon(Icons.person_outline, color: AppTheme.cOutline, size: 22),
          ),
          const SizedBox(height: 6),
          Text('...', style: BiladaText.label(color: AppTheme.cOutline, size: 10)),
        ],
      ),
    );
  }
}

