# LiveKit Android SDK
-keep class io.livekit.** { *; }
-keepclassmembers class io.livekit.** { *; }

# Protobuf（livekit-server 与协议定义）
-keep class livekit.** { *; }
-keep class com.google.protobuf.** { *; }

# JWT（端内签 token 用）
-keep class com.auth0.jwt.** { *; }
-keep class com.auth0.jwk.** { *; }

# WebRTC（LiveKit 内部使用的 shade 包）
-keep class livekit.org.webrtc.** { *; }
-keep class org.webrtc.** { *; }
