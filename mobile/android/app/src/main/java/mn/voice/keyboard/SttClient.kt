package mn.voice.keyboard

import org.json.JSONObject
import java.io.DataOutputStream
import java.net.HttpURLConnection
import java.net.URL

/** Sends WAV audio to the VOICE server (`/api/chimege/transcribe`) and returns recognized text. */
object SttClient {

    class SttException(message: String) : Exception(message)

    @Throws(SttException::class)
    fun transcribe(server: String, wav: ByteArray, language: String): String {
        val boundary = "----VOICE" + System.currentTimeMillis()
        val conn = try {
            (URL("$server/api/chimege/transcribe").openConnection() as HttpURLConnection)
        } catch (e: Exception) {
            throw SttException("Серверийн хаяг буруу байна")
        }

        try {
            conn.connectTimeout = 60_000 // free hosting may need time to wake up
            conn.readTimeout = 90_000
            conn.doOutput = true
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")

            DataOutputStream(conn.outputStream).use { o ->
                o.writeBytes("--$boundary\r\n")
                o.writeBytes("Content-Disposition: form-data; name=\"language\"\r\n\r\n")
                o.writeBytes("$language\r\n")
                o.writeBytes("--$boundary\r\n")
                o.writeBytes("Content-Disposition: form-data; name=\"audio\"; filename=\"speech.wav\"\r\n")
                o.writeBytes("Content-Type: audio/wav\r\n\r\n")
                o.write(wav)
                o.writeBytes("\r\n--$boundary--\r\n")
            }

            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val body = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""
            if (code !in 200..299) throw SttException("Сервер алдаа ($code)")

            val json = try { JSONObject(body) } catch (e: Exception) { throw SttException("Серверийн хариу буруу") }
            val text = json.optString("text", "").trim()
            if (text.isEmpty()) {
                throw SttException("Яриа танигдсангүй, тод ярина уу")
            }
            return text
        } catch (e: SttException) {
            throw e
        } catch (e: java.net.SocketTimeoutException) {
            throw SttException("Сервер хариу өгсөнгүй, дахин оролдоно уу")
        } catch (e: java.io.IOException) {
            throw SttException("Интернэт холболтоо шалгана уу")
        } finally {
            conn.disconnect()
        }
    }
}
