/**
 * Shared controls for reading rendered AI insight cards aloud.
 * Uses the browser-native Web Speech API through the common speech controller.
 */
import { createSpeechController } from "./speech.js";

const CONTROL_CLASS = "ai-speech-controls";
const activeControls = new WeakMap();

export function attachSpeechControls(container) {
    if (!container || !container.ownerDocument) return null;

    const previous = activeControls.get(container);
    previous?.controller.stop();
    previous?.unsubscribeVoices();
    container.querySelector(`.${CONTROL_CLASS}`)?.remove();

    const documentRef = container.ownerDocument;
    const controls = documentRef.createElement("div");
    controls.className = CONTROL_CLASS;
    controls.setAttribute("role", "group");
    controls.setAttribute("aria-label", "Read AI insights aloud");
    controls.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:12px 0;";

    const readButton = documentRef.createElement("button");
    readButton.type = "button";
    readButton.className = "ai-action ai-action-compact";
    readButton.textContent = "🔊 Read aloud";
    readButton.setAttribute("aria-label", "Read AI insights aloud");

    const pauseButton = documentRef.createElement("button");
    pauseButton.type = "button";
    pauseButton.className = "ai-action ai-action-compact";
    pauseButton.textContent = "Pause";
    pauseButton.hidden = true;

    const resumeButton = documentRef.createElement("button");
    resumeButton.type = "button";
    resumeButton.className = "ai-action ai-action-compact";
    resumeButton.textContent = "Resume";
    resumeButton.hidden = true;

    const stopButton = documentRef.createElement("button");
    stopButton.type = "button";
    stopButton.className = "ai-action ai-action-compact";
    stopButton.textContent = "Stop";
    stopButton.hidden = true;

    const voiceSelect = documentRef.createElement("select");
    voiceSelect.className = "ai-speech-voice";
    voiceSelect.setAttribute("aria-label", "Speech voice");
    voiceSelect.title = "Choose a voice";
    voiceSelect.style.cssText = "max-width:220px;min-height:34px;padding:4px 8px;border-radius:6px;";

    const status = documentRef.createElement("span");
    status.className = "ai-speech-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    status.style.cssText = "font-size:0.85em;opacity:.75;";

    controls.append(readButton, pauseButton, resumeButton, stopButton, voiceSelect, status);
    container.prepend(controls);

    const controller = createSpeechController({
        onStateChange(state) {
            const active = state === "speaking" || state === "paused";
            readButton.hidden = active;
            pauseButton.hidden = state !== "speaking";
            resumeButton.hidden = state !== "paused";
            stopButton.hidden = !active;
            status.textContent = state === "speaking" ? "Reading…" :
                state === "paused" ? "Paused" :
                state === "ended" ? "Finished" :
                state === "error" ? "Speech unavailable" : "";
        },
        onError() {
            status.textContent = "Speech could not continue. Try again.";
        },
    });

    if (!controller.supported) {
        controls.remove();
        return null;
    }

    function populateVoices(voices) {
        const selected = voiceSelect.value;
        voiceSelect.replaceChildren();
        const defaultOption = documentRef.createElement("option");
        defaultOption.value = "";
        defaultOption.textContent = "Default voice";
        voiceSelect.appendChild(defaultOption);

        voices.forEach((voice, index) => {
            const option = documentRef.createElement("option");
            option.value = voice.voiceURI || String(index);
            option.textContent = `${voice.name}${voice.lang ? ` (${voice.lang})` : ""}`;
            voiceSelect.appendChild(option);
        });
        if (selected && voices.some(voice => voice.voiceURI === selected)) {
            voiceSelect.value = selected;
            controller.setVoiceByURI(selected);
        }
        voiceSelect.hidden = voices.length < 2;
    }

    populateVoices(controller.getVoices());
    const unsubscribeVoices = controller.onVoicesChanged(populateVoices);
    activeControls.set(container, { controller, unsubscribeVoices });

    readButton.addEventListener("click", () => {
        const content = container.cloneNode(true);
        content.querySelector(`.${CONTROL_CLASS}`)?.remove();
        const text = content.innerText || content.textContent || "";
        if (!controller.speak(text)) {
            status.textContent = "There is no insight text to read.";
        }
    });
    pauseButton.addEventListener("click", () => controller.pause());
    resumeButton.addEventListener("click", () => controller.resume());
    stopButton.addEventListener("click", () => controller.stop());
    voiceSelect.addEventListener("change", () => controller.setVoiceByURI(voiceSelect.value));

    return controller;
}
