package io.livekit.voiceagentdemo.token

import com.auth0.jwt.JWT
import com.auth0.jwt.algorithms.Algorithm
import java.util.Date
import kotlin.random.Random

/**
 * 端内签发 LiveKit 连接 token（JWT）。
 *
 * 用 com.auth0:java-jwt 手动构造 claims，结构与 `../agent-web/server/index.mjs`
 * 以及 server-sdk-kotlin 的输出一致：
 *   - video grant：camelCase（roomJoin / canPublish / canSubscribe / canPublishData / room）
 *   - roomConfig.agents[].agentName：camelCase（与 livekit-api / agent-web 一致，已用 livekit-api 对比验证）
 *
 * agentName 必须匹配 agent-py 的 `agent_name`，才会被派发进房。签名是纯本地 HMAC
 * 计算，不联网。
 *
 * 注：不引入 server-sdk-kotlin，因为客户端 SDK（livekit-android）使用 protobuf-javalite，
 * 与 server-sdk-kotlin 的 protobuf-java 同包同类会冲突。
 */
object TokenSigner {

    private val CHARS = ('a'..'z') + ('0'..'9')

    private fun randomId(len: Int = 8): String =
        (1..len).map { CHARS.random(Random) }.joinToString("")

    private const val TTL_MS = 6L * 60 * 60 * 1000 // 6 小时

    fun sign(apiKey: String, apiSecret: String, agentName: String): String {
        require(apiKey.isNotBlank() && apiSecret.isNotBlank()) { "API Key / Secret 不能为空" }
        require(agentName.isNotBlank()) { "Agent 名称不能为空" }

        val identity = "android-${randomId()}"
        val roomName = "room-${randomId()}"
        val now = System.currentTimeMillis()

        val videoGrant = mapOf<String, Any>(
            "roomJoin" to true,
            "room" to roomName,
            "canPublish" to true,
            "canSubscribe" to true,
            "canPublishData" to true,
        )
        val roomConfig = mapOf<String, Any>(
            "agents" to listOf(mapOf("agentName" to agentName)),
        )

        return JWT.create()
            .withIssuer(apiKey)
            .withSubject(identity)
            .withClaim("name", "Android")
            .withIssuedAt(Date(now))
            .withExpiresAt(Date(now + TTL_MS))
            .withClaim("video", videoGrant)
            .withClaim("roomConfig", roomConfig)
            .sign(Algorithm.HMAC256(apiSecret))
    }
}
