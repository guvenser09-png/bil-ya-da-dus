import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

/// Şifremi unuttum — e-posta gir, sıfırlama bağlantısı gönder.
class ForgotPasswordScreen extends ConsumerStatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  ConsumerState<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends ConsumerState<ForgotPasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  bool _sent = false;
  String? _debugToken;

  static final _emailRegex = RegExp(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$');

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _handleSubmit() async {
    if (!_formKey.currentState!.validate()) return;
    FocusScope.of(context).unfocus();
    try {
      final debugToken =
          await ref.read(authProvider.notifier).forgotPassword(_emailController.text.trim());
      if (!mounted) return;
      setState(() {
        _sent = true;
        _debugToken = debugToken;
      });
    } catch (_) {
      if (!mounted) return;
      final error = ref.read(authProvider).error ?? 'İşlem başarısız';
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
                      onPressed: () => context.pop(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  const BiladaLogo(fontSize: 36),
                  const SizedBox(height: 8),
                  Text(
                    'Şifreni mi unuttun?',
                    style: BiladaText.body(color: AppTheme.cOnSurfaceVariant),
                  ),
                  const SizedBox(height: 28),
                  GlassCard(
                    padding: const EdgeInsets.all(24),
                    child: _sent ? _successView() : _formView(isLoading),
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

  Widget _formView(bool isLoading) {
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Kayıtlı e-posta adresini gir. Şifre sıfırlama bağlantısını sana gönderelim.',
            style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 14),
          ),
          const SizedBox(height: 20),
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
          const SizedBox(height: 28),
          ChunkyButton(
            height: 56,
            onPressed: isLoading ? null : _handleSubmit,
            child: const Text('BAĞLANTI GÖNDER'),
          ),
          const SizedBox(height: 16),
          GestureDetector(
            onTap: isLoading ? null : () => context.push('/reset-password'),
            child: Text(
              'Zaten bir kodun var mı? Şifreyi sıfırla',
              textAlign: TextAlign.center,
              style: BiladaText.label(color: AppTheme.cPrimary, size: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _successView() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Icon(Icons.mark_email_read_rounded, color: AppTheme.cTertiary, size: 48),
        const SizedBox(height: 16),
        Text(
          'Bağlantı gönderildi!',
          textAlign: TextAlign.center,
          style: BiladaText.title(size: 18),
        ),
        const SizedBox(height: 8),
        Text(
          'Eğer bu e-posta kayıtlıysa, şifre sıfırlama bağlantısını gönderdik. Gelen kutunu (ve spam klasörünü) kontrol et.',
          textAlign: TextAlign.center,
          style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 14),
        ),
        // DEBUG kolaylığı: backend debug_token döndüyse doğrudan sıfırlama ekranına geç.
        if (kDebugMode && _debugToken != null) ...[
          const SizedBox(height: 16),
          Text(
            'DEBUG token: $_debugToken',
            textAlign: TextAlign.center,
            style: BiladaText.label(color: AppTheme.gold, size: 11),
          ),
          const SizedBox(height: 12),
          ChunkyButton(
            height: 48,
            color: AppTheme.cTertiaryContainer,
            foreground: Colors.white,
            shadowColor: AppTheme.cTertiaryShadow,
            onPressed: () => context.push('/reset-password', extra: _debugToken),
            child: const Text('TOKEN İLE SIFIRLA', style: TextStyle(fontSize: 15)),
          ),
        ],
        const SizedBox(height: 24),
        ChunkyButton(
          height: 52,
          onPressed: () => context.go('/login'),
          child: const Text('GİRİŞE DÖN', style: TextStyle(fontSize: 16)),
        ),
      ],
    );
  }
}
