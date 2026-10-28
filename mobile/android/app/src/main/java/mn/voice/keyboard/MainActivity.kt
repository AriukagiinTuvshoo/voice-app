package mn.voice.keyboard

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

class MainActivity : Activity() {

    private lateinit var micStatusTv: TextView
    private lateinit var serverInput: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val scroll = ScrollView(this).apply {
            setBackgroundColor(Color.parseColor("#090D16"))
        }

        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(28), dp(20), dp(40))
        }

        val title = TextView(this).apply {
            text = "🎤 VOICE Keyboard"
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 24f)
            typeface = Typeface.DEFAULT_BOLD
        }
        container.addView(title)

        val subtitle = TextView(this).apply {
            text = "Chrome, Google хайлт, Facebook, Messenger, Instagram зэрэг бүх апп дээр Монгол, Англи, Япон хэлээр шууд ярьж бичих гар."
            setTextColor(Color.parseColor("#94A3B8"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            setPadding(0, dp(6), 0, dp(18))
        }
        container.addView(subtitle)

        // Step 1: Microphone Permission
        micStatusTv = TextView(this).apply {
            setTextColor(Color.parseColor("#10B981"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            setPadding(0, 0, 0, dp(8))
        }
        updateMicPermissionLabel()

        container.addView(
            buildStepCard(
                stepTitle = "1-р алхам: Микрофон зөвшөөрөл өгөх",
                stepDesc = "Дуу хоолойг танихын тулд микрофон ашиглах зөвшөөрөл олгоно уу.",
                extraView = micStatusTv,
                buttonText = "🎤 Микрофон зөвшөөрөх",
                buttonColor = "#6366F1"
            ) {
                requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 101)
            }
        )

        // Step 2: Enable Keyboard in Android Settings
        container.addView(
            buildStepCard(
                stepTitle = "2-р алхам: VOICE Keyboard-ийг идэвхжүүлэх",
                stepDesc = "Системийн гарын жагсаалтаас 'VOICE Keyboard'-ийг асаана уу.",
                buttonText = "⚙️ Гарын тохиргоо нээх",
                buttonColor = "#3B82F6"
            ) {
                startActivity(Intent(Settings.ACTION_INPUT_METHOD_SETTINGS))
            }
        )

        // Step 3: Select VOICE Keyboard as active IME
        container.addView(
            buildStepCard(
                stepTitle = "3-р алхам: VOICE Keyboard сонгох",
                stepDesc = "Доорх товчийг дараад 'VOICE Keyboard'-ийг үндсэн гараар сонгоно уу.",
                buttonText = "⌨️ Гар солих цэс нээх",
                buttonColor = "#10B981"
            ) {
                val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
                imm.showInputMethodPicker()
            }
        )

        // Step 4: Test Input Box
        val testBox = EditText(this).apply {
            hint = "Энд дарж VOICE Keyboard-ийн 🎤 товчоор ярьж шалгана уу..."
            setHintTextColor(Color.parseColor("#64748B"))
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            setPadding(dp(14), dp(14), dp(14), dp(14))
            background = cardBg("#0F172A", stroke = "#334155")
        }
        container.addView(
            buildStepCard(
                stepTitle = "4-р алхам: Энд шууд туршиж бичих",
                stepDesc = "Доорх нүдэн дээр дарахад VOICE гар гарч ирнэ. 🎤 товч дээр дараад ярина уу!",
                extraView = testBox
            )
        )

        // Step 5: Server URL Configuration
        serverInput = EditText(this).apply {
            setText(Prefs.server(this@MainActivity))
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            setSingleLine(true)
            setPadding(dp(12), dp(10), dp(12), dp(10))
            background = cardBg("#0F172A", stroke = "#334155")
        }
        container.addView(
            buildStepCard(
                stepTitle = "🌐 VOICE AI Серверийн хаяг",
                stepDesc = "Таны Render.com дээрх онлайн VOICE серверийн URL хаяг:",
                extraView = serverInput,
                buttonText = "💾 Сервер хадгалах",
                buttonColor = "#475569"
            ) {
                Prefs.setServer(this, serverInput.text.toString())
                Toast.makeText(this, "Серверийн хаяг хадгалагдлаа!", Toast.LENGTH_SHORT).show()
            }
        )

        scroll.addView(container)
        setContentView(scroll)
    }

    override fun onResume() {
        super.onResume()
        updateMicPermissionLabel()
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        updateMicPermissionLabel()
    }

    private fun updateMicPermissionLabel() {
        val granted = checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        micStatusTv.text = if (granted) "✅ Микрофоны зөвшөөрөл нээлттэй байна" else "⚠️ Микрофоны зөвшөөрөл өгөөгүй байна"
        micStatusTv.setTextColor(Color.parseColor(if (granted) "#10B981" else "#F59E0B"))
    }

    private fun buildStepCard(
        stepTitle: String,
        stepDesc: String,
        extraView: View? = null,
        buttonText: String? = null,
        buttonColor: String = "#6366F1",
        onClick: (() -> Unit)? = null
    ): View {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(16), dp(16), dp(16))
            background = cardBg("#131B2E", stroke = "#1E293B")
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                bottomMargin = dp(14)
            }
        }

        val t = TextView(this).apply {
            text = stepTitle
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            typeface = Typeface.DEFAULT_BOLD
        }
        card.addView(t)

        val d = TextView(this).apply {
            text = stepDesc
            setTextColor(Color.parseColor("#94A3B8"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            setPadding(0, dp(4), 0, dp(10))
        }
        card.addView(d)

        if (extraView != null) {
            card.addView(extraView)
        }

        if (buttonText != null && onClick != null) {
            val btn = Button(this).apply {
                text = buttonText
                setTextColor(Color.WHITE)
                isAllCaps = false
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
                typeface = Typeface.DEFAULT_BOLD
                background = cardBg(buttonColor)
                gravity = Gravity.CENTER
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    dp(44)
                ).apply {
                    topMargin = dp(8)
                }
                setOnClickListener { onClick() }
            }
            card.addView(btn)
        }

        return card
    }

    private fun cardBg(hex: String, stroke: String? = null): GradientDrawable {
        return GradientDrawable().apply {
            setColor(Color.parseColor(hex))
            cornerRadius = dp(14).toFloat()
            if (stroke != null) {
                setStroke(dp(1), Color.parseColor(stroke))
            }
        }
    }

    private fun dp(v: Int): Int =
        TypedValue.applyDimension(
            TypedValue.COMPLEX_UNIT_DIP,
            v.toFloat(),
            resources.displayMetrics
        ).toInt()
}
