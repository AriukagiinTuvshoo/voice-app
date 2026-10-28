import SwiftUI
import AVFoundation

@main
struct VoiceKeyboardApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

struct ContentView: View {
    @State private var serverURL: String = {
        let d = UserDefaults(suiteName: "group.mn.voice.keyboard") ?? .standard
        return d.string(forKey: "server_url") ?? "https://voice-app.onrender.com"
    }()
    @State private var testText: String = ""
    @State private var micGranted: Bool = false

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text("🎤 VOICE Keyboard (iOS)")
                        .font(.title.bold())
                    Text("Safari, Chrome, Google, Facebook, Messenger, Instagram дээр Монгол, Англи, Япон хэлээр шууд ярьж бичих гар.")
                        .font(.subheadline)
                        .foregroundColor(.secondary)

                    GroupBox(label: Label("1. Микрофон зөвшөөрөл", systemImage: "mic.fill")) {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(micGranted ? "✅ Микрофон зөвшөөрөгдсөн" : "Дуу хоолой танихын тулд зөвшөөрөл өгнө үү.")
                                .font(.footnote)
                            Button("Микрофон зөвшөөрөх") {
                                AVAudioSession.sharedInstance().requestRecordPermission { ok in
                                    DispatchQueue.main.async { micGranted = ok }
                                }
                            }
                            .buttonStyle(.borderedProminent)
                        }
                    }

                    GroupBox(label: Label("2. iPhone Гарын Тохиргоо", systemImage: "keyboard")) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("1. Settings → General → Keyboard → Keyboards руу орно.")
                            Text("2. Add New Keyboard → VOICE Keyboard сонгоно.")
                            Text("3. VOICE Keyboard дээр дараад 'Allow Full Access' асаана.")
                        }
                        .font(.footnote)
                    }

                    GroupBox(label: Label("3. Туршиж бичих", systemImage: "text.bubble")) {
                        TextField("Энд дарж 🌐 товчоор VOICE гарыг сонгоод ярина уу...", text: $testText)
                            .textFieldStyle(.roundedBorder)
                    }

                    GroupBox(label: Label("4. Серверийн хаяг", systemImage: "globe")) {
                        VStack(alignment: .leading, spacing: 8) {
                            TextField("https://...", text: $serverURL)
                                .textFieldStyle(.roundedBorder)
                                .autocapitalization(.none)
                            Button("Хадгалах") {
                                let d = UserDefaults(suiteName: "group.mn.voice.keyboard") ?? .standard
                                d.set(serverURL, forKey: "server_url")
                            }
                            .buttonStyle(.bordered)
                        }
                    }
                }
                .padding()
            }
            .navigationBarHidden(true)
        }
    }
}
