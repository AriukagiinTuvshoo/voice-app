import { encodeWAV, resampleFloat32Array } from "./wav-encoder";

export interface AudioRecorderOptions {
  deviceId?: string;
  onAudioLevel?: (level: number) => void;
  onSilenceDetected?: () => void;
  autoStop?: boolean;
}

export class AudioRecorder {
  private mediaStream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private recordedChunks: Float32Array[] = [];
  private totalSamples: number = 0;
  private levelInterval: ReturnType<typeof setInterval> | null = null;
  private silenceTimer: number = 0;
  private isRecording: boolean = false;
  private options: AudioRecorderOptions;

  constructor(options: AudioRecorderOptions = {}) {
    this.options = options;
  }

  async start(): Promise<void> {
    if (this.isRecording) return;
    this.recordedChunks = [];
    this.totalSamples = 0;
    this.silenceTimer = 0;

    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      const isSecure = typeof window !== "undefined" && window.isSecureContext;
      const host = typeof window !== "undefined" ? window.location.hostname : "";
      if (!isSecure && host && host !== "localhost" && host !== "127.0.0.1") {
        throw new Error(
          `Хөтөч аюулгүй биш орчинд (HTTP://${host}) ажиллаж байна. Chrome дээр микрофон ашиглахын тулд http://localhost:8000 эсвэл http://127.0.0.1:8000 хаягаар нээнэ үү.`
        );
      }
      throw new Error(
        "Микрофон ашиглах боломжгүй байна. Chrome/Edge хөтөч эсвэл HTTPS холболт ашиглана уу."
      );
    }

    const baseConstraints: MediaTrackConstraints = {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    };

