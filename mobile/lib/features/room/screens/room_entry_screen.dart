import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/room/providers/room_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

/// Oda girişi: "ODA KUR" (host) veya "KODA KATIL" (6 haneli kod) seçimi.
/// Bağlantı başarılı olunca room_screen'e geçer.
class RoomEntryScreen extends ConsumerStatefulWidget {
  const RoomEntryScreen({super.key});

  @override
  ConsumerState<RoomEntryScreen> createState() => _RoomEntryScreenState();
}

class _RoomEntryScreenState extends ConsumerState<RoomEntryScreen> {
  final _codeController = TextEditingController();
  bool _navigated = false;

  @override
  void dispose() {
    _codeController.dispose();
    super.dispose();
  }

  void _createRoom() {
    _navigated = false;
    ref.read(roomProvider.notifier).createRoom();
  }

  void _joinRoom() {
    final code = _codeController.text.trim();
    if (code.length != 6) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('6 haneli oda kodunu gir.'),
          backgroundColor: AppTheme.danger,
        ),
      );
      return;
    }
    FocusScope.of(context).unfocus();
    _navigated = false;
    ref.read(roomProvider.notifier).joinRoom(code);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(roomProvider);
    final connecting = state.status == RoomStatus.connecting;

    // Odaya girince room_screen'e geç.
    ref.listen(roomProvider, (_, next) {
      if (!_navigated && next.status == RoomStatus.inRoom) {
        _navigated = true;
        context.go('/room/lobby');
      }
      if (next.status == RoomStatus.error && next.error != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(next.error!), backgroundColor: AppTheme.danger),
        );
      }
    });

    return Scaffold(
      body: Stack(
        children: [
          const Positioned.fill(child: BiladaBackground()),
          SafeArea(
            child: Column(
              children: [
                // Header
                Padding(
                  padding: const EdgeInsets.fromLTRB(8, 8, 20, 0),
                  child: Row(
                    children: [
                      IconButton(
                        onPressed: () => context.go('/home'),
                        icon: const Icon(Icons.arrow_back_rounded, color: AppTheme.cOnSurfaceVariant),
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
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const SizedBox(height: 12),
                        Text(
                          'Arkadaşlarla Oyna',
                          style: BiladaText.headline(color: AppTheme.cPrimary, size: 26),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Özel bir oda kur ya da arkadaşının\nkoduyla katıl.',
                          style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 14),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 28),
                        // ODA KUR
                        ChunkyButton(
                          height: 72,
                          onPressed: connecting ? null : _createRoom,
                          child: const Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.add_circle_outline_rounded, size: 26),
                              SizedBox(width: 10),
                              Text('ODA KUR', style: TextStyle(fontSize: 20)),
                            ],
                          ),
                        ),
                        const SizedBox(height: 24),
                        Row(
                          children: [
                            const Expanded(child: Divider(color: AppTheme.cOutlineVariant)),
                            Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 12),
                              child: Text('VEYA', style: BiladaText.label(size: 12)),
                            ),
                            const Expanded(child: Divider(color: AppTheme.cOutlineVariant)),
                          ],
                        ),
                        const SizedBox(height: 24),
                        // KODA KATIL
                        GlassCard(
                          padding: const EdgeInsets.all(18),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Text('Koda Katıl', style: BiladaText.title(size: 18)),
                              const SizedBox(height: 12),
                              TextField(
                                controller: _codeController,
                                enabled: !connecting,
                                textCapitalization: TextCapitalization.characters,
                                textAlign: TextAlign.center,
                                maxLength: 6,
                                style: BiladaText.headline(size: 28, color: AppTheme.cPrimary),
                                inputFormatters: [
                                  FilteringTextInputFormatter.allow(RegExp(r'[A-Za-z0-9]')),
                                  _UpperCaseFormatter(),
                                ],
                                decoration: InputDecoration(
                                  counterText: '',
                                  hintText: 'ABC123',
                                  hintStyle: BiladaText.headline(size: 28, color: AppTheme.cOutline),
                                  filled: true,
                                  fillColor: AppTheme.cSurfaceContainerHigh,
                                  border: OutlineInputBorder(
                                    borderRadius: BorderRadius.circular(16),
                                    borderSide: BorderSide.none,
                                  ),
                                ),
                                onSubmitted: (_) => _joinRoom(),
                              ),
                              const SizedBox(height: 12),
                              ChunkyButton(
                                height: 56,
                                color: AppTheme.cSecondaryContainer,
                                foreground: Colors.white,
                                shadowColor: AppTheme.cSecondaryShadow,
                                onPressed: connecting ? null : _joinRoom,
                                child: const Text('KATIL', style: TextStyle(fontSize: 18)),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 24),
                        if (connecting)
                          const Center(
                            child: Padding(
                              padding: EdgeInsets.only(top: 8),
                              child: CircularProgressIndicator(color: AppTheme.cPrimary),
                            ),
                          ),
                      ],
                    ),
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

/// Girişi büyük harfe çevirir (oda kodları büyük harf).
class _UpperCaseFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(TextEditingValue oldValue, TextEditingValue newValue) {
    return newValue.copyWith(text: newValue.text.toUpperCase());
  }
}
