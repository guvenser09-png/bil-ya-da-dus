import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/room/providers/room_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/player_avatar.dart';

/// Özel oda maçı için gereken en az gerçek oyuncu sayısı (backend ile aynı).
/// Oda botla doldurulmaz; arkadaşlar 2 kişilik düello oynar.
const int _kMinPlayers = 2;

/// Oda lobisi: kod paylaşımı, üye listesi, host için BAŞLAT / herkes için AYRIL.
/// `room_starting` → /game'e geçer; `room_closed` → uyarı + home'a döner.
class RoomScreen extends ConsumerStatefulWidget {
  const RoomScreen({super.key});

  @override
  ConsumerState<RoomScreen> createState() => _RoomScreenState();
}

class _RoomScreenState extends ConsumerState<RoomScreen> {
  bool _navigated = false;

  void _leave() {
    ref.read(roomProvider.notifier).leave();
    context.go('/home');
  }

  void _copyCode(String code) {
    // Arkadaşa göndermesi kolay olsun diye kodu açıklayıcı bir metinle kopyala.
    Clipboard.setData(ClipboardData(
      text: 'Bil ya da Düş\'te düelloya gel! Oda kodum: $code',
    ));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Oda kodu kopyalandı — arkadaşına gönder!'),
        backgroundColor: AppTheme.cTertiary,
        duration: Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(roomProvider);

    ref.listen(roomProvider, (_, next) {
      // Oyuna geçiş: abonelik provider içinde zaten temizlendi (room_starting).
      if (!_navigated && next.status == RoomStatus.starting && next.gameId != null) {
        _navigated = true;
        context.go('/game/${next.gameId}');
      }
      // Oda kapandı (host ayrıldı vb.) → uyarı + home.
      if (next.status == RoomStatus.closed) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(next.closedReason ?? 'Oda kapatıldı.'),
            backgroundColor: AppTheme.danger,
          ),
        );
        context.go('/home');
      }
      if (next.status == RoomStatus.error && next.error != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(next.error!), backgroundColor: AppTheme.danger),
        );
      }
    });

    final code = state.code ?? '------';
    final members = state.members;

    return WillPopScope(
      onWillPop: () async {
        ref.read(roomProvider.notifier).leave();
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
                          Text('Oda Lobisi', style: BiladaText.headline(color: AppTheme.cPrimary, size: 24)),
                          const SizedBox(height: 16),
                          _CodeCard(code: code, onCopy: () => _copyCode(code)),
                          const SizedBox(height: 12),
                          Text(
                            'Arkadaşın bu kodu girsin — 2 kişilik düello!',
                            textAlign: TextAlign.center,
                            style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 13),
                          ),
                          const SizedBox(height: 20),
                          _membersHeader(members.length),
                          const SizedBox(height: 12),
                          _membersGrid(members, state.hostUserId),
                          const SizedBox(height: 28),
                          if (state.isHost) ...[
                            ChunkyButton(
                              height: 60,
                              // Oda BOTSUZ başlar → en az 2 gerçek oyuncu gerekir.
                              onPressed: members.length >= _kMinPlayers
                                  ? () => ref.read(roomProvider.notifier).start()
                                  : null,
                              child: const Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.play_arrow_rounded, size: 28),
                                  SizedBox(width: 6),
                                  Text('BAŞLAT', style: TextStyle(fontSize: 20)),
                                ],
                              ),
                            ),
                            if (members.length < _kMinPlayers) ...[
                              const SizedBox(height: 10),
                              Text(
                                'En az $_kMinPlayers oyuncu gerekli. Arkadaşının katılmasını bekle.',
                                textAlign: TextAlign.center,
                                style: BiladaText.label(color: AppTheme.cOutline, size: 12),
                              ),
                            ],
                          ] else
                            GlassCard(
                              padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  const SizedBox(
                                    width: 18,
                                    height: 18,
                                    child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.cTertiary),
                                  ),
                                  const SizedBox(width: 12),
                                  Text('Host bekleniyor...', style: BiladaText.body(size: 15)),
                                ],
                              ),
                            ),
                          const SizedBox(height: 12),
                          SizedBox(
                            width: 180,
                            child: ChunkyButton(
                              height: 52,
                              depth: 4,
                              color: AppTheme.cSurfaceContainerHigh,
                              foreground: AppTheme.cOnSurface,
                              shadowColor: AppTheme.cSurfaceContainerLowest,
                              onPressed: _leave,
                              child: const Text('AYRIL', style: TextStyle(fontSize: 18)),
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

  Widget _membersHeader(int count) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.group_rounded, color: AppTheme.cTertiary, size: 20),
        const SizedBox(width: 8),
        Text('$count Oyuncu', style: BiladaText.title(size: 16)),
      ],
    );
  }

  Widget _membersGrid(List<Map<String, dynamic>> members, String? hostUserId) {
    if (members.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 20),
        child: Text('Henüz kimse yok...', style: BiladaText.label(color: AppTheme.cOutline)),
      );
    }
    return Wrap(
      spacing: 16,
      runSpacing: 16,
      alignment: WrapAlignment.center,
      children: members.map((m) {
        final uid = m['user_id']?.toString();
        return _MemberSlot(
          username: (m['display_name'] ?? m['username'] ?? '?').toString(),
          avatarId: (m['avatar_id'] ?? 'default_01').toString(),
          isHost: hostUserId != null && uid == hostUserId,
        );
      }).toList(),
    );
  }
}

/// Büyük, kopyalanabilir oda kodu kartı.
class _CodeCard extends StatelessWidget {
  const _CodeCard({required this.code, required this.onCopy});
  final String code;
  final VoidCallback onCopy;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(18),
      onTap: onCopy,
      child: Column(
        children: [
          Text('ODA KODU', style: BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 12)),
          const SizedBox(height: 8),
          Text(
            code,
            style: BiladaText.displayXl(color: AppTheme.cPrimary, size: 40).copyWith(letterSpacing: 6),
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.copy_rounded, size: 16, color: AppTheme.cTertiary),
              const SizedBox(width: 6),
              Text('Kopyala ve paylaş', style: BiladaText.label(color: AppTheme.cTertiary, size: 12)),
            ],
          ),
        ],
      ),
    );
  }
}

class _MemberSlot extends StatelessWidget {
  const _MemberSlot({required this.username, required this.avatarId, required this.isHost});
  final String username;
  final String avatarId;
  final bool isHost;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 64,
      child: Column(
        children: [
          Stack(
            clipBehavior: Clip.none,
            children: [
              Container(
                padding: const EdgeInsets.all(2),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: isHost ? AppTheme.gold : AppTheme.cPrimaryContainer,
                    width: 2,
                  ),
                ),
                child: PlayerAvatar(avatarId: avatarId, username: username, size: 48),
              ),
              if (isHost)
                const Positioned(
                  top: -8,
                  left: 0,
                  right: 0,
                  child: Center(child: Text('👑', style: TextStyle(fontSize: 18))),
                ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            username.length > 8 ? '${username.substring(0, 7)}…' : username,
            style: BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 11),
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}
