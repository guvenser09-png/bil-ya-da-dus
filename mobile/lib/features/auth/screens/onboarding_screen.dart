import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;
  static const int _totalPages = 3;

  final List<_OnboardingPage> _pages = const [
    _OnboardingPage(
      icon: Icons.groups_rounded,
      color: AppTheme.cPrimaryContainer,
      title: '20 Oyuncu, 5 Tur!',
      subtitle: 'Her turda yanlış cevap verenler elenir. Son ayakta kalan şampiyon olur!',
    ),
    _OnboardingPage(
      icon: Icons.bolt_rounded,
      color: AppTheme.cTertiary,
      title: 'Hızlı Cevap Ver!',
      subtitle: 'Ne kadar hızlı cevap verirsen o kadar fazla puan! Seri doğrularda çarpan bonusu!',
    ),
    _OnboardingPage(
      icon: Icons.emoji_events_rounded,
      color: AppTheme.gold,
      title: 'Şampiyon Ol!',
      subtitle: 'Günlük, haftalık ve sezonluk sıralamada zirveye çık. Rozetler ve ödüller kazan!',
    ),
  ];

  void _next() {
    if (_currentPage < _totalPages - 1) {
      _pageController.nextPage(duration: const Duration(milliseconds: 400), curve: Curves.easeInOut);
    } else {
      context.go('/login');
    }
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isLast = _currentPage == _totalPages - 1;
    return Scaffold(
      body: Stack(
        children: [
          const Positioned.fill(child: BiladaBackground(gradient: AppTheme.epicGradient)),
          SafeArea(
            child: Column(
              children: [
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: () => context.go('/login'),
                    child: Text('Atla', style: BiladaText.label(color: AppTheme.cOnSurfaceVariant)),
                  ),
                ),
                Expanded(
                  child: PageView.builder(
                    controller: _pageController,
                    onPageChanged: (i) => setState(() => _currentPage = i),
                    itemCount: _totalPages,
                    itemBuilder: (_, i) => _page(_pages[i]),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 16, 24, 36),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: List.generate(_totalPages, (i) {
                          final active = i == _currentPage;
                          return AnimatedContainer(
                            duration: const Duration(milliseconds: 300),
                            margin: const EdgeInsets.symmetric(horizontal: 4),
                            width: active ? 24 : 8,
                            height: 8,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(4),
                              color: active ? AppTheme.cPrimaryContainer : AppTheme.cOutlineVariant,
                            ),
                          );
                        }),
                      ),
                      const SizedBox(height: 28),
                      ChunkyButton(
                        height: 60,
                        onPressed: _next,
                        child: Text(isLast ? 'BAŞLA' : 'SONRAKİ'),
                      ),
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

  Widget _page(_OnboardingPage page) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 170,
            height: 170,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: page.color.withValues(alpha: 0.12),
              boxShadow: [BoxShadow(color: page.color.withValues(alpha: 0.25), blurRadius: 50, spreadRadius: 8)],
            ),
            child: Icon(page.icon, size: 84, color: page.color),
          ),
          const SizedBox(height: 40),
          Text(page.title, textAlign: TextAlign.center, style: BiladaText.displayXl(color: AppTheme.cOnSurface, size: 28)),
          const SizedBox(height: 16),
          Text(page.subtitle, textAlign: TextAlign.center, style: BiladaText.body(color: AppTheme.cOnSurfaceVariant)),
        ],
      ),
    );
  }
}

class _OnboardingPage {
  final IconData icon;
  final Color color;
  final String title;
  final String subtitle;
  const _OnboardingPage({required this.icon, required this.color, required this.title, required this.subtitle});
}
