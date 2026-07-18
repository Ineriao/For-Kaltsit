const TARGET_SAMPLE_RATE = 16000

export class VoiceRecorder {
  constructor(options = {}) {
    this.options = {
      speechThreshold: 0.018,
      silenceMs: 950,
      noSpeechTimeoutMs: 8000,
      maxDurationMs: 30000,
      onLevel: () => {},
      onAutoStop: () => {},
      ...options
    }
    this.context = null
    this.stream = null
    this.source = null
    this.worklet = null
    this.chunks = []
    this.startedAt = 0
    this.lastSpeechAt = 0
    this.hadSpeech = false
    this.running = false
    this.timer = null
  }

  async start() {
    if (this.running) return
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    })
    this.context = new AudioContext({ latencyHint: 'interactive' })
    await this.context.audioWorklet.addModule('/audio/pcm-recorder-worklet.js')
    this.source = this.context.createMediaStreamSource(this.stream)
    this.worklet = new AudioWorkletNode(this.context, 'pcm-recorder')
    this.worklet.port.onmessage = event => this.handleFrame(event.data)
    this.source.connect(this.worklet)
    this.worklet.connect(this.context.destination)
    this.startedAt = performance.now()
    this.lastSpeechAt = this.startedAt
    this.running = true
    this.timer = window.setInterval(() => this.checkAutoStop(), 100)
  }

  handleFrame({ samples, level }) {
    if (!this.running || !samples) return
    this.chunks.push(samples)
    const normalizedLevel = Math.max(0, Math.min(1, level / 0.16))
    this.options.onLevel(normalizedLevel)
    if (level >= this.options.speechThreshold) {
      this.hadSpeech = true
      this.lastSpeechAt = performance.now()
    }
  }

  checkAutoStop() {
    if (!this.running) return
    const now = performance.now()
    if (!this.hadSpeech && now - this.startedAt >= this.options.noSpeechTimeoutMs) {
      this.options.onAutoStop('no-speech')
    } else if (this.hadSpeech && now - this.lastSpeechAt >= this.options.silenceMs) {
      this.options.onAutoStop('silence')
    } else if (now - this.startedAt >= this.options.maxDurationMs) {
      this.options.onAutoStop('max-duration')
    }
  }

  async stop(reason = 'manual') {
    if (!this.running) return null
    this.running = false
    window.clearInterval(this.timer)
    this.options.onLevel(0)
    this.worklet?.disconnect()
    this.source?.disconnect()
    this.stream?.getTracks().forEach(track => track.stop())
    await this.context?.close()

    const inputSampleRate = this.context?.sampleRate || TARGET_SAMPLE_RATE
    const merged = mergeChunks(this.chunks)
    const downsampled = downsample(merged, inputSampleRate, TARGET_SAMPLE_RATE)
    return {
      blob: encodeWav(downsampled, TARGET_SAMPLE_RATE),
      duration: downsampled.length / TARGET_SAMPLE_RATE,
      hadSpeech: this.hadSpeech,
      reason
    }
  }
}

function mergeChunks(chunks) {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0)
  const merged = new Float32Array(length)
  let offset = 0
  for (const chunk of chunks) {
    merged.set(chunk, offset)
    offset += chunk.length
  }
  return merged
}

function downsample(samples, inputRate, outputRate) {
  if (inputRate === outputRate) return samples
  const ratio = inputRate / outputRate
  const output = new Float32Array(Math.floor(samples.length / ratio))
  for (let index = 0; index < output.length; index += 1) {
    const start = Math.floor(index * ratio)
    const end = Math.min(samples.length, Math.floor((index + 1) * ratio))
    let sum = 0
    for (let inputIndex = start; inputIndex < end; inputIndex += 1) sum += samples[inputIndex]
    output[index] = sum / Math.max(1, end - start)
  }
  return output
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(view, 36, 'data')
  view.setUint32(40, samples.length * 2, true)
  let offset = 44
  for (const sample of samples) {
    const clipped = Math.max(-1, Math.min(1, sample))
    view.setInt16(offset, clipped < 0 ? clipped * 32768 : clipped * 32767, true)
    offset += 2
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

function writeString(view, offset, value) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index))
  }
}
