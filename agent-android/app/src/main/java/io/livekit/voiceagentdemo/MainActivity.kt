package io.livekit.voiceagentdemo

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import io.livekit.voiceagentdemo.data.Defaults
import io.livekit.voiceagentdemo.data.LiveKitConfig
import io.livekit.voiceagentdemo.data.SettingsRepository
import io.livekit.voiceagentdemo.token.TokenSigner
import io.livekit.voiceagentdemo.ui.CallScreen
import io.livekit.voiceagentdemo.ui.ConnectScreen
import io.livekit.voiceagentdemo.ui.theme.VoiceAgentTheme
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private val settings by lazy { SettingsRepository(applicationContext) }

    /** 权限授予是异步回调；授予后用最近一次 composition 捕获的 goCall 进入通话。 */
    private var pendingConfig: LiveKitConfig? = null
    private var goCall: (LiveKitConfig) -> Unit = {}

    private val requestMicPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        val cfg = pendingConfig
        if (granted && cfg != null) goCall(cfg)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            VoiceAgentTheme {
                val savedConfig by settings.config.collectAsState(initial = Defaults.CLOUD)
                var screen by remember { mutableStateOf<Screen>(Screen.Connect) }
                var callArgs by remember { mutableStateOf<Pair<String, String>?>(null) }
                val scope = rememberCoroutineScope()

                goCall = { cfg ->
                    val token = TokenSigner.sign(cfg.apiKey, cfg.apiSecret, cfg.agentName)
                    callArgs = cfg.url to token
                    screen = Screen.Call
                }

                when (screen) {
                    Screen.Connect -> ConnectScreen(
                        initial = savedConfig,
                        onStart = { cfg ->
                            scope.launch { settings.save(cfg) }
                            if (hasMicPermission()) {
                                goCall(cfg)
                            } else {
                                pendingConfig = cfg
                                requestMicPermission.launch(Manifest.permission.RECORD_AUDIO)
                            }
                        },
                    )

                    Screen.Call -> {
                        val (url, token) = callArgs!!
                        CallScreen(
                            url = url,
                            token = token,
                            onHangup = { screen = Screen.Connect },
                        )
                    }
                }
            }
        }
    }

    private fun hasMicPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    private sealed class Screen {
        data object Connect : Screen()
        data object Call : Screen()
    }
}
