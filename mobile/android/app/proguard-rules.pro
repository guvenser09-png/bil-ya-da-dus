# Flutter
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }

# Firebase
-keep class com.google.firebase.** { *; }
-keep class com.google.android.gms.** { *; }

# AdMob
-keep class com.google.android.gms.ads.** { *; }

# Hive
-keep class com.hive.** { *; }

# Keep model classes
-keep class com.bilyadadus.** { *; }

# Kotlin
-keep class kotlin.** { *; }
-dontwarn kotlin.**

# Play Core (Flutter deferred components) — bu uygulama PARCALI INDIRME
# kullanmiyor; Flutter motoru siniflari yine de referansliyor. Kural olmadan
# R8 "Missing class com.google.android.play.core.**" ile derlemeyi kirar.
-dontwarn com.google.android.play.core.**
-keep class com.google.android.play.core.** { *; }
