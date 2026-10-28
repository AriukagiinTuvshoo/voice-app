package mn.voice.keyboard

import android.content.Context

const val DEFAULT_SERVER = "https://voice-app.onrender.com"

/** Shared settings between the setup app and the keyboard service. */
object Prefs {
    private const val NAME = "voice_keyboard_prefs"

    val LANGUAGES = listOf(
        "mn" to "MN",
        "auto" to "AUTO",
        "en" to "EN",
        "ja" to "JA",
    )

    fun server(c: Context): String =
        c.getSharedPreferences(NAME, Context.MODE_PRIVATE)
            .getString("server", DEFAULT_SERVER)
            ?.trim()
            ?.trimEnd('/')
            .takeUnless { it.isNullOrEmpty() } ?: DEFAULT_SERVER

    fun setServer(c: Context, value: String) {
        c.getSharedPreferences(NAME, Context.MODE_PRIVATE).edit()
            .putString("server", value.trim().trimEnd('/'))
            .apply()
    }

    fun language(c: Context): String =
        c.getSharedPreferences(NAME, Context.MODE_PRIVATE).getString("language", "mn") ?: "mn"

    fun setLanguage(c: Context, value: String) {
        c.getSharedPreferences(NAME, Context.MODE_PRIVATE).edit().putString("language", value).apply()
    }

    fun nextLanguage(c: Context): String {
        val current = language(c)
        val idx = LANGUAGES.indexOfFirst { it.first == current }
        val next = LANGUAGES[(idx + 1).mod(LANGUAGES.size)].first
        setLanguage(c, next)
        return next
    }

    fun languageLabel(code: String): String =
        LANGUAGES.firstOrNull { it.first == code }?.second ?: code.uppercase()
}
