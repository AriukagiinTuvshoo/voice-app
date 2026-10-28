import UIKit
import AVFoundation

/**
 * VOICE Keyboard Extension for iOS (iPhone / iPad)
 * System-wide keyboard that works inside Chrome, Google Search, Safari, Messenger, Instagram, Notes, etc.
 * Features:
 *  - Top VOICE AI Dictation Bar (Tap 🎤 to speak in Mongolian + English + Japanese -> types directly into active text field)
 *  - Full Mongolian Cyrillic Keyboard layout + Globe switcher + Backspace + Space + Search/Return
 */
class KeyboardViewController: UIInputViewController, AVAudioRecorderDelegate {

    private var audioRecorder: AVAudioRecorder?
    private var isRecording = false
    private var currentLang = "mn" // "mn", "auto", "en", "ja"
    private var shiftActive = false

    private let statusLabel = UILabel()
    private let micButton = UIButton(type: .system)
    private let langButton = UIButton(type: .system)
    private var letterButtons: [UIButton] = []

    private let mnRows: [[String]] = [
        ["ф", "ц", "у", "ж", "э", "н", "г", "ш", "ү", "з", "к", "ъ"],
        ["й", "ы", "б", "ө", "а", "х", "р", "о", "л", "д", "п"],
        ["я", "ч", "ё", "с", "м", "и", "т", "ь", "в", "ю", "е"]
    ]

