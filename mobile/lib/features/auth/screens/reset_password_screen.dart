import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

/// Şifre sıfırlama — token + yeni şifre gir, başarıda login'e dön.
class ResetPasswordScreen extends ConsumerStatefulWidget {
  const ResetPasswordScreen({super.key, this.initialToken});

  /// (Opsiyonel) Bağlantıdan/DEBUG akışından gelen sıfırlama token'ı.
  final String? initialToken;

  @override
  ConsumerState<ResetPasswordScreen> createState() => _ResetPasswordScreenState();
}

class _ResetPasswordScreenState extends ConsumerState<ResetPasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _tokenController;
  final _passwordController = TextEditingController();
  final _confirmController = TextEditingController();
  bool _obscurePassword = true;

  @override
  void initState() {
    super.initState();
    _tokenController = TextEditingController(text: widget.initialToken ?? '');
  }

  @override
  void dispose() {
    _tokenController.dispose();
    _passwordController.dispose();
    _confirmController.dispose();
    super.dispose();
  }

  Future<void> _handleSubmit() async {
    if (!_formKey.currentState!.validate()) return;
    FocusScope.of(context).unfocus();
    final ok = await ref.read(authProvider.notifier).resetPassword(
          _tokenController.text.trim(),
          _passwordController.text,
        );
    if (!mounted) return;
    if (ok) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Şifren güncellendi. Yeni şifrenle giriş yapabilirsin.'),
          backgroundColor: AppTheme.cTertiaryContainer,
        ),
      );
      context.go('/login');
    } else {
      final error = ref.read(authProvider).error ?? 'Sıfırlama başarısız';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error), backgroundColor: AppTheme.danger),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final isLoading = ref.watch(authProvider).isLoading;
    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: Stack(
        children: [
          const Positioned.fill(child: BiladaBackground(gradient: AppTheme.epicGradient)),
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
              child: Column(
                children: [
                  Align(
                    alignment: Alignment.centerLeft,
                    child: IconButton(
                      icon: const Icon(Icons.arrow_back_rounded, color: AppTheme.cOnSurface),
                      onPressed: () => context.canPop() ? context.pop() : context.go('/login'),
                    ),
                  ),
                  const SizedBox(height: 8),
                  const BiladaLogo(fontSize: 36),
                  const SizedBox(height: 8),
                  Text(
                    'Yeni şifreni belirle',
                    style: BiladaText.body(color: AppTheme.cOnSurfaceVariant),
                  ),
                  const SizedBox(height: 28),
                  GlassCard(
                    padding: const EdgeInsets.all(24),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          TextFormField(
                            controller: _tokenController,
                            enabled: !isLoading,
                            style: BiladaText.body(),
                            decoration: const InputDecoration(
                              labelText: 'Sıfırlama kodu',
                              prefixIcon: Icon(Icons.vpn_key_rounded),
                            ),
                            validator: (v) =>
                                (v == null || v.trim().isEmpty) ? 'Sıfırlama kodu zorunludur' : null,
                          ),
                          const SizedBox(height: 16),
                          TextFormField(
                            controller: _passwordController,
                            obscureText: _obscurePassword,
                            enabled: !isLoading,
                            style: BiladaText.body(),
                            decoration: InputDecoration(
                              labelText: 'Yeni şifre',
                              prefixIcon: const Icon(Icons.lock_rounded),
                              suffixIcon: IconButton(
                                icon: Icon(_obscurePassword
                                    ? Icons.visibility_off_rounded
                                    : Icons.visibility_rounded),
                                onPressed: () =>
                                    setState(() => _obscurePassword = !_obscurePassword),
                              ),
                            ),
                            validator: (v) {
                              if (v == null || v.isEmpty) return 'Şifre zorunludur';
                              if (v.length < 8) return 'En az 8 karakter olmalı';
                              return null;
                            },
                          ),
                          const SizedBox(height: 16),
                          TextFormField(
                            controller: _confirmController,
                            obscureText: _obscurePassword,
                            enabled: !isLoading,
                            style: BiladaText.body(),
                            decoration: const InputDecoration(
                              labelText: 'Yeni şifre (tekrar)',
                              prefixIcon: Icon(Icons.lock_outline_rounded),
                            ),
                            validator: (v) {
                              if (v == null || v.isEmpty) return 'Şifreyi tekrar gir';
                              if (v != _passwordController.text) return 'Şifreler eşleşmiyor';
                              return null;
                            },
                          ),
                          const SizedBox(height: 28),
                          ChunkyButton(
                            height: 56,
                            onPressed: isLoading ? null : _handleSubmit,
                            child: const Text('ŞİFREYİ SIFIRLA'),
                          ),
                        ],
                      ),
                    ),
                  ),
                  if (isLoading) ...[
                    const SizedBox(height: 24),
                    const CircularProgressIndicator(color: AppTheme.cPrimaryContainer),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