    try {
      try {
        const audioConstraints: MediaTrackConstraints = { ...baseConstraints };
        if (this.options.deviceId) {
          audioConstraints.deviceId = { ideal: this.options.deviceId };
        }
        this.mediaStream = await navigator.mediaDevices.getUserMedia({
          audio: audioConstraints,
        });
      } catch (firstErr: unknown) {
        const errName = firstErr instanceof Error ? firstErr.name : "";
        if (errName === "NotAllowedError" || errName === "PermissionDeniedError") {
          throw new Error(
            "Микрофон ашиглах зөвшөөрөл хаалттай байна. Хөтчийнхөө хаягийн мөрний 🔒 тэмдэг дээр дарж Микрофоныг 'Зөвшөөрөх / Allow' болгоно уу."
          );
        }
        if (errName === "NotFoundError" || errName === "DevicesNotFoundError") {
          throw new Error(
            "Микрофон төхөөрөмж олдсонгүй. Микрофон тань компьютерт холбогдсон эсэхийг шалгана уу."
          );
        }
        if (errName === "NotReadableError" || errName === "TrackStartError") {
          throw new Error(
            "Микрофоныг өөр програм ашиглаж байна (эсвэл үйлдлийн систем дээр хаалттай). Бусад програмуудаа шалгаад дахин оролдоно уу."
          );
        }
        // Fallback to simple { audio: true } if custom deviceId failed
        try {
          this.mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: true,
          });
        } catch (secondErr: unknown) {
          const sErrName = secondErr instanceof Error ? secondErr.name : "";
          if (sErrName === "NotAllowedError" || sErrName === "PermissionDeniedError") {
            throw new Error(
              "Микрофон ашиглах зөвшөөрөл хаалттай байна. Хөтчийнхөө хаягийн мөрний 🔒 тэмдэг дээр дарж Микрофоныг 'Зөвшөөрөх / Allow' болгоно уу."
            );
          }
          if (sErrName === "NotFoundError" || sErrName === "DevicesNotFoundError") {
            throw new Error(
              "Микрофон төхөөрөмж олдсонгүй. Микрофон тань компьютерт холбогдсон эсэхийг шалгана уу."
            );
          }
          if (sErrName === "NotReadableError" || sErrName === "TrackStartError") {
            throw new Error(
              "Микрофоныг өөр програм ашиглаж байна. Бусад дуут програмуудаа хаагаад дахин оролдоно уу."
            );
          }
          throw secondErr;
        }
      }

      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.audioContext = new AudioCtx();

      if (this.audioContext.state === "suspended") {
        await this.audioContext.resume();
      }

      this.source = this.audioContext.createMediaStreamSource(this.mediaStream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 512;
      this.analyser.smoothingTimeConstant = 0.3;

      this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
      this.processor.onaudioprocess = (e) => {
        if (!this.isRecording) return;
        const inputData = e.inputBuffer.getChannelData(0);
        const clone = new Float32Array(inputData.length);
        clone.set(inputData);
        this.recordedChunks.push(clone);
        this.totalSamples += clone.length;
      };

      this.source.connect(this.analyser);
      this.analyser.connect(this.processor);
      this.processor.connect(this.audioContext.destination);

      this.isRecording = true;

      // Time-domain buffer for computing true RMS waveform amplitude
      const timeData = new Uint8Array(this.analyser.fftSize);
      this.levelInterval = setInterval(() => {
        if (!this.analyser || !this.isRecording) return;
        this.analyser.getByteTimeDomainData(timeData);

        let sumSquares = 0;
        for (let i = 0; i < timeData.length; i++) {
          const sample = (timeData[i] - 128) / 128;
          sumSquares += sample * sample;
        }
        const rms = Math.sqrt(sumSquares / timeData.length);
        const normalized = Math.min(1, Math.max(0, rms * 3.5));

        this.options.onAudioLevel?.(normalized);

        if (this.options.autoStop) {
          if (normalized < 0.05) {
            this.silenceTimer += 50;
            if (this.silenceTimer >= 3200) {
              this.options.onSilenceDetected?.();
            }
          } else {
            this.silenceTimer = 0;
          }
        }
      }, 50);
    } catch (err: unknown) {
      this.cleanUp();
      const errName = err instanceof Error ? err.name : "";
      if (errName === "NotAllowedError" || errName === "PermissionDeniedError") {
        throw new Error(
          "Микрофон ашиглах зөвшөөрөл хаалттай байна. Хөтчийнхөө хаягийн мөрний 🔒 тэмдэг дээр дарж Микрофоныг 'Зөвшөөрөх / Allow' болгоно уу."
        );
      }
      throw err;
    }
  }

  async stop(): Promise<Blob> {
    if (!this.isRecording) {
      throw new Error("Recording is not in progress");
    }

    this.isRecording = false;

    const fullBuffer = new Float32Array(this.totalSamples);
    let offset = 0;
    for (const chunk of this.recordedChunks) {
      fullBuffer.set(chunk, offset);
      offset += chunk.length;
    }

    const sampleRate = this.audioContext ? this.audioContext.sampleRate : 44100;
    this.cleanUp();

    if (fullBuffer.length === 0) {
      throw new Error("Аудио бичигдээгүй, дахин оролдоно уу.");
    }

    const resampled = resampleFloat32Array(fullBuffer, sampleRate, 16000);
    return encodeWAV(resampled, 16000);
  }

  getInterimWavBlob(maxSeconds: number = 3.0): Blob | null {
    if (!this.isRecording || this.recordedChunks.length === 0) return null;
    const sampleRate = this.audioContext ? this.audioContext.sampleRate : 44100;
    const maxSamples = Math.floor(sampleRate * maxSeconds);

    let collectedSamples = 0;
    const recentChunks: Float32Array[] = [];
    for (let i = this.recordedChunks.length - 1; i >= 0; i--) {
      recentChunks.unshift(this.recordedChunks[i]);
      collectedSamples += this.recordedChunks[i].length;
      if (collectedSamples >= maxSamples) break;
    }

    if (collectedSamples < sampleRate * 0.4) return null;

    const slice = new Float32Array(collectedSamples);
    let offset = 0;
    for (const ch of recentChunks) {
      slice.set(ch, offset);
      offset += ch.length;
    }

    const resampled = resampleFloat32Array(slice, sampleRate, 16000);
    return encodeWAV(resampled, 16000);
  }

  cancel(): void {
    this.isRecording = false;
    this.cleanUp();
  }

  private cleanUp(): void {
    if (this.levelInterval) {
      clearInterval(this.levelInterval);
      this.levelInterval = null;
    }

    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }

    if (this.analyser) {
      this.analyser.disconnect();
      this.analyser = null;
    }

    if (this.source) {
      this.source.disconnect();
      this.source = null;
    }

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    if (this.audioContext && this.audioContext.state !== "closed") {
      this.audioContext.close();
      this.audioContext = null;
    }

    this.recordedChunks = [];
    this.totalSamples = 0;
  }
}

export async function getAudioInputDevices(): Promise<MediaDeviceInfo[]> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.enumerateDevices) {
    return [];
  }
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter((d) => d.kind === "audioinput");
  } catch {
    return [];
  }
}
