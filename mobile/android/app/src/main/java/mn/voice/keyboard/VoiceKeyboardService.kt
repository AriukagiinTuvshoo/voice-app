package mn.voice.keyboard

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.inputmethodservice.InputMethodService
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.util.TypedValue
import android.view.Gravity
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView

class VoiceKeyboardService : InputMethodService() {

    private val mainHandler = Handler(Looper.getMainLooper())
    private var recorder: WavRecorder? = null

    private var statusLabel: TextView? = null
    private var micButton: LinearLayout? = null
    private var micCircle: FrameLayout? = null
    private var langButton: TextView? = null
    private var levelBars: List<View> = emptyList()
    private var shiftActive = false
    private val letterKeyViews = mutableListOf<TextView>()

    private val mnRows = listOf(
        listOf("ф", "ц", "у", "ж", "э", "н", "г", "ш", "ү", "з", "к", "ъ"),
        listOf("й", "ы", "б", "ө", "а", "х", "р", "о", "л", "д", "п"),
        listOf("я", "ч", "ё", "с", "м", "и", "т", "ь", "в", "ю", "е")
    )

    private var backspaceRepeatRunnable: Runnable? = null

    override fun onCreateInputView(): View {
        letterKeyViews.clear()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#0B0F19"))
            setPadding(dp(6), dp(8), dp(6), dp(12))
        }

        // 1. Top VOICE AI Dictation Bar
        root.addView(buildVoiceToolbar())

