import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;
  bool _acceptedTerms = false;

  static final _usernameRegex = RegExp(r'^[a-zA-Z0-9_.]{3,15}$');
  static final _emailRegex = RegExp(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$');

  @override
  void initState() {
    super.initState();
    _passwordController.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _handleRegister() async {
    if (!_formKey.currentState!.validate()) return;
    if (!_acceptedTerms) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Devam etmek için Gizlilik Politikası ve Kullanım Şartları\'nı kabul etmelisin.'),
          backgroundColor: AppTheme.danger,
        ),
      );
      return;
    }
    FocusScope.of(context).unfocus();
    final ok = await ref.read(authProvider.notifier).register(
          _usernameController.text.trim(),
          _emailController.text.trim(),
          _passwordController.text,
        );
    if (!mounted) return;
    if (ok) {
      context.go('/home');
    } else {
      final error = ref.read(authProvider).error ?? 'Kayıt başarısız';
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
                  const SizedBox(height: 24),
                  const BiladaLogo(fontSize: 40),
                  const SizedBox(height: 8),
                  Text('Hesap oluştur, oynamaya başla!', style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 13)),
                  const SizedBox(height: 28),
                  GlassCard(
                    padding: const EdgeInsets.all(24),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          TextFormField(
                            controller: _usernameController,
                            enabled: !isLoading,
                            style: BiladaText.body(),
                            decoration: const InputDecoration(
                              labelText: 'Kullanıcı Adı',
                              prefixIcon: Icon(Icons.alternate_email_rounded),
                            ),
                            validator: (v) {
                              if (v == null || v.trim().isEmpty) return 'Kullanıcı adı zorunludur';
                              if (!_usernameRegex.hasMatch(v.trim())) return '3-15 karakter; harf, rakam, . ve _';
                              return null;
                            },
                          ),
                          const SizedBox(height: 16),
                          TextFormField(
                            controller: _emailController,
                            enabled: !isLoading,
                            keyboardType: TextInputType.emailAddress,
                            style: BiladaText.body(),
                            decoration: const InputDecoration(
                              labelText: 'E-posta',
                              prefixIcon: Icon(Icons.email_rounded),
                            ),
                            validator: (v) {
                              if (v == null || v.trim().isEmpty) return 'E-posta zorunludur';
                              if (!_emailRegex.hasMatch(v.trim())) return 'Geçerli bir e-posta gir';
                              return null;
                            },
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
                            validator: (v) {
                              if (v == null || v.isEmpty) return 'Şifre zorunludur';
                              if (v.length < 8) return 'En az 8 karakter olmalı';
                              return null;
                            },
                          ),
                          _passwordStrength(),
                          const SizedBox(height: 20),
                          _consentCheckbox(isLoading),
                          const SizedBox(height: 24),
                          ChunkyButton(
                            height: 56,
                            onPressed: (isLoading || !_acceptedTerms) ? null : _handleRegister,
                            child: const Text('KAYIT OL'),
                          ),
                          const SizedBox(height: 24),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text('Zaten hesabın var mı? ', style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 14)),
                              GestureDetector(
                                onTap: isLoading ? null : () => context.go('/login'),
                                child: Text('Giriş Yap', style: BiladaText.title(color: AppTheme.cPrimary, size: 14)),
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

  /// Zorunlu yasal onay kutusu — işaretlenmeden kayıt butonu pasif kalır.
  Widget _consentCheckbox(bool isLoading) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 28,
          height: 28,
          child: Checkbox(
            value: _acceptedTerms,
            onChanged: isLoading ? null : (v) => setState(() => _acceptedTerms = v ?? false),
            activeColor: AppTheme.cPrimaryContainer,
            checkColor: AppTheme.cOnPrimaryContainer,
            side: const BorderSide(color: AppTheme.cOutline, width: 1.5),
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text.rich(
              TextSpan(
                style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 13),
                children: [
                  TextSpan(
                    text: 'Gizlilik Politikası',
                    style: BiladaText.body(color: AppTheme.cPrimary, size: 13).copyWith(
                      fontWeight: FontWeight.w700,
                      decoration: TextDecoration.underline,
                    ),
                    recognizer: TapGestureRecognizer()..onTap = () => context.push('/legal/privacy'),
                  ),
                  const TextSpan(text: ' ve '),
                  TextSpan(
                    text: 'Kullanım Şartları',
                    style: BiladaText.body(color: AppTheme.cPrimary, size: 13).copyWith(
                      fontWeight: FontWeight.w700,
                      decoration: TextDecoration.underline,
                    ),
                    recognizer: TapGestureRecognizer()..onTap = () => context.push('/legal/terms'),
                  ),
                  const TextSpan(text: '\'nı okudum, kabul ediyorum.'),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _passwordStrength() {
    final password = _passwordController.text;
    if (password.isEmpty) return const SizedBox.shrink();
    int strength = 0;
    if (password.length >= 8) strength++;
    if (password.contains(RegExp(r'[A-Z]'))) strength++;
    if (password.contains(RegExp(r'[0-9]'))) strength++;
    if (password.contains(RegExp(r'[!@#$%^&*(),.?":{}|<>]'))) strength++;
    const labels = ['Zayıf', 'Orta', 'İyi', 'Güçlü'];
    const colors = [AppTheme.cError, AppTheme.gold, AppTheme.cTertiary, AppTheme.cTertiary];
    final idx = (strength - 1).clamp(0, 3);
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: List.generate(4, (i) {
              return Expanded(
                child: Container(
                  margin: const EdgeInsets.only(right: 4),
                  height: 4,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(2),
                    color: i < strength ? colors[idx] : AppTheme.cOutlineVariant,
                  ),
                ),
              );
            }),
          ),
          const SizedBox(height: 6),
          Text('Şifre gücü: ${labels[idx]}', style: BiladaText.label(color: colors[idx], size: 11)),
        ],
      ),
    );
  }
}
