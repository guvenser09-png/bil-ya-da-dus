import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _identifierController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;

  @override
  void dispose() {
    _identifierController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _handleLogin() async {
    if (!_formKey.currentState!.validate()) return;
    FocusScope.of(context).unfocus();
    final ok = await ref.read(authProvider.notifier).login(
          _identifierController.text.trim(),
          _passwordController.text,
        );
    if (!mounted) return;
    if (ok) {
      context.go('/home');
    } else {
      final error = ref.read(authProvider).error ?? 'Giriş başarısız';
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
                  const SizedBox(height: 32),
                  const BiladaLogo(fontSize: 44),
                  const SizedBox(height: 8),
                  Text('Hoş geldin!', style: BiladaText.body(color: AppTheme.cOnSurfaceVariant)),
                  const SizedBox(height: 32),
                  GlassCard(
                    padding: const EdgeInsets.all(24),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          TextFormField(
                            controller: _identifierController,
                            enabled: !isLoading,
                            style: BiladaText.body(),
                            decoration: const InputDecoration(
                              labelText: 'Kullanıcı adı veya e-posta',
                              prefixIcon: Icon(Icons.person_rounded),
                            ),
                            validator: (v) => (v == null || v.trim().isEmpty) ? 'Bu alan zorunludur' : null,
                          ),
                          const SizedBox(height: 16),
                          TextFormField(
                            controller: _passwordController,
                            obscureText: _obscurePassword,
                            enabled: !isLoading,
                            style: BiladaText.body(),
                            decoration: InputDecoration(
                              labelText: 'Şifre',
                              prefixIcon: const Icon(Icons.lock_rounded),
                              suffixIcon: IconButton(
                                icon: Icon(_obscurePassword ? Icons.visibility_off_rounded : Icons.visibility_rounded),
                                onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                              ),
                            ),
                            validator: (v) => (v == null || v.isEmpty) ? 'Şifre zorunludur' : null,
                          ),
                          const SizedBox(height: 12),
                          Align(
                            alignment: Alignment.centerRight,
                            child: GestureDetector(
                              onTap: isLoading ? null : () => context.push('/forgot-password'),
                              child: Text(
                                'Şifremi unuttum',
                                style: BiladaText.label(color: AppTheme.cPrimary, size: 12),
                              ),
                            ),
                          ),
                          const SizedBox(height: 20),
                          ChunkyButton(
                            height: 56,
                            onPressed: isLoading ? null : _handleLogin,
                            child: const Text('GİRİŞ YAP'),
                          ),
                          const SizedBox(height: 24),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text('Hesabın yok mu? ', style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 14)),
                              GestureDetector(
                                onTap: isLoading ? null : () => context.go('/register'),
                                child: Text('Kayıt Ol', style: BiladaText.title(color: AppTheme.cPrimary, size: 14)),
                              ),
                            ],
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
