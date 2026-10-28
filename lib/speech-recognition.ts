import type { Language } from "./types";

// Type definitions for Web Speech API
interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message?: string;
}

interface SpeechRecognitionEvent extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface IWindowWithSpeech extends Window {
  SpeechRecognition?: {
    new (): ISpeechRecognition;
  };
  webkitSpeechRecognition?: {
    new (): ISpeechRecognition;
  };
}

interface ISpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((this: ISpeechRecognition, ev: SpeechRecognitionEvent) => unknown) | null;
  onerror: ((this: ISpeechRecognition, ev: SpeechRecognitionErrorEvent) => unknown) | null;
  onend: ((this: ISpeechRecognition, ev: Event) => unknown) | null;
}

export function isBrowserSpeechSupported(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as IWindowWithSpeech;
  return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
}

export class BrowserSpeechRecognizer {
  private recognition: ISpeechRecognition | null = null;
  private isListening: boolean = false;
  private finalTranscript: string = "";

  constructor(
    private options: {
      language: Language;
      onInterim?: (text: string) => void;
      onFinal?: (text: string) => void;
      onError?: (error: string) => void;
    }
  ) {}

  start(): void {
    if (typeof window === "undefined") return;
    const w = window as unknown as IWindowWithSpeech;
    const SpeechClass = w.SpeechRecognition || w.webkitSpeechRecognition;

    if (!SpeechClass) {
      this.options.onError?.("Хөтөч тань Web Speech API дэмжихгүй байна.");
      return;
    }

    try {
      this.recognition = new SpeechClass();
      this.recognition.continuous = true;
      this.recognition.interimResults = true;

      // Map language code
      switch (this.options.language) {
        case "mn":
          this.recognition.lang = "mn-MN";
          break;
        case "en":
          this.recognition.lang = "en-US";
          break;
        case "ja":
          this.recognition.lang = "ja-JP";
          break;
        default:
          this.recognition.lang = navigator.language || "en-US";
          break;
      }

      this.finalTranscript = "";
      this.isListening = true;

      this.recognition.onresult = (e: SpeechRecognitionEvent) => {
        let interim = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const item = e.results[i];
          if (item.isFinal) {
            this.finalTranscript += (this.finalTranscript ? " " : "") + item[0].transcript.trim();
          } else {
            interim += item[0].transcript;
          }
        }
        if (interim) {
          this.options.onInterim?.(interim);
        }
        if (this.finalTranscript) {
          this.options.onFinal?.(this.finalTranscript);
        }
      };

      this.recognition.onerror = (e: SpeechRecognitionErrorEvent) => {
        if (e.error !== "no-speech") {
          this.options.onError?.(`Speech алдаа: ${e.error}`);
        }
      };

      this.recognition.onend = () => {
        this.isListening = false;
      };

      this.recognition.start();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Яриа танигч эхлэхэд алдаа гарлаа";
      this.options.onError?.(msg);
    }
  }

  stop(): Promise<string> {
    return new Promise((resolve) => {
      if (!this.recognition || !this.isListening) {
        resolve(this.finalTranscript.trim());
        return;
      }
      this.recognition.onend = () => {
        this.isListening = false;
        resolve(this.finalTranscript.trim());
      };
      try {
        this.recognition.stop();
      } catch {
        resolve(this.finalTranscript.trim());
      }
    });
  }

  abort(): void {
    if (this.recognition) {
      try {
        this.recognition.abort();
      } catch {}
      this.recognition = null;
      this.isListening = false;
    }
  }
}
