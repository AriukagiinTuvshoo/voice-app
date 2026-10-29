export type Language = "mn" | "en" | "ja" | "auto";
export type RecordingState = "idle" | "recording" | "processing" | "success" | "error";
export type RecordingMode = "toggle" | "push_to_talk" | "microphone";
export type Shortcut = "Space" | "F2" | "F4" | "F8" | "Ctrl+Space" | "Alt+Space";
export type ProcessingMode = "raw" | "standard" | "clean" | "polished";
export type Theme = "light" | "dark" | "system";
export type SttEngine = "chimege" | "browser" | "auto" | "google" | "whisper";

export interface ChimegeVoice {
  id: string;
  name: string;
  gender: "female" | "male";
  description: string;
  tag: string;
}

export interface Settings {
  language: Language;
  sttEngine: SttEngine;
  chimegeToken: string;
  useStandardStt: boolean;
  recordingMode: RecordingMode;
  shortcut: Shortcut;
  autoStop: boolean;
  autoPunctuation: boolean;
  autoCorrection: boolean;
  removeFillers: boolean;
  processingMode: ProcessingMode;
  theme: Theme;
  saveRecordings: boolean;
  saveTranscripts: boolean;
  selectedAudioDevice: string;
  // TTS & Voice Settings
  defaultVoiceId: string;
  ttsSpeed: number;
  ttsPitch: number;
  // Desktop mode settings (Duudlaga Flow / VOICE Capsule)
  desktopHotkey: string;
  autoInsertText: boolean;
  showFlowBar: boolean;
  whisperModel?: string;
  // Enhanced features (v1.2.8)
  soundCues?: boolean;
  numberNormalization?: boolean;
  voiceActions?: boolean;
  fillerWordCleaner?: boolean;
  noiseGate?: boolean;
  startWithWindows?: boolean;
}

export interface TranscriptionRecord {
  id: string;
  text: string;
  rawText?: string;
  timestamp: number;
  durationSeconds: number;
  language: Language;
  engine: string;
  wordCount: number;
  charCount: number;
}

export interface SpellCheckResult {
  text: string;
  misspelled: string[];
  suggestions: Record<string, string[]>;
}
