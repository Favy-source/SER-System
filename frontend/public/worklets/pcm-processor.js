/**
 * AudioWorklet processor — captures raw float32 PCM from the audio graph
 * and sends each block to the main thread for WebSocket transmission.
 */
class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (channel) {
      const copy = new Float32Array(channel);
      this.port.postMessage(copy.buffer, [copy.buffer]);
    }
    return true;
  }
}
registerProcessor('pcm-processor', PCMProcessor);
