package io.livekit.voiceagentdemo.data

/** 传输层预设，与根目录 .livekit.env 的 LIVEKIT_PROFILE(cloud|local) 概念对齐。 */
enum class Profile(val displayName: String) {
    CLOUD("Cloud"),
    LOCAL("本地 Server");

    companion object {
        fun fromName(name: String?): Profile = entries.firstOrNull { it.name == name } ?: CLOUD
    }
}

/** 用户在配置页填写的连接信息。 */
data class LiveKitConfig(
    val profile: Profile,
    val url: String,
    val apiKey: String,
    val apiSecret: String,
    val agentName: String,
) {
    val isValid: Boolean
        get() {
            val urlOk = url.startsWith("ws://", ignoreCase = true) ||
                url.startsWith("wss://", ignoreCase = true)
            return urlOk &&
                apiKey.isNotBlank() &&
                apiSecret.isNotBlank() &&
                agentName.isNotBlank()
        }
}

object Defaults {
    const val AGENT_NAME = "my-agent"

    val LOCAL = LiveKitConfig(
        profile = Profile.LOCAL,
        url = "ws://192.168.1.100:7880",
        apiKey = "devkey",
        apiSecret = "secret",
        agentName = AGENT_NAME,
    )

    val CLOUD = LiveKitConfig(
        profile = Profile.CLOUD,
        url = "",
        apiKey = "",
        apiSecret = "",
        agentName = AGENT_NAME,
    )

    fun forProfile(profile: Profile): LiveKitConfig = when (profile) {
        Profile.CLOUD -> CLOUD
        Profile.LOCAL -> LOCAL
    }
}
