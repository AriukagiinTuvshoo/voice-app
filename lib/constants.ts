import type { Language, RecordingMode, ProcessingMode, Shortcut, Theme, SttEngine, Settings, ChimegeVoice } from "./types";

export const languages: { value: Language; label: string; icon: string }[] = [
  { value: "mn", label: "Монгол хэл (Цэвэр монгол)", icon: "🇲🇳" },
  { value: "auto", label: "Олон хэл (MN • EN • JP холимог)", icon: "🌐" },
  { value: "en", label: "English", icon: "🇬🇧" },
  { value: "ja", label: "日本語 (Япон)", icon: "🇯🇵" },
];

export const sttEngines: { value: SttEngine; label: string; description: string }[] = [
  { value: "auto", label: "Google Web Speech (Үнэгүй, Санал болгох)", description: "Монгол, Англи, Япон яриаг бодит цагт үнэгүй, найдвартай танина." },
  { value: "whisper", label: "Faster-Whisper (Оффлайн AI, туршилтын горим)", description: "Таны компьютерт интернет холболтгүй үед бие даан ажиллах загвар." },
  { value: "chimege", label: "Chimege API (Хувийн токентой)", description: "Хувийн Chimege API түлхүүрээр студийн танилт хийх горим." },
];

export const recordingModes: { value: RecordingMode; label: string; description: string }[] = [
  { value: "toggle", label: "Toggle (Товчлуурт)", description: "Нэг дарж эхлүүлээд, дуусмагц дахин дарж зогсооно." },
  { value: "push_to_talk", label: "Push-to-talk (Дарж ярих)", description: "Shortcut эсвэл товчийг дарж байх үед бичнэ." },
  { value: "microphone", label: "Microphone товч", description: "Дэлгэц дээрх микрофон товчоор удирдана." },
];

export const shortcuts: Shortcut[] = ["Space", "F2", "F4", "F8", "Ctrl+Space", "Alt+Space"];

export const modes: { value: ProcessingMode; label: string; description: string }[] = [
  { value: "raw", label: "Raw (Шууд)", description: "Таньсан текстийг ямар ч өөрчлөлтгүйгээр шууд харуулна." },
  { value: "standard", label: "Standard (Стандарт)", description: "Эхний үсгийг томоор эхлүүлж, цэг таслал тохируулна." },
  { value: "clean", label: "Clean (Цэвэрлэсэн)", description: "Сул үгсийг хасаж, зөв бичгийн алдааг засварлана." },
  { value: "polished", label: "Polished (Боловсронгуй)", description: "Догол мөр, найруулга, цэвэрлэгээг бүрэн хийнэ." },
];

export const themes: { value: Theme; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

export const chimegeVoices: ChimegeVoice[] = [
  // Эмэгтэй хоолойнууд
  { id: "FEMALE3v2", name: "Болор", gender: "female", description: "Уян зөөлөн, байгалийн өнгө аяс", tag: "Анхдагч • Эмэгтэй" },
  { id: "FEMALE1v2", name: "Номин", gender: "female", description: "Тод, цэвэр дуудлагатай", tag: "Эмэгтэй" },
  { id: "FEMALE2v2", name: "Сарнай", gender: "female", description: "Эелдэг, дулаахан өнгө төрх", tag: "Эмэгтэй" },
  { id: "FEMALE4v2", name: "Ану", gender: "female", description: "Мэдээ уншигч, албан ёсны", tag: "Эмэгтэй" },
  { id: "FEMALE5v2", name: "Төгсөө", gender: "female", description: "Эрч хүчтэй, залуулаг", tag: "Эмэгтэй" },
  { id: "FEMALE1", name: "Эгшиглэн", gender: "female", description: "Сонгодог хувилбар 1", tag: "Эмэгтэй v1" },
  // Эрэгтэй хоолойнууд
  { id: "MALE1v2", name: "Зориг", gender: "male", description: "Гүн, баргил, өөртөө итгэлтэй", tag: "Эрэгтэй" },
  { id: "MALE2v2", name: "Тулга", gender: "male", description: "Хүчирхэг, тайван, найдвартай", tag: "Эрэгтэй" },
  { id: "MALE3v2", name: "Баатар", gender: "male", description: "Уран яруу, өргөн цар хүрээтэй", tag: "Эрэгтэй" },
  { id: "MALE4v2", name: "Энхээ", gender: "male", description: "Залуулаг, өдөр тутмын яриа", tag: "Эрэгтэй" },
  { id: "MALE1", name: "Тэмүүлэн", gender: "male", description: "Сонгодог хувилбар 1", tag: "Эрэгтэй v1" },
];

export const defaultSettings: Settings = {
  language: "mn",
  sttEngine: "auto",
  chimegeToken: "",
  useStandardStt: true,
  recordingMode: "toggle",
  shortcut: "Space",
  autoStop: false,
  autoPunctuation: true,
  autoCorrection: true,
  removeFillers: false,
  processingMode: "standard",
  theme: "system",
  saveRecordings: true,
  saveTranscripts: true,
  selectedAudioDevice: "",
  // TTS Settings
  defaultVoiceId: "FEMALE3v2",
  ttsSpeed: 1.0,
  ttsPitch: 1.0,
  // Desktop mode
  autoInsertText: true,
  showFlowBar: true,
  whisperModel: "small",
  desktopHotkey: "f8",
  soundCues: true,
  numberNormalization: true,
  voiceActions: true,
  fillerWordCleaner: true,
  noiseGate: true,
  startWithWindows: true,
  customSnippets: true,
  techTermsNormalization: true,
  useGpu: true,
  cpuThreads: 6,
  mongolianGrammar: true,
  customVocabulary: [
    "Улаанбаатар",
    "Оюутолгой",
    "Тавантолгой",
    "ХААН Банк",
    "ШУТИС",
    "Монголбанк",
    "VoiceApp",
  ],
  snippets: {
    "миний имэйл": "user@example.invalid",
    "миний утас": "+97600000000",
    "данс": "2815108795",
  },
};

export const CHIMEGE_API_URL = "https://api.chimege.com/v1.2";
export const SPELLCHECK_API_URL = "https://spellcheck.mn/cms-client/modules/spellchecker";

export const MONGOLIAN_FILLER_WORDS = [
  "нөгөө",
  "нөгөөх",
  "нөгөөдөх",
  "ер нь",
  "ерөөсөө",
  "аан",
  "аанхаа",
  "за",
  "за за",
  "тэгээд",
  "гээд",
  "ээ",
  "хөөе",
  "тийм ээ",
  "юу юугүй",
  "байдгийм",
  "болгоод",
  "уг нь",
];
