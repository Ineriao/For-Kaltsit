class PcmRecorderProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0]?.[0]
    if (!input?.length) return true
    const samples = new Float32Array(input)
    let sum = 0
    for (const sample of samples) sum += sample * sample
    this.port.postMessage({
      samples,
      level: Math.sqrt(sum / samples.length)
    }, [samples.buffer])
    return true
  }
}

registerProcessor('pcm-recorder', PcmRecorderProcessor)
