package mn.voice.keyboard

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Records 16 kHz mono PCM16 audio and produces a WAV file.
 * Calls [onLevel] (~10x/sec, background thread) and [onAutoStop] after sustained silence
 * following speech, or after the max duration.
 */
class WavRecorder(
    private val onLevel: (Float) -> Unit,
    private val onAutoStop: () -> Unit,
) {
    private val sampleRate = 16000
    private val silenceStopMs = 2500
    private val maxDurationMs = 60_000

    @Volatile private var running = false
    private var thread: Thread? = null
    private val pcm = ByteArrayOutputStream()

    val isRecording: Boolean get() = running

    @SuppressLint("MissingPermission")
    fun start(): Boolean {
        if (running) return true
        val minBuf = AudioRecord.getMinBufferSize(
            sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
        )
        if (minBuf <= 0) return false

        val recorder = try {
            AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                sampleRate,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                max(minBuf, 8192) * 2
            )
        } catch (e: SecurityException) {
            return false
        } catch (e: IllegalArgumentException) {
            return false
        }

        if (recorder.state != AudioRecord.STATE_INITIALIZED) {
            recorder.release()
            return false
        }

        synchronized(pcm) { pcm.reset() }
        try {
            recorder.startRecording()
        } catch (e: IllegalStateException) {
            recorder.release()
            return false
        }
        running = true

        thread = Thread {
            val buf = ShortArray(sampleRate / 10) // 100 ms
            var silentMs = 0
            var totalMs = 0
            var spoke = false
            while (running) {
                val n = recorder.read(buf, 0, buf.size)
                if (n <= 0) continue
                val bytes = ByteArray(n * 2)
                var sum = 0.0
                for (i in 0 until n) {
                    val s = buf[i].toInt()
                    sum += (s * s).toDouble()
                    bytes[2 * i] = (s and 0xff).toByte()
                    bytes[2 * i + 1] = ((s shr 8) and 0xff).toByte()
                }
                synchronized(pcm) { pcm.write(bytes) }

                val rms = sqrt(sum / n) / 32768.0
                val level = min(1.0, rms * 9.0).toFloat()
                onLevel(level)

                val chunkMs = n * 1000 / sampleRate
                totalMs += chunkMs
                if (level > 0.07f) {
                    spoke = true
                    silentMs = 0
                } else {
                    silentMs += chunkMs
                }
                if ((spoke && silentMs >= silenceStopMs) || totalMs >= maxDurationMs) {
                    running = false
                    onAutoStop()
                }
            }
            try {
                recorder.stop()
            } catch (_: IllegalStateException) {
            }
            recorder.release()
        }.also { it.start() }
        return true
    }

    /** Stops recording and returns a complete WAV file (may be empty if nothing was captured). */
    fun stop(): ByteArray {
        running = false
        thread?.join(1500)
        thread = null
        val data = synchronized(pcm) { pcm.toByteArray() }
        return wav(data)
    }

    fun cancel() {
        running = false
        thread = null
        synchronized(pcm) { pcm.reset() }
    }

    private fun wav(data: ByteArray): ByteArray {
        val out = ByteArrayOutputStream(44 + data.size)
        val byteRate = sampleRate * 2
        fun int(v: Int) { out.write(v and 0xff); out.write((v shr 8) and 0xff); out.write((v shr 16) and 0xff); out.write((v shr 24) and 0xff) }
        fun short(v: Int) { out.write(v and 0xff); out.write((v shr 8) and 0xff) }
        out.write("RIFF".toByteArray()); int(36 + data.size)
        out.write("WAVE".toByteArray())
        out.write("fmt ".toByteArray()); int(16); short(1); short(1)
        int(sampleRate); int(byteRate); short(2); short(16)
        out.write("data".toByteArray()); int(data.size)
        out.write(data)
        return out.toByteArray()
    }

    companion object {
        /** WAV header is 44 bytes; require at least ~0.3 s of audio. */
        fun hasAudio(wav: ByteArray): Boolean = wav.size > 44 + 16000 * 2 * 3 / 10
    }
}
