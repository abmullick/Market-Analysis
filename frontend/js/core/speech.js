/**
 * Browser-native text-to-speech controller shared by AI insight experiences.
 *
 * This module only uses the Web Speech API. It does not send text or audio to
 * an external service. UI components own their buttons and call this controller.
 */

const DEFAULT_CHUNK_LENGTH = 220;

function splitIntoChunks(text, maxLength) {
    const normalized = String(text ?? "").replace(/\s+/g, " ").trim();
    if (!normalized) return [];

    const sentences = normalized.match(/[^.!?]+[.!?]*/g) || [normalized];
    const chunks = [];
    let current = "";

    for (const sentence of sentences) {
        let remaining = sentence.trim();
        if (!remaining) continue;

        while (remaining.length > maxLength) {
            const boundary = remaining.lastIndexOf(" ", maxLength);
            const splitAt = boundary > 0 ? boundary : maxLength;
            const part = remaining.slice(0, splitAt).trim();
            if (part) {
                if (current) chunks.push(current);
                chunks.push(part);
            }
            remaining = remaining.slice(splitAt).trim();
        }

        if (remaining) {
            if (current && current.length + remaining.length + 1 > maxLength) {
                chunks.push(current);
                current = remaining;
            } else {
                current += (current ? " " : "") + remaining;
            }
        }
    }

    if (current) chunks.push(current);
    return chunks;
}

/**
 * Create an independent speech session.
 *
 * @param {object} options
 * @param {SpeechSynthesis} [options.speechSynthesis]
 * @param {typeof SpeechSynthesisUtterance} [options.Utterance]
 * @param {number} [options.chunkLength=220]
 * @param {number} [options.rate=1]
 * @param {number} [options.pitch=1]
 * @param {(state: string) => void} [options.onStateChange]
 * @param {(error: SpeechSynthesisErrorEvent) => void} [options.onError]
 */
export function createSpeechController({
    speechSynthesis = globalThis.speechSynthesis,
    Utterance = globalThis.SpeechSynthesisUtterance,
    chunkLength = DEFAULT_CHUNK_LENGTH,
    rate = 1,
    pitch = 1,
    onStateChange = () => {},
    onError = () => {},
} = {}) {
    const supported = Boolean(
        speechSynthesis
        && typeof speechSynthesis.speak === "function"
        && typeof speechSynthesis.cancel === "function"
        && typeof Utterance === "function",
    );

    let state = "idle";
    let chunks = [];
    let chunkIndex = 0;
    let selectedVoice = null;
    let sessionId = 0;

    function setState(nextState) {
        state = nextState;
        onStateChange(state);
    }

    function speakNext(id) {
        if (id !== sessionId || state !== "speaking") return;

        if (chunkIndex >= chunks.length) {
            chunks = [];
            chunkIndex = 0;
            setState("ended");
            return;
        }

        const utterance = new Utterance(chunks[chunkIndex]);
        utterance.rate = rate;
        utterance.pitch = pitch;
        if (selectedVoice) utterance.voice = selectedVoice;

        utterance.onend = () => {
            if (id !== sessionId || state !== "speaking") return;
            chunkIndex += 1;
            speakNext(id);
        };

        utterance.onerror = event => {
            if (id !== sessionId) return;
            chunks = [];
            chunkIndex = 0;
            setState("error");
            onError(event);
        };

        speechSynthesis.speak(utterance);
    }

    function speak(text) {
        if (!supported) return false;

        stop();
        chunks = splitIntoChunks(text, Math.max(40, Number(chunkLength) || DEFAULT_CHUNK_LENGTH));
        chunkIndex = 0;
        if (chunks.length === 0) {
            setState("idle");
            return false;
        }

        const id = sessionId;
        setState("speaking");
        speakNext(id);
        return true;
    }

    function pause() {
        if (!supported || state !== "speaking") return false;
        speechSynthesis.pause();
        setState("paused");
        return true;
    }

    function resume() {
        if (!supported || state !== "paused") return false;
        speechSynthesis.resume();
        setState("speaking");
        return true;
    }

    function stop() {
        if (!supported) return false;
        sessionId += 1;
        speechSynthesis.cancel();
        chunks = [];
        chunkIndex = 0;
        setState("idle");
        return true;
    }

    function getVoices() {
        return supported && typeof speechSynthesis.getVoices === "function"
            ? speechSynthesis.getVoices()
            : [];
    }

    function setVoice(voice) {
        selectedVoice = voice || null;
    }

    function setVoiceByURI(uri) {
        selectedVoice = getVoices().find(voice => voice.voiceURI === uri) || null;
        return selectedVoice;
    }

    function onVoicesChanged(callback) {
        if (!supported || typeof callback !== "function") return () => {};
        const handler = () => callback(getVoices());
        if (typeof speechSynthesis.addEventListener === "function") {
            speechSynthesis.addEventListener("voiceschanged", handler);
            return () => speechSynthesis.removeEventListener?.("voiceschanged", handler);
        }
        const previous = speechSynthesis.onvoiceschanged;
        speechSynthesis.onvoiceschanged = handler;
        return () => {
            if (speechSynthesis.onvoiceschanged === handler) {
                speechSynthesis.onvoiceschanged = previous || null;
            }
        };
    }

    return {
        get supported() { return supported; },
        get state() { return state; },
        speak,
        pause,
        resume,
        stop,
        getVoices,
        setVoice,
        setVoiceByURI,
        onVoicesChanged,
    };
}

export { splitIntoChunks };
