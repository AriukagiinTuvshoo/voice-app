/**
 * WAV audio encoder for Chimege STT API.
 * Encodes Float32Array PCM audio into 16kHz, 16-bit Mono WAV format.
 */

export function encodeWAV(samples: Float32Array, sampleRate: number = 16000): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  // RIFF identifier
  writeString(view, 0, "RIFF");
  // RIFF chunk length
  view.setUint32(4, 36 + samples.length * 2, true);
  // RIFF type
  writeString(view, 8, "WAVE");
  // format chunk identifier
  writeString(view, 12, "fmt ");
  // format chunk length
  view.setUint32(16, 16, true);
  // sample format (raw PCM = 1)
  view.setUint16(20, 1, true);
  // channel count (mono = 1)
  view.setUint16(22, 1, true);
  // sample rate (16000)
  view.setUint32(24, sampleRate, true);
  // byte rate (sample rate * block align)
  view.setUint32(28, sampleRate * 2, true);
  // block align (channels * bytes per sample)
  view.setUint16(32, 2, true);
  // bits per sample (16)
  view.setUint16(34, 16, true);
  // data chunk identifier
  writeString(view, 36, "data");
  // data chunk length
  view.setUint32(40, samples.length * 2, true);

  // Write PCM samples (float -1..1 converted to int16 -32768..32767)
  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }

  return new Blob([buffer], { type: "audio/wav" });
}

export function encodeSilence(durationSeconds: number = 0.5, sampleRate: number = 16000): Blob {
  const samplesCount = Math.floor(sampleRate * durationSeconds);
  const samples = new Float32Array(samplesCount);
  return encodeWAV(samples, sampleRate);
}

function writeString(view: DataView, offset: number, string: string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}

/**
 * Resamples an audio buffer to 16kHz mono.
 */
export function resampleTo16kMono(audioBuffer: AudioBuffer): Float32Array {
  const targetRate = 16000;
  const numChannels = audioBuffer.numberOfChannels;
  const sourceRate = audioBuffer.sampleRate;
  const sourceLength = audioBuffer.length;

  // Mix down channels to mono Float32Array
  const mono = new Float32Array(sourceLength);
  for (let c = 0; c < numChannels; c++) {
    const channelData = audioBuffer.getChannelData(c);
    for (let i = 0; i < sourceLength; i++) {
      mono[i] += channelData[i] / numChannels;
    }
  }

  if (sourceRate === targetRate) {
    return mono;
  }

  // Linear interpolation resampling to 16kHz
  const ratio = sourceRate / targetRate;
  const targetLength = Math.round(sourceLength / ratio);
  const result = new Float32Array(targetLength);

  for (let i = 0; i < targetLength; i++) {
    const srcIndex = i * ratio;
    const indexLow = Math.floor(srcIndex);
    const indexHigh = Math.min(indexLow + 1, sourceLength - 1);
    const weight = srcIndex - indexLow;
    result[i] = mono[indexLow] * (1 - weight) + mono[indexHigh] * weight;
  }

  return result;
}

/**
 * Resamples a raw Float32Array from sourceRate to targetRate (e.g. 48kHz/44.1kHz -> 16kHz)
 * without needing an extra OfflineAudioContext, which is prone to crashing on iOS Safari.
 */
export function resampleFloat32Array(
  samples: Float32Array,
  sourceRate: number,
  targetRate: number = 16000
): Float32Array {
  if (sourceRate === targetRate || samples.length === 0) {
    return samples;
  }

  const ratio = sourceRate / targetRate;
  const targetLength = Math.round(samples.length / ratio);
  const result = new Float32Array(targetLength);

  for (let i = 0; i < targetLength; i++) {
    const srcIndex = i * ratio;
    const indexLow = Math.floor(srcIndex);
    const indexHigh = Math.min(indexLow + 1, samples.length - 1);
    const weight = srcIndex - indexLow;
    result[i] = samples[indexLow] * (1 - weight) + samples[indexHigh] * weight;
  }

  return result;
}
