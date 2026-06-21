package io.livekit.voiceagentdemo.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import io.livekit.voiceagentdemo.data.Defaults
import io.livekit.voiceagentdemo.data.LiveKitConfig
import io.livekit.voiceagentdemo.data.Profile

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConnectScreen(
    initial: LiveKitConfig,
    onStart: (LiveKitConfig) -> Unit,
) {
    // 用 remember（非 rememberSaveable）避免 enum 需自定义 Saver；配置从 DataStore 回填。
    var profile by remember { mutableStateOf(initial.profile) }
    var url by remember { mutableStateOf(initial.url) }
    var apiKey by remember { mutableStateOf(initial.apiKey) }
    var apiSecret by remember { mutableStateOf(initial.apiSecret) }
    var agentName by remember { mutableStateOf(initial.agentName) }
    var showSecret by remember { mutableStateOf(false) }

    fun applyProfile(p: Profile) {
        val preset = Defaults.forProfile(p)
        profile = p
        url = preset.url
        apiKey = preset.apiKey
        apiSecret = preset.apiSecret
    }

    val config = LiveKitConfig(profile, url, apiKey, apiSecret, agentName)

    Scaffold(topBar = { TopAppBar(title = { Text("LiveKit 语音助手") }) }) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .padding(20.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("选择连接方式", style = MaterialTheme.typography.labelLarge)

            SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
                Profile.entries.forEachIndexed { index, p ->
                    SegmentedButton(
                        selected = profile == p,
                        onClick = { applyProfile(p) },
                        shape = SegmentedButtonDefaults.itemShape(index, Profile.entries.size),
                    ) { Text(p.displayName) }
                }
            }

            Card {
                Text(
                    if (profile == Profile.LOCAL) {
                        "本地模式：填运行 livekit-server 的电脑局域网 IP，如 ws://192.168.1.100:7880\n" +
                            "默认 devkey / secret（livekit-server --dev 自带）。\n" +
                            "模拟器连宿主机用 ws://10.0.2.2:7880。"
                    } else {
                        "Cloud 模式：从 cloud.livekit.io → 项目 Settings 获取\n" +
                            "URL（wss://…）、API Key、API Secret。"
                    },
                    modifier = Modifier.padding(12.dp),
                    style = MaterialTheme.typography.bodySmall,
                )
            }

            OutlinedTextField(
                value = url,
                onValueChange = { url = it },
                label = { Text("LiveKit URL") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = apiKey,
                onValueChange = { apiKey = it },
                label = { Text("API Key") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = apiSecret,
                onValueChange = { apiSecret = it },
                label = { Text("API Secret") },
                singleLine = true,
                visualTransformation = if (showSecret) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    TextButton(onClick = { showSecret = !showSecret }) {
                        Text(if (showSecret) "隐藏" else "显示")
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = agentName,
                onValueChange = { agentName = it },
                label = { Text("Agent 名称") },
                singleLine = true,
                supportingText = { Text("须与 agent-py 的 agent_name 一致，默认 my-agent") },
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(Modifier.height(4.dp))
            Button(
                onClick = { onStart(config) },
                enabled = config.isValid,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 52.dp),
            ) {
                Icon(Icons.Default.Mic, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("开始通话", fontWeight = FontWeight.SemiBold)
            }
        }
    }
}
