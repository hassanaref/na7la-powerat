package com.powerk.app

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.fragment.app.FragmentActivity

class MainActivity : FragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        Server.init(this)
        Lang.init(this)
        Lang.applyStored(this)
        setContent {
            PowerkTheme {
                PowerkApp()
            }
        }
    }
}
