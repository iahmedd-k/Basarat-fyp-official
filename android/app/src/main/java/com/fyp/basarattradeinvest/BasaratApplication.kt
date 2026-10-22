package com.fyp.basarattradeinvest

import android.app.Application
import com.fyp.basarattradeinvest.core.notifications.NotificationChannels
import com.fyp.basarattradeinvest.core.session.SessionManager

class BasaratApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        SessionManager.init(this)
        NotificationChannels.create(this)
    }
}
