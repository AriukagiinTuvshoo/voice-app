import { encodeWAV, resampleTo16kMono } from "./wav-encoder";

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

    const audioConstraints: MediaTrackConstraints = {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    };

    if (this.options.deviceId) {
      audioConstraints.deviceId = { exact: this.options.deviceId };
    }

    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: audioConstraints,
      });

      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.audioContext = new AudioCtx();

      this.source = this.audioContext.createMediaStreamSource(this.mediaStream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 512;
      this.analyser.smoothingTimeConstant = 0.3;

      // ScriptProcessor to record audio samples
      // Buffer size 4096 gives balance of performance and responsiveness
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

      // Setup audio level polling & silence detection (~20 FPS)
      const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
      this.levelInterval = setInterval(() => {
        if (!this.analyser || !this.isRecording) return;
        this.analyser.getByteFrequencyData(dataArray);

        // Compute RMS / average volume
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        const avg = sum / dataArray.length;
        const normalized = Math.min(1, avg / 128); // 0 to 1

        this.options.onAudioLevel?.(normalized);

        // Auto stop on sustained silence
        if (this.options.autoStop) {
          if (normalized < 0.05) {
            this.silenceTimer += 50;
            // 2.5 seconds of silence
            if (this.silenceTimer >= 2500) {
              this.options.onSilenceDetected?.();
            }
          } else {
            this.silenceTimer = 0;
          }
        }
      }, 50);
    } catch (err) {
      this.cleanUp();
      throw err;
    }
  }

  async stop(): Promise<Blob> {
    if (!this.isRecording) {
      throw new Error("Recording is not in progress");
    }

    this.isRecording = false;

    // Gather collected samples
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

    // Resample to 16kHz mono WAV for Chimege API
    // Create an offline/temporary audio buffer to resample
    const offlineCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    const sourceBuffer = offlineCtx.createBuffer(1, fullBuffer.length, sampleRate);
    sourceBuffer.copyToChannel(fullBuffer, 0);

    const resampled = resampleTo16kMono(sourceBuffer);
    offlineCtx.close();

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

/**
 * Enumerate available microphone audio inputs.
 */
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