        // 2. Mongolian Cyrillic Keyboard Rows
        mnRows.forEachIndexed { rowIndex, keys ->
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    dp(44)
                ).apply {
                    topMargin = dp(5)
                }
            }

            if (rowIndex == 2) {
                // Shift Key on left of 3rd row
                row.addView(buildActionKey("⇧", weight = 1.3f, bgColor = "#1E293B") {
                    shiftActive = !shiftActive
                    updateShiftLabels()
                })
            }

            for (k in keys) {
                val tv = buildLetterKey(k)
                letterKeyViews.add(tv)
                row.addView(tv)
            }

            if (rowIndex == 2) {
                // Backspace Key on right of 3rd row
                row.addView(buildBackspaceKey())
            }

            root.addView(row)
        }

        // 3. Bottom Row: Globe (Switch IME) | Language | Spacebar | Comma/Period | Search/Enter
        root.addView(buildBottomRow())

        return root
    }

    private fun buildVoiceToolbar(): View {
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(8), dp(6), dp(8), dp(6))
            background = roundedRect("#131B2E", dp(16), strokeColor = "#2E3A59", strokeWidth = dp(1))
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                bottomMargin = dp(4)
            }
        }

        // Language selector pill (MN / AUTO / EN / JA)
        val langTv = TextView(this).apply {
            val code = Prefs.language(this@VoiceKeyboardService)
            text = "🌐 ${Prefs.languageLabel(code)}"
            setTextColor(Color.parseColor("#A5B4FC"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f)
            typeface = Typeface.DEFAULT_BOLD
            setPadding(dp(10), dp(7), dp(10), dp(7))
            background = roundedRect("#1E293B", dp(12))
            setOnClickListener {
                vibrate(20)
                val next = Prefs.nextLanguage(this@VoiceKeyboardService)
                text = "🌐 ${Prefs.languageLabel(next)}"
                statusLabel?.text = when (next) {
                    "mn" -> "Монгол (+Англи/Япон) • Дарж ярина уу"
                    "auto" -> "Автомат (MN/EN/JA) • Дарж ярина уу"
                    "en" -> "English • Tap mic to speak"
                    else -> "日本語 • マイクを押して話す"
                }
            }
        }
        langButton = langTv
        bar.addView(langTv)

        // Center Mic + Status Capsule
        val micContainer = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(10), dp(6), dp(12), dp(6))
            background = roundedRect("#1E1B4B", dp(999), strokeColor = "#6366F1", strokeWidth = dp(1))
            layoutParams = LinearLayout.LayoutParams(
                0,
                LinearLayout.LayoutParams.WRAP_CONTENT,
                1f
            ).apply {
                marginStart = dp(8)
                marginEnd = dp(8)
            }
            setOnClickListener {
                toggleVoiceRecording()
            }
        }
        micButton = micContainer

        val circle = FrameLayout(this).apply {
            background = roundedRect("#6366F1", dp(999))
            layoutParams = LinearLayout.LayoutParams(dp(32), dp(32))
        }
        val micIcon = TextView(this).apply {
            text = "🎤"
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            gravity = Gravity.CENTER
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
        }
        circle.addView(micIcon)
        micCircle = circle
        micContainer.addView(circle)

        val status = TextView(this).apply {
            text = "Дарж ярих (VOICE AI)"
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            typeface = Typeface.DEFAULT_BOLD
            setPadding(dp(10), 0, dp(6), 0)
            maxLines = 1
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }
        statusLabel = status
        micContainer.addView(status)

        // Mini audio level bars
        val barsWrap = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val bars = mutableListOf<View>()
        for (i in 0 until 4) {
            val v = View(this).apply {
                background = roundedRect("#818CF8", dp(2))
                layoutParams = LinearLayout.LayoutParams(dp(3), dp(6)).apply {
                    marginStart = dp(2)
                }
            }
            bars.add(v)
            barsWrap.addView(v)
        }
        levelBars = bars
        micContainer.addView(barsWrap)

        bar.addView(micContainer)

        // Settings gear button
        val gearBtn = TextView(this).apply {
            text = "⚙️"
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            setPadding(dp(8), dp(6), dp(8), dp(6))
            background = roundedRect("#1E293B", dp(12))
            setOnClickListener {
                val intent = Intent(this@VoiceKeyboardService, MainActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                startActivity(intent)
            }
        }
        bar.addView(gearBtn)

        return bar
    }

    private fun buildLetterKey(letter: String): TextView {
        return TextView(this).apply {
            text = if (shiftActive) letter.uppercase() else letter
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            gravity = Gravity.CENTER
            background = roundedRect("#1E293B", dp(7))
            layoutParams = LinearLayout.LayoutParams(
                0,
                LinearLayout.LayoutParams.MATCH_PARENT,
                1f
            ).apply {
                marginStart = dp(2)
                marginEnd = dp(2)
            }
            setOnClickListener {
                vibrate(12)
                val out = if (shiftActive) letter.uppercase() else letter
                currentInputConnection?.commitText(out, 1)
                if (shiftActive) {
                    shiftActive = false
                    updateShiftLabels()
                }
            }
        }
    }

    private fun buildBackspaceKey(): View {
        return TextView(this).apply {
            text = "⌫"
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f)
            gravity = Gravity.CENTER
            background = roundedRect("#334155", dp(7))
            layoutParams = LinearLayout.LayoutParams(
                0,
                LinearLayout.LayoutParams.MATCH_PARENT,
                1.4f
            ).apply {
                marginStart = dp(2)
                marginEnd = dp(2)
            }
            setOnTouchListener { _, event ->
                when (event.action) {
                    MotionEvent.ACTION_DOWN -> {
                        vibrate(15)
                        deleteOneChar()
                        val r = object : Runnable {
                            override fun run() {
                                deleteOneChar()
                                mainHandler.postDelayed(this, 65)
                            }
                        }
                        backspaceRepeatRunnable = r
                        mainHandler.postDelayed(r, 380)
                        true
                    }
                    MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                        backspaceRepeatRunnable?.let { mainHandler.removeCallbacks(it) }
                        backspaceRepeatRunnable = null
                        true
                    }
                    else -> false
                }
            }
        }
    }

    private fun deleteOneChar() {
        val ic = currentInputConnection ?: return
        val selected = ic.getSelectedText(0)
        if (!selected.isNullOrEmpty()) {
            ic.commitText("", 1)
        } else {
            ic.deleteSurroundingText(1, 0)
        }
    }

    private fun buildBottomRow(): View {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(46)
            ).apply {
                topMargin = dp(6)
            }
        }

        // Switch keyboard (Globe)
        row.addView(buildActionKey("🌐 Гар", weight = 1.3f, bgColor = "#1E293B") {
            val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                switchToNextInputMethod(false)
            } else {
                imm.showInputMethodPicker()
            }
        })

        // Comma
        row.addView(buildActionKey(",", weight = 0.8f, bgColor = "#1E293B") {
            currentInputConnection?.commitText(", ", 1)
        })

        // Spacebar
        row.addView(buildActionKey("Зай (Space)", weight = 3.5f, bgColor = "#334155") {
            currentInputConnection?.commitText(" ", 1)
        })

        // Period
        row.addView(buildActionKey(".", weight = 0.8f, bgColor = "#1E293B") {
            currentInputConnection?.commitText(". ", 1)
        })

        // Enter / Search action key
        row.addView(buildActionKey("🔍 Хайх / ↵", weight = 1.6f, bgColor = "#4F46E5") {
            val ic = currentInputConnection ?: return@buildActionKey
            val info = currentInputEditorInfo
            val action = info?.imeOptions?.and(EditorInfo.IME_MASK_ACTION) ?: EditorInfo.IME_ACTION_NONE
            if (action != EditorInfo.IME_ACTION_NONE && action != EditorInfo.IME_ACTION_UNSPECIFIED) {
                if (!ic.performEditorAction(action)) {
                    ic.sendKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_ENTER))
                    ic.sendKeyEvent(KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_ENTER))
                }
            } else {
                ic.sendKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_ENTER))
                ic.sendKeyEvent(KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_ENTER))
            }
        })

        return row
    }

    private fun buildActionKey(
        label: String,
        weight: Float,
        bgColor: String,
        onClick: () -> Unit
    ): TextView {
        return TextView(this).apply {
            text = label
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            typeface = Typeface.DEFAULT_BOLD
            gravity = Gravity.CENTER
            background = roundedRect(bgColor, dp(8))
            layoutParams = LinearLayout.LayoutParams(
                0,
                LinearLayout.LayoutParams.MATCH_PARENT,
                weight
            ).apply {
                marginStart = dp(2)
                marginEnd = dp(2)
            }
            setOnClickListener {
                vibrate(15)
                onClick()
            }
        }
    }

    private fun updateShiftLabels() {
        letterKeyViews.forEach { tv ->
            val current = tv.text.toString()
            tv.text = if (shiftActive) current.uppercase() else current.lowercase()
        }
    }

    private fun toggleVoiceRecording() {
        val currentRec = recorder
        if (currentRec != null && currentRec.isRecording) {
            finishAndTranscribe()
        } else {
            startVoiceRecording()
        }
    }

    private fun startVoiceRecording() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            statusLabel?.text = "⚠️ Микрофон зөвшөөрөл өгнө үү (Дарна уу)"
            val intent = Intent(this, MainActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            startActivity(intent)
            return
        }

        vibrate(35)
        val rec = WavRecorder(
            onLevel = { lvl ->
                mainHandler.post {
                    levelBars.forEachIndexed { idx, bar ->
                        val h = dp((6 + (lvl * 18) + (idx % 2) * 3).toInt().coerceIn(5, 24))
                        val lp = bar.layoutParams
                        lp.height = h
                        bar.layoutParams = lp
                    }
                }
            },
            onAutoStop = {
                mainHandler.post {
                    finishAndTranscribe()
                }
            }
        )

        if (!rec.start()) {
            statusLabel?.text = "Микрофон завгүй байна. Дахин дарна уу"
            return
        }

        recorder = rec
        micCircle?.background = roundedRect("#EF4444", dp(999))
        micButton?.background = roundedRect("#3B0A0A", dp(999), strokeColor = "#EF4444", strokeWidth = dp(1))
        statusLabel?.text = "🔴 Сонсож байна... (Зогсоох бол дар)"
    }

    private fun finishAndTranscribe() {
        val rec = recorder ?: return
        recorder = null
        val wav = rec.stop()
        vibrate(25)

        resetMicVisuals("⏳ Боловсруулж байна...")

        if (!WavRecorder.hasAudio(wav)) {
            resetMicVisuals("Яриа сонсогдсонгүй • Дарж ярих")
            return
        }

        val serverUrl = Prefs.server(this)
        val lang = Prefs.language(this)

        Thread {
            try {
                val text = SttClient.transcribe(serverUrl, wav, lang)
                mainHandler.post {
                    val ic = currentInputConnection
                    if (ic != null && text.isNotEmpty()) {
                        ic.commitText("$text ", 1)
                        vibrate(40)
                        resetMicVisuals("✅ Бичигдлээ! • Дарж ярих")
                    } else {
                        resetMicVisuals("Дарж ярих (VOICE AI)")
                    }
                }
            } catch (e: SttClient.SttException) {
                mainHandler.post {
                    resetMicVisuals("⚠️ ${e.message ?: "Алдаа гарлаа"}")
                }
            }
        }.start()
    }

    private fun resetMicVisuals(message: String) {
        micCircle?.background = roundedRect("#6366F1", dp(999))
        micButton?.background = roundedRect("#1E1B4B", dp(999), strokeColor = "#6366F1", strokeWidth = dp(1))
        statusLabel?.text = message
        levelBars.forEach { bar ->
            val lp = bar.layoutParams
            lp.height = dp(6)
            bar.layoutParams = lp
        }
    }

    override fun onFinishInputView(finishingInput: Boolean) {
        super.onFinishInputView(finishingInput)
        recorder?.cancel()
        recorder = null
    }

    private fun vibrate(ms: Long) {
        try {
            val v = getSystemService(VIBRATOR_SERVICE) as? Vibrator ?: return
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                v.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                v.vibrate(ms)
            }
        } catch (_: Exception) {
        }
    }

    private fun roundedRect(
        fillHex: String,
        radiusPx: Int,
        strokeColor: String? = null,
        strokeWidth: Int = 0
    ): GradientDrawable {
        return GradientDrawable().apply {
            setColor(Color.parseColor(fillHex))
            cornerRadius = radiusPx.toFloat()
            if (strokeColor != null && strokeWidth > 0) {
                setStroke(strokeWidth, Color.parseColor(strokeColor))
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
