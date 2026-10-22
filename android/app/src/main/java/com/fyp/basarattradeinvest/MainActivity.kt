package com.fyp.basarattradeinvest

import android.Manifest
import android.os.Bundle
import android.os.Build
import android.view.View
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.GravityCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding
import androidx.drawerlayout.widget.DrawerLayout
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.NavHostFragment
import androidx.navigation.navOptions
import androidx.navigation.ui.setupWithNavController
import com.fyp.basarattradeinvest.core.notifications.DeviceRegistrationScheduler
import com.fyp.basarattradeinvest.core.notifications.NotificationBadgeState
import com.fyp.basarattradeinvest.core.notifications.NotificationEvents
import com.fyp.basarattradeinvest.core.notifications.NotificationTarget
import com.fyp.basarattradeinvest.core.session.AuthState
import com.fyp.basarattradeinvest.core.session.SessionEvent
import com.fyp.basarattradeinvest.core.session.SessionManager
import com.fyp.basarattradeinvest.databinding.ActivityMainBinding
import com.fyp.basarattradeinvest.data.repository.NotificationsRepositoryImpl
import com.fyp.basarattradeinvest.data.repository.CommunityRepositoryImpl
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.snackbar.Snackbar
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private var pendingLaunchTarget: NotificationTarget? = null
    private val handledReadIds = mutableSetOf<String>()

    // Screens that legitimately live in a signed-out state; never force these to login.
    private val authFlowDestinations = setOf(
        R.id.splashFragment,
        R.id.onboardingFragment,
        R.id.loginFragment,
        R.id.signUpFragment,
        R.id.emailVerificationFragment,
        R.id.forgotPasswordFragment,
        R.id.verifyResetCodeFragment,
        R.id.resetPasswordFragment
    )
    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* The app remains fully usable when notification permission is denied. */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SessionManager.init(applicationContext)
        pendingLaunchTarget = NotificationTarget.from(intent)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupNavigation()
        observeSession()
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        NotificationTarget.from(intent)?.let(::handleNotificationTarget)
    }

    override fun onResume() {
        super.onResume()
        if (SessionManager.authState.value is AuthState.Authenticated) {
            lifecycleScope.launch { NotificationBadgeState.refresh() }
        }
    }

    private fun setupNavigation() {
        val navHostFragment = supportFragmentManager
            .findFragmentById(R.id.nav_host_fragment) as? NavHostFragment ?: return
        val navController = navHostFragment.navController

        binding.bottomNavigation.setupWithNavController(navController)

        setupDrawer(navController)

        // Show BottomNavigationView only on main app destinations, hide on Splash, Onboarding & Auth screens
        navController.addOnDestinationChangedListener { _, destination, _ ->
            if (destination.id == R.id.nav_home) {
                maybeRequestNotificationPermission()
            }
            pendingLaunchTarget?.let { target ->
                if (SessionManager.authState.value is AuthState.Authenticated &&
                    destination.id != R.id.splashFragment && destination.id != R.id.loginFragment
                ) {
                    pendingLaunchTarget = null
                    handleNotificationTarget(target)
                } else if (SessionManager.authState.value !is AuthState.Authenticated) {
                    pendingLaunchTarget = null
                    rememberPostLoginTarget(target)
                }
            }
            when (destination.id) {
                R.id.splashFragment,
                R.id.onboardingFragment,
                R.id.loginFragment,
                R.id.signUpFragment,
                R.id.emailVerificationFragment,
                R.id.forgotPasswordFragment,
                R.id.verifyResetCodeFragment,
                R.id.resetPasswordFragment,
                R.id.changePasswordFragment,
                R.id.editProfileFragment,
                R.id.riskProfileFragment,
                R.id.notificationPreferencesFragment,
                R.id.alertsFragment,
                R.id.notificationsFragment,
                R.id.chartFullscreenFragment,
                R.id.communityFollowersFragment,
                R.id.communityNotificationsFragment,
                R.id.assistantConversationsFragment,
                R.id.assistantChatFragment,
                R.id.adminCommunityHubFragment,
                R.id.adminReportDetailFragment -> {
                    binding.bottomNavigation.visibility = View.GONE
                }
                else -> {
                    binding.bottomNavigation.visibility = View.VISIBLE
                }
            }
        }
    }

    private var drawerNotificationsBadge: TextView? = null

    private fun setupDrawer(navController: androidx.navigation.NavController) {
        // Keep the drawer locked closed so the left-edge swipe does not open it on every
        // screen; it is opened only from the Home screen's menu button via openDrawer().
        binding.drawerLayout.setDrawerLockMode(DrawerLayout.LOCK_MODE_LOCKED_CLOSED)
        binding.drawerLayout.addDrawerListener(object : DrawerLayout.SimpleDrawerListener() {
            override fun onDrawerOpened(drawerView: View) {
                binding.drawerLayout.setDrawerLockMode(DrawerLayout.LOCK_MODE_UNLOCKED)
                binding.navView.getHeaderView(0)?.let(::refreshDrawerHeader)
            }

            override fun onDrawerClosed(drawerView: View) {
                binding.drawerLayout.setDrawerLockMode(DrawerLayout.LOCK_MODE_LOCKED_CLOSED)
            }
        })

        setupDrawerHeader(navController)
        setupDrawerMenu(navController)
        observeDrawerBadge()

        navController.addOnDestinationChangedListener { _, destination, _ ->
            if (binding.navView.menu.findItem(destination.id) != null) {
                binding.navView.setCheckedItem(destination.id)
            }
        }
    }

    private fun setupDrawerHeader(navController: androidx.navigation.NavController) {
        val header = binding.navView.getHeaderView(0) ?: return
        // The drawer panel spans the full screen height, so its wordmark would sit
        // under the status bar without this inset.
        val headerBasePaddingTop = header.paddingTop
        ViewCompat.setOnApplyWindowInsetsListener(header) { view, insets ->
            val statusBarTop = insets.getInsets(WindowInsetsCompat.Type.statusBars()).top
            view.updatePadding(top = headerBasePaddingTop + statusBarTop)
            insets
        }
        header.findViewById<View>(R.id.btn_drawer_close).setOnClickListener {
            binding.drawerLayout.closeDrawer(GravityCompat.START)
        }
        header.findViewById<View>(R.id.layout_drawer_profile).setOnClickListener {
            binding.drawerLayout.closeDrawer(GravityCompat.START)
            runCatching { navController.navigate(R.id.nav_you) }
        }
        refreshDrawerHeader(header)
    }

    private fun refreshDrawerHeader(header: View) {
        val auth = SessionManager.authState.value as? AuthState.Authenticated
        header.findViewById<TextView>(R.id.tv_drawer_user_name).text =
            auth?.userName?.takeIf { it.isNotBlank() } ?: "Investor"
        header.findViewById<TextView>(R.id.tv_drawer_user_email).text = auth?.userEmail.orEmpty()
    }

    private fun setupDrawerMenu(navController: androidx.navigation.NavController) {
        val menu = binding.navView.menu
        for (i in 0 until menu.size()) {
            val item = menu.getItem(i)
            val action = layoutInflater.inflate(R.layout.drawer_item_action, binding.navView, false)
            item.actionView = action
            if (item.itemId == R.id.notificationsFragment) {
                drawerNotificationsBadge = action.findViewById(R.id.tv_drawer_badge)
            }
        }
        binding.navView.setNavigationItemSelectedListener { item ->
            if (item.itemId == R.id.drawer_logout) {
                binding.drawerLayout.closeDrawer(GravityCompat.START)
                SessionManager.clearSession()
                return@setNavigationItemSelectedListener true
            }
            val handled = runCatching { navController.navigate(item.itemId) }.isSuccess
            binding.drawerLayout.closeDrawer(GravityCompat.START)
            handled
        }
    }

    private fun observeDrawerBadge() {
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                NotificationBadgeState.unreadCount.collect { count ->
                    val badge = drawerNotificationsBadge ?: return@collect
                    badge.visibility = if (count > 0) View.VISIBLE else View.GONE
                    badge.text = if (count > 99) "99+" else count.toString()
                }
            }
        }
    }

    /** Opens the navigation drawer. Called from the Home screen's menu button. */
    fun openDrawer() {
        binding.drawerLayout.setDrawerLockMode(DrawerLayout.LOCK_MODE_UNLOCKED)
        binding.drawerLayout.openDrawer(GravityCompat.START)
    }

    private fun observeSession() {
        val navHostFragment = supportFragmentManager
            .findFragmentById(R.id.nav_host_fragment) as? NavHostFragment ?: return
        val navController = navHostFragment.navController

        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                launch {
                    SessionManager.authState.collect { state ->
                        if (state is AuthState.Authenticated) {
                            DeviceRegistrationScheduler.requestCurrentToken(applicationContext)
                            lifecycleScope.launch { NotificationBadgeState.refresh() }
                            return@collect
                        }
                        // Expired or unauthenticated: route back to login instead of leaving a
                        // protected screen showing an on-screen "not authenticated" error.
                        if (state != AuthState.SessionExpired && state != AuthState.Unauthenticated) {
                            return@collect
                        }
                        val currentDestination = navController.currentDestination ?: return@collect
                        if (currentDestination.id in authFlowDestinations) return@collect

                        SessionManager.rememberPostLoginDestination(
                            destinationId = currentDestination.id,
                            arguments = navController.currentBackStackEntry?.arguments
                        )
                        Toast.makeText(
                            this@MainActivity,
                            if (state == AuthState.SessionExpired) {
                                "Your session expired. Please sign in again."
                            } else {
                                "Please sign in to continue."
                            },
                            Toast.LENGTH_LONG
                        ).show()
                        navController.navigate(
                            R.id.loginFragment,
                            null,
                            navOptions {
                                popUpTo(navController.graph.id) { inclusive = false }
                                launchSingleTop = true
                            }
                        )
                    }
                }

                launch {
                    SessionManager.sessionEvents.collect { event ->
                        if (event == SessionEvent.RefreshTemporarilyUnavailable) {
                            Toast.makeText(
                                this@MainActivity,
                                "Couldn't verify your session. Check your connection and try again.",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    }
                }

                launch {
                    NotificationEvents.foregroundNotifications.collect { target ->
                        lifecycleScope.launch { NotificationBadgeState.refresh() }
                        Snackbar.make(binding.root, target.body, Snackbar.LENGTH_LONG)
                            .setAction("View") { handleNotificationTarget(target) }
                            .show()
                    }
                }
            }
        }
    }

    private fun maybeRequestNotificationPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
            android.content.pm.PackageManager.PERMISSION_GRANTED ||
            SessionManager.wasNotificationPermissionAsked()
        ) return

        SessionManager.setNotificationPermissionAsked()
        MaterialAlertDialogBuilder(this)
            .setTitle("Stay up to date")
            .setMessage("Get timely price alerts, portfolio risk updates, and community notifications.")
            .setPositiveButton("Enable") { _, _ ->
                notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
            .setNegativeButton("Not now", null)
            .show()
    }

    private fun rememberPostLoginTarget(target: NotificationTarget) {
        val (destinationId, arguments) = target.destination()
        SessionManager.rememberPostLoginDestination(destinationId, arguments)
    }

    private fun handleNotificationTarget(target: NotificationTarget) {
        if (SessionManager.authState.value !is AuthState.Authenticated) {
            rememberPostLoginTarget(target)
            val navHost = supportFragmentManager.findFragmentById(R.id.nav_host_fragment) as? NavHostFragment
            val navController = navHost?.navController ?: return
            if (navController.currentDestination?.id != R.id.loginFragment) {
                runCatching { navController.navigate(R.id.loginFragment) }
            }
            return
        }

        val (destinationId, arguments) = target.destination()
        val navController = (supportFragmentManager
            .findFragmentById(R.id.nav_host_fragment) as? NavHostFragment)?.navController ?: return
        runCatching { navController.navigate(destinationId, arguments) }
        val notificationId = target.notificationId
        if (!notificationId.isNullOrBlank() && handledReadIds.add(notificationId)) {
            lifecycleScope.launch {
                val result = if (target.screen.equals("COMMUNITY", ignoreCase = true)) {
                    CommunityRepositoryImpl().markNotificationAsRead(notificationId)
                } else {
                    NotificationsRepositoryImpl().markNotificationAsRead(notificationId)
                }
                if (result.isSuccess) {
                    if (target.screen.equals("COMMUNITY", ignoreCase = true)) {
                        NotificationBadgeState.markCommunityRead()
                    } else {
                        NotificationBadgeState.markRead()
                    }
                } else NotificationBadgeState.refresh()
            }
        }
    }

    private fun NotificationTarget.destination(): Pair<Int, Bundle?> = when (screen?.uppercase()) {
        "STOCK" -> if (!symbol.isNullOrBlank()) {
            R.id.stockDetailFragment to Bundle().apply { putString("symbol", symbol) }
        } else R.id.notificationsFragment to null
        "RISK" -> R.id.riskAnalyticsFragment to null
        "COMMUNITY" -> R.id.communityNotificationsFragment to null
        "ALERTS" -> R.id.alertsFragment to null
        "NOTIFICATIONS" -> R.id.notificationsFragment to null
        else -> R.id.notificationsFragment to null
    }
}
