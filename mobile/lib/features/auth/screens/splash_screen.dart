import 'dart:async';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/core/storage/secure_storage.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1200))..repeat(reverse: true);

  @override
  void initState() {
    super.initState();
    _navigateAfterDelay();
  }

  Future<void> _navigateAfterDelay() async {
    await Future.delayed(const Duration(milliseconds: 2500));
    if (!mounted) return;
    bool isLoggedIn = false;
    try {
      isLoggedIn = await SecureStorage.instance.isLoggedIn();
    } catch (_) {}
    if (!mounted) return;
    context.go(isLoggedIn ? '/home' : '/onboarding');
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          const Positioned.fill(child: BiladaBackground(gradient: AppTheme.epicGradient)),
          Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                ScaleTransition(
                  scale: Tween<double>(begin: 0.96, end: 1.06).animate(
                    CurvedAnimation(parent: _c, curve: Curves.easeInOut),
                  ),
                  child: Container(
                    width: 132,
                    height: 132,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: const LinearGradient(
                        colors: [AppTheme.cPrimaryContainer, AppTheme.cSecondaryContainer],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      boxShadow: [
                        BoxShadow(color: AppTheme.cPrimaryContainer.withValues(alpha: 0.5), blurRadius: 40, spreadRadius: 6),
                      ],
                    ),
                    child: const Icon(Icons.psychology_rounded, color: Colors.white, size: 72),
                  ),
                ),
                const SizedBox(height: 40),
                const BiladaLogo(fontSize: 44),
                const SizedBox(height: 16),
                FadeTransition(
                  opacity: Tween<double>(begin: 0.4, end: 1).animate(_c),
                  child: Text('YÜKLENİYOR...', style: BiladaText.label(color: AppTheme.cTertiary, size: 13)),
                ),
              ],
            ),
          ),
          Positioned(
            bottom: 32,
            left: 0,
            right: 0,
            child: Text(
              'v1.0.0',
              textAlign: TextAlign.center,
              style: BiladaText.label(color: AppTheme.cOutline.withValues(alpha: 0.6), size: 11),
            ),
          ),
        ],
      ),
    );
  }
}
