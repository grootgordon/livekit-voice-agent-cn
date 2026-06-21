package io.livekit.voiceagentdemo.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CallEnd
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.livekit.android.compose.local.RoomScope
import io.livekit.android.compose.state.AgentState
import io.livekit.android.compose.state.rememberVoiceAssistant
import io.livekit.android.compose.ui.audio.VoiceAssistantBarVisualizer

@Composable
fun CallScreen(
    url: String,
    token: String,
    onHangup: () -> Unit,
) {
    var errorMsg by remember { mutableStateOf<String?>(null) }

    // audio=true：连接成功后自动发布麦克风；订阅的远端音频（agent TTS）自动播放。
    // 退出本 Composable 时 RoomScope 默认 disconnectOnDispose=true，自动断开。
    RoomScope(
        url = url,
        token = token,
        audio = true,
        connect = true,
        onError = { _, e -> errorMsg = e?.message ?: "连接出错" },
    ) {
        CallContent(errorMsg = errorMsg, onHangup = onHangup)
    }
}

@Composable
private fun CallContent(errorMsg: String?, onHangup: () -> Unit) {
    val voiceAssistant = rememberVoiceAssistant()

    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.SpaceBetween,
        ) {
            Spacer(Modifier.height(24.dp))

            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("Agent 已就绪", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                Text(
                    "状态：${voiceAssistant.state.label()}",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                errorMsg?.let {
                    Spacer(Modifier.height(8.dp))
                    Text(it, color = MaterialTheme.colorScheme.error, fontSize = 13.sp)
                }
            }

            VoiceAssistantBarVisualizer(
                voiceAssistant = voiceAssistant,
                brush = SolidColor(MaterialTheme.colorScheme.primary),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(160.dp),
            )

            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    "直接开口说话即可",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 13.sp,
                )
                Spacer(Modifier.height(16.dp))
                FilledIconButton(
                    onClick = onHangup,
                    modifier = Modifier.size(72.dp),
                    shape = CircleShape,
                    colors = IconButtonDefaults.filledIconButtonColors(
                        containerColor = MaterialTheme.colorScheme.error,
                    ),
                ) {
                    Icon(Icons.Default.CallEnd, contentDescription = "挂断", modifier = Modifier.size(32.dp))
                }
                Spacer(Modifier.height(32.dp))
            }
        }
    }
}

private fun AgentState?.label(): String = when (this) {
    AgentState.CONNECTING -> "连接中"
    AgentState.INITIALIZING -> "初始化"
    AgentState.LISTENING -> "聆听中"
    AgentState.THINKING -> "思考中"
    AgentState.SPEAKING -> "说话中"
    else -> "—"
}
