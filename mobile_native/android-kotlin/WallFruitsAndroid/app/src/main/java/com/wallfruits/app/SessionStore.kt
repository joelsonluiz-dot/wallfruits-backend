package com.wallfruits.app

import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SessionStore @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val prefs = context.getSharedPreferences("wallfruits_session", Context.MODE_PRIVATE)

    var accessToken: String?
        get() = prefs.getString("access_token", null)
        set(value) {
            prefs.edit().putString("access_token", value).apply()
        }

    var userName: String?
        get() = prefs.getString("user_name", null)
        set(value) {
            prefs.edit().putString("user_name", value).apply()
        }

    fun clear() {
        prefs.edit().clear().apply()
    }
}
