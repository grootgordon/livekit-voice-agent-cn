package io.livekit.voiceagentdemo.data

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "livekit_settings")

/** 用 DataStore 持久化连接配置，下次打开自动回填。 */
class SettingsRepository(private val context: Context) {

    private object Keys {
        val PROFILE = stringPreferencesKey("profile")
        val URL = stringPreferencesKey("url")
        val API_KEY = stringPreferencesKey("api_key")
        val API_SECRET = stringPreferencesKey("api_secret")
        val AGENT_NAME = stringPreferencesKey("agent_name")
    }

    val config: Flow<LiveKitConfig> = context.dataStore.data.map { it.toConfig() }

    suspend fun save(config: LiveKitConfig) {
        context.dataStore.edit { prefs ->
            prefs[Keys.PROFILE] = config.profile.name
            prefs[Keys.URL] = config.url.trim()
            prefs[Keys.API_KEY] = config.apiKey.trim()
            prefs[Keys.API_SECRET] = config.apiSecret.trim()
            prefs[Keys.AGENT_NAME] = config.agentName.trim()
        }
    }

    private fun Preferences.toConfig(): LiveKitConfig {
        val profile = Profile.fromName(this[Keys.PROFILE])
        return LiveKitConfig(
            profile = profile,
            url = this[Keys.URL] ?: Defaults.forProfile(profile).url,
            apiKey = this[Keys.API_KEY] ?: Defaults.forProfile(profile).apiKey,
            apiSecret = this[Keys.API_SECRET] ?: Defaults.forProfile(profile).apiSecret,
            agentName = this[Keys.AGENT_NAME] ?: Defaults.AGENT_NAME,
        )
    }
}