    private var serverURL: String {
        let defaults = UserDefaults(suiteName: "group.mn.voice.keyboard") ?? .standard
        let saved = defaults.string(forKey: "server_url")?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return saved.isEmpty ? "https://voice-app.onrender.com" : saved
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 0.04, green: 0.06, blue: 0.10, alpha: 1.0)
        setupKeyboardLayout()
    }

    private func setupKeyboardLayout() {
        let mainStack = UIStackView()
        mainStack.axis = .vertical
        mainStack.spacing = 6
        mainStack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(mainStack)

        NSLayoutConstraint.activate([
            mainStack.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 5),
            mainStack.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -5),
            mainStack.topAnchor.constraint(equalTo: view.topAnchor, constant: 6),
            mainStack.bottomAnchor.constraint(equalTo: view.bottomAnchor, constant: -6),
            view.heightAnchor.constraint(equalToConstant: 256)
        ])

        // 1. VOICE AI Dictation Top Bar
        mainStack.addArrangedSubview(buildTopVoiceBar())

        // 2. Mongolian Cyrillic Rows
        for (rowIdx, rowKeys) in mnRows.enumerated() {
            let rowStack = UIStackView()
            rowStack.axis = .horizontal
            rowStack.spacing = 4
            rowStack.distribution = .fillEqually
            rowStack.heightAnchor.constraint(equalToConstant: 42).isActive = true

            if rowIdx == 2 {
                let shiftBtn = makeKeyButton(title: "⇧", bgHex: 0x1E293B)
                shiftBtn.addTarget(self, action: #selector(toggleShift), for: .touchUpInside)
                rowStack.addArrangedSubview(shiftBtn)
            }

            for key in rowKeys {
                let btn = makeKeyButton(title: key, bgHex: 0x1E293B)
                btn.addTarget(self, action: #selector(letterTapped(_:)), for: .touchUpInside)
                letterButtons.append(btn)
                rowStack.addArrangedSubview(btn)
            }

            if rowIdx == 2 {
                let delBtn = makeKeyButton(title: "⌫", bgHex: 0x334155)
                delBtn.addTarget(self, action: #selector(backspaceTapped), for: .touchUpInside)
                rowStack.addArrangedSubview(delBtn)
            }

            mainStack.addArrangedSubview(rowStack)
        }

        // 3. Bottom Row (Globe, Space, Search/Return)
        mainStack.addArrangedSubview(buildBottomRow())
    }

    private func buildTopVoiceBar() -> UIView {
        let container = UIStackView()
        container.axis = .horizontal
        container.spacing = 8
        container.alignment = .center
        container.layoutMargins = UIEdgeInsets(top: 5, left: 8, bottom: 5, right: 8)
        container.isLayoutMarginsRelativeArrangement = true
        container.backgroundColor = UIColor(red: 0.08, green: 0.11, blue: 0.18, alpha: 1.0)
        container.layer.cornerRadius = 14
        container.heightAnchor.constraint(equalToConstant: 44).isActive = true

        langButton.setTitle("🌐 MN", for: .normal)
        langButton.setTitleColor(.white, for: .normal)
        langButton.titleLabel?.font = .boldSystemFont(ofSize: 12)
        langButton.backgroundColor = UIColor(red: 0.12, green: 0.16, blue: 0.23, alpha: 1.0)
        langButton.layer.cornerRadius = 10
        langButton.contentEdgeInsets = UIEdgeInsets(top: 6, left: 10, bottom: 6, right: 10)
        langButton.addTarget(self, action: #selector(cycleLanguage), for: .touchUpInside)
        container.addArrangedSubview(langButton)

        statusLabel.text = "🎤 Дарж ярих (VOICE AI)"
        statusLabel.textColor = .white
        statusLabel.font = .boldSystemFont(ofSize: 13)
        statusLabel.setContentHuggingPriority(.defaultLow, for: .horizontal)
        container.addArrangedSubview(statusLabel)

        micButton.setTitle("🎤 Ярих", for: .normal)
        micButton.setTitleColor(.white, for: .normal)
        micButton.titleLabel?.font = .boldSystemFont(ofSize: 13)
        micButton.backgroundColor = UIColor(red: 0.39, green: 0.40, blue: 0.95, alpha: 1.0)
        micButton.layer.cornerRadius = 14
        micButton.contentEdgeInsets = UIEdgeInsets(top: 7, left: 14, bottom: 7, right: 14)
        micButton.addTarget(self, action: #selector(toggleRecording), for: .touchUpInside)
        container.addArrangedSubview(micButton)

        return container
    }

    private func buildBottomRow() -> UIView {
        let row = UIStackView()
        row.axis = .horizontal
        row.spacing = 5
        row.distribution = .fillProportionally
        row.heightAnchor.constraint(equalToConstant: 44).isActive = true

        let globeBtn = makeKeyButton(title: "🌐", bgHex: 0x1E293B)
        globeBtn.addTarget(self, action: #selector(handleInputModeList(from:with:)), for: .allTouchEvents)
        globeBtn.widthAnchor.constraint(equalToConstant: 46).isActive = true
        row.addArrangedSubview(globeBtn)

        let spaceBtn = makeKeyButton(title: "Зай (Space)", bgHex: 0x334155)
        spaceBtn.addTarget(self, action: #selector(spaceTapped), for: .touchUpInside)
        row.addArrangedSubview(spaceBtn)

        let enterBtn = makeKeyButton(title: "🔍 Хайх / ↵", bgHex: 0x4F46E5)
        enterBtn.widthAnchor.constraint(equalToConstant: 96).isActive = true
        enterBtn.addTarget(self, action: #selector(enterTapped), for: .touchUpInside)
        row.addArrangedSubview(enterBtn)

        return row
    }

    private func makeKeyButton(title: String, bgHex: Int) -> UIButton {
        let btn = UIButton(type: .system)
        btn.setTitle(title, for: .normal)
        btn.setTitleColor(.white, for: .normal)
        btn.titleLabel?.font = .systemFont(ofSize: 15, weight: .semibold)
        btn.backgroundColor = UIColor(
            red: CGFloat((bgHex >> 16) & 0xFF) / 255.0,
            green: CGFloat((bgHex >> 8) & 0xFF) / 255.0,
            blue: CGFloat(bgHex & 0xFF) / 255.0,
            alpha: 1.0
        )
        btn.layer.cornerRadius = 7
        return btn
    }

    @objc private func cycleLanguage() {
        let order = ["mn", "auto", "en", "ja"]
        let idx = order.firstIndex(of: currentLang) ?? 0
        currentLang = order[(idx + 1) % order.count]
        langButton.setTitle("🌐 \(currentLang.uppercased())", for: .normal)
    }

    @objc private func toggleShift() {
        shiftActive.toggle()
        for btn in letterButtons {
            if let t = btn.title(for: .normal) {
                btn.setTitle(shiftActive ? t.uppercased() : t.lowercased(), for: .normal)
            }
        }
    }

    @objc private func letterTapped(_ sender: UIButton) {
        guard let t = sender.title(for: .normal) else { return }
        textDocumentProxy.insertText(t)
        if shiftActive {
            toggleShift()
        }
    }

    @objc private func backspaceTapped() {
        textDocumentProxy.deleteBackward()
    }

    @objc private func spaceTapped() {
        textDocumentProxy.insertText(" ")
    }

    @objc private func enterTapped() {
        textDocumentProxy.insertText("\n")
    }

    @objc private func toggleRecording() {
        if isRecording {
            stopAndTranscribe()
        } else {
            startRecording()
        }
    }

    private func startRecording() {
        let session = AVAudioSession.sharedInstance()
        session.requestRecordPermission { [weak self] granted in
            DispatchQueue.main.async {
                guard let self = self else { return }
                if !granted {
                    self.statusLabel.text = "⚠️ Микрофон & Allow Full Access асаана уу"
                    return
                }
                do {
                    try session.setCategory(.playAndRecord, mode: .measurement, options: [.defaultToSpeaker])
                    try session.setActive(true)
                    let url = FileManager.default.temporaryDirectory.appendingPathComponent("voice_kbd.wav")
                    let settings: [String: Any] = [
                        AVFormatIDKey: Int(kAudioFormatLinearPCM),
                        AVSampleRateKey: 16000.0,
                        AVNumberOfChannelsKey: 1,
                        AVLinearPCMBitDepthKey: 16,
                        AVLinearPCMIsBigEndianKey: false,
                        AVLinearPCMIsFloatKey: false
                    ]
                    let rec = try AVAudioRecorder(url: url, settings: settings)
                    rec.delegate = self
                    rec.record()
                    self.audioRecorder = rec
                    self.isRecording = true
                    self.statusLabel.text = "🔴 Сонсож байна..."
                    self.micButton.setTitle("⏹ Дуусгах", for: .normal)
                    self.micButton.backgroundColor = .systemRed
                } catch {
                    self.statusLabel.text = "⚠️ Allow Full Access асаана уу"
                }
            }
        }
    }

    private func stopAndTranscribe() {
        guard let rec = audioRecorder else { return }
        let fileURL = rec.url
        rec.stop()
        audioRecorder = nil
        isRecording = false

        statusLabel.text = "⏳ Хөрвүүлж байна..."
        micButton.setTitle("🎤 Ярих", for: .normal)
        micButton.backgroundColor = UIColor(red: 0.39, green: 0.40, blue: 0.95, alpha: 1.0)

        guard let audioData = try? Data(contentsOf: fileURL), audioData.count > 1000 else {
            statusLabel.text = "Яриа сонсогдсонгүй"
            return
        }

        guard let url = URL(string: "\(serverURL)/api/ios-dictate?lang=\(currentLang)") else { return }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("audio/wav", forHTTPHeaderField: "Content-Type")
        req.httpBody = audioData
        req.timeoutInterval = 30

        URLSession.shared.dataTask(with: req) { [weak self] data, _, error in
            DispatchQueue.main.async {
                guard let self = self else { return }
                if let data = data, let text = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty {
                    self.textDocumentProxy.insertText(text + " ")
                    self.statusLabel.text = "✅ Бичигдлээ! • Дарж ярих"
                } else if error != nil {
                    self.statusLabel.text = "⚠️ Интернэт эсвэл Full Access шалгана уу"
                } else {
                    self.statusLabel.text = "Тод ярина уу • Дарж ярих"
                }
            }
        }.resume()
    }
}
