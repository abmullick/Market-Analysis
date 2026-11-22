import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

const speechSource = await readFile("frontend/js/core/speech.js", "utf8");
const { createSpeechController, splitIntoChunks } = await import(
    `data:text/javascript;base64,${Buffer.from(speechSource).toString("base64")}`,
);

class FakeUtterance {
    constructor(text) {
        this.text = text;
        this.rate = 1;
        this.pitch = 1;
        this.voice = null;
    }
}

class FakeSpeechSynthesis {
    constructor() {
        this.queue = [];
        this.cancelCount = 0;
        this.paused = false;
        this.voices = [
            { name: "English Voice", lang: "en-US", voiceURI: "english" },
            { name: "Bengali Voice", lang: "bn-IN", voiceURI: "bengali" },
        ];
        this.listeners = new Map();
    }
    speak(utterance) { this.queue.push(utterance); }
    cancel() { this.cancelCount += 1; this.queue = []; this.paused = false; }
    pause() { this.paused = true; }
    resume() { this.paused = false; }
    getVoices() { return this.voices; }
    addEventListener(name, handler) { this.listeners.set(name, handler); }
    removeEventListener(name) { this.listeners.delete(name); }
    finishCurrent() {
        const utterance = this.queue.shift();
        utterance?.onend?.();
        return utterance;
    }
}

function makeController(options = {}) {
    const engine = new FakeSpeechSynthesis();
    const states = [];
    const errors = [];
    const controller = createSpeechController({
        speechSynthesis: engine,
        Utterance: FakeUtterance,
        onStateChange: state => states.push(state),
        onError: error => errors.push(error),
        ...options,
    });
    return { controller, engine, states, errors };
}

test("splits long text at sentence or word boundaries", () => {
    const chunks = splitIntoChunks("First sentence. " + "word ".repeat(30) + "Final sentence.", 40);
    assert.ok(chunks.length > 2);
    assert.ok(chunks.every(chunk => chunk.length <= 40));
    assert.match(chunks[0], /^First sentence\./);
});

test("speaks text sequentially and reports completion", () => {
    const { controller, engine, states } = makeController({ chunkLength: 45 });
    assert.equal(controller.speak("One sentence. " + "Another sentence. ".repeat(8)), true);
    assert.equal(controller.state, "speaking");
    assert.equal(engine.queue.length, 1);

    while (engine.queue.length) engine.finishCurrent();
    assert.equal(controller.state, "ended");
    assert.ok(states.includes("ended"));
});

test("supports pause and resume only while appropriate", () => {
    const { controller, engine } = makeController();
    assert.equal(controller.pause(), false);
    controller.speak("A short insight.");
    assert.equal(controller.pause(), true);
    assert.equal(controller.state, "paused");
    assert.equal(engine.paused, true);
    assert.equal(controller.resume(), true);
    assert.equal(controller.state, "speaking");
    assert.equal(engine.paused, false);
});

test("stop cancels queued speech and ignores stale completion events", () => {
    const { controller, engine } = makeController({ chunkLength: 40 });
    controller.speak("A sentence. ".repeat(12));
    const staleUtterance = engine.queue[0];
    controller.stop();
    staleUtterance.onend();
    assert.equal(controller.state, "idle");
    assert.equal(engine.queue.length, 0);
    assert.equal(engine.cancelCount, 2);
});

test("supports selecting a voice by URI and applies it to utterances", () => {
    const { controller, engine } = makeController();
    assert.equal(controller.setVoiceByURI("bengali").name, "Bengali Voice");
    controller.speak("Hello.");
    assert.equal(engine.queue[0].voice.name, "Bengali Voice");
});

test("reports speech errors and enters error state", () => {
    const { controller, engine, errors } = makeController();
    controller.speak("Hello.");
    const error = { error: "synthesis-failed" };
    engine.queue[0].onerror(error);
    assert.equal(controller.state, "error");
    assert.deepEqual(errors, [error]);
});

test("handles unavailable browser speech APIs and empty text", () => {
    const unavailable = createSpeechController({ speechSynthesis: null, Utterance: null });
    assert.equal(unavailable.supported, false);
    assert.equal(unavailable.speak("Hello"), false);

    const { controller, engine } = makeController();
    assert.equal(controller.speak("   "), false);
    assert.equal(engine.queue.length, 0);
});

test("subscribes to voice-list changes and can unsubscribe", () => {
    const { controller, engine } = makeController();
    let updates = 0;
    const unsubscribe = controller.onVoicesChanged(voices => {
        updates += 1;
        assert.equal(voices.length, 2);
    });
    engine.listeners.get("voiceschanged")();
    unsubscribe();
    assert.equal(updates, 1);
    assert.equal(engine.listeners.has("voiceschanged"), false);
});
