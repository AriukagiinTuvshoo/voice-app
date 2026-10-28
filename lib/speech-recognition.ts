import type { Language } from "./types";
import { restoreCodeSwitchingTerms } from "./text-processor";

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
  private shouldContinue: boolean = false;
  private finalTranscript: string = "";
  private lastInterim: string = "";

  constructor(
    private options: {
      language: Language;
      onInterim?: (fullPreviewText: string) => void;
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

      switch (this.options.language) {
        case "mn":
        case "auto":
          this.recognition.lang = "mn-MN";
          break;
        case "en":
          this.recognition.lang = "en-US";
          break;
        case "ja":
          this.recognition.lang = "ja-JP";
          break;
        default:
          this.recognition.lang = "mn-MN";
          break;
      }

      this.finalTranscript = "";
      this.lastInterim = "";
      this.isListening = true;
      this.shouldContinue = true;

      this.recognition.onresult = (e: SpeechRecognitionEvent) => {
        let interim = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const item = e.results[i];
          if (item.isFinal) {
            const seg = item[0].transcript.trim();
            if (seg) {
              this.finalTranscript += (this.finalTranscript ? " " : "") + seg;
            }
          } else {
            interim += item[0].transcript;
          }
        }
        this.lastInterim = interim.trim();
        const combined = restoreCodeSwitchingTerms(
          [this.finalTranscript, this.lastInterim]
            .filter(Boolean)
            .join(" ")
            .trim()
        );

        if (combined) {
          this.options.onInterim?.(combined);
        }
        if (this.finalTranscript) {
          this.options.onFinal?.(restoreCodeSwitchingTerms(this.finalTranscript));
        }
      };

      this.recognition.onerror = (e: SpeechRecognitionErrorEvent) => {
        if (e.error !== "no-speech" && e.error !== "aborted") {
          this.options.onError?.(`Speech алдаа: ${e.error}`);
        }
      };

      this.recognition.onend = () => {
        if (this.shouldContinue && this.recognition) {
          try {
            this.recognition.start();
            return;
          } catch {
            // Ignore restart error if already stopping
          }
        }
        this.isListening = false;
      };

      this.recognition.start();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Яриа танигч эхлэхэд алдаа гарлаа";
      this.options.onError?.(msg);
    }
  }

  stop(): Promise<string> {
    this.shouldContinue = false;
    return new Promise((resolve) => {
      const getBestText = () =>
        [this.finalTranscript, this.lastInterim].filter(Boolean).join(" ").trim();

      if (!this.recognition || !this.isListening) {
        resolve(getBestText());
        return;
      }

      const timeout = setTimeout(() => {
        this.isListening = false;
        resolve(getBestText());
      }, 600);

      this.recognition.onend = () => {
        clearTimeout(timeout);
        this.isListening = false;
        resolve(getBestText());
      };

      try {
        this.recognition.stop();
      } catch {
        clearTimeout(timeout);
        resolve(getBestText());
      }
    });
  }

  abort(): void {
    this.shouldContinue = false;
    if (this.recognition) {
      try {
        this.recognition.abort();
      } catch {}
      this.recognition = null;
      this.isListening = false;
    }
  }
}
