/**
 * Live transcript while recording, strictly on-device.
 *
 * The Web Speech API can also run in the cloud (Chrome sends audio to Google). That would leak
 * patient names before our redaction runs, so this module only ever asks for `processLocally`
 * recognition and reports "unavailable" when the browser cannot do it locally. The server
 * still transcribes the recording; the live text is a preview the nurse can correct and, when
 * no transcription provider is configured, the text the draft is built from.
 */

export type SpeechSupport = "available" | "downloadable" | "downloading" | "unavailable";

const LANG = "en-US";

// Minimal typings: lib.dom does not cover the on-device extensions.
interface RecognitionResult {
  readonly isFinal: boolean;
  readonly 0: { readonly transcript: string };
}
interface RecognitionEvent {
  readonly resultIndex: number;
  readonly results: ArrayLike<RecognitionResult>;
}
interface Recognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  processLocally: boolean;
  onresult: ((e: RecognitionEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
interface RecognitionStatic {
  new (): Recognition;
  available?: (options: { langs: string[]; processLocally: boolean }) => Promise<SpeechSupport>;
  install?: (options: { langs: string[]; processLocally: boolean }) => Promise<boolean>;
}

function ctor(): RecognitionStatic | undefined {
  if (typeof window === "undefined") return undefined;
  // Headless Chromium crashes the renderer on the on-device probe (a headed browser answers it
  // fine), and automation can spoof its user agent. Any automated browser gets "no live
  // transcript" rather than a crashed page; the end-to-end tests cover the server path.
  if (navigator.webdriver || /HeadlessChrome/.test(navigator.userAgent)) return undefined;
  const w = window as unknown as {
    SpeechRecognition?: RecognitionStatic;
    webkitSpeechRecognition?: RecognitionStatic;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

/** Whether this browser can transcribe on the device. Never reports cloud recognition. */
export async function speechSupport(): Promise<SpeechSupport> {
  const Rec = ctor();
  if (!Rec?.available) return "unavailable";
  try {
    return await Rec.available({ langs: [LANG], processLocally: true });
  } catch {
    return "unavailable";
  }
}

/** Download the on-device language pack (Chrome asks the user). Resolves once usable. */
export async function installSpeech(): Promise<boolean> {
  const Rec = ctor();
  if (!Rec?.install) return false;
  try {
    return await Rec.install({ langs: [LANG], processLocally: true });
  } catch {
    return false;
  }
}

/** Final sentences plus the phrase still being recognised, as one readable string. */
export function joinTranscript(finals: string[], interim: string): string {
  return [...finals, interim]
    .map((s) => s.trim())
    .filter(Boolean)
    .join(" ")
    .replace(/\s+([,.;:])/g, "$1");
}

export type LiveTranscript = {
  /** Stop listening; resolves to the final text (empty when nothing was recognised). */
  stop: () => Promise<string>;
};

/**
 * Start on-device recognition next to the MediaRecorder. `onUpdate` receives the running text.
 * Returns null when the browser cannot recognise locally.
 */
/** Why recognition stopped, in words the nurse can act on. Null for routine, harmless events. */
export function describeSpeechError(code: string): string | null {
  switch (code) {
    case "no-speech":
    case "aborted":
      return null;
    case "not-allowed":
    case "service-not-allowed":
      return "the browser did not allow speech recognition";
    case "audio-capture":
      return "the microphone could not be shared with speech recognition";
    case "language-not-supported":
      return "English is not installed for on-device recognition";
    case "network":
      return "it needed the network, which is not allowed here";
    default:
      return `it reported "${code}"`;
  }
}

export function startLiveTranscript(
  onUpdate: (text: string) => void,
  onError: (message: string) => void = () => {},
): LiveTranscript | null {
  const Rec = ctor();
  if (!Rec?.available) return null;
  const rec = new Rec();
  rec.lang = LANG;
  rec.continuous = true;
  rec.interimResults = true;
  rec.processLocally = true;
  const finals: string[] = [];
  let interim = "";
  let stopping = false;
  let ended: (() => void) | null = null;
  rec.onresult = (e) => {
    interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (!r) continue;
      if (r.isFinal) finals.push(r[0].transcript);
      else interim += r[0].transcript;
    }
    onUpdate(joinTranscript(finals, interim));
  };
  rec.onerror = (e) => {
    const message = describeSpeechError(e.error);
    if (message) {
      stopping = true; // do not restart after a real failure
      onError(message);
    }
  };
  rec.onend = () => {
    if (stopping) {
      ended?.();
      return;
    }
    // Continuous recognition can end on its own (a long pause); keep listening until Stop.
    try {
      rec.start();
    } catch {
      ended?.();
    }
  };
  try {
    rec.start();
  } catch {
    return null;
  }
  return {
    stop: () =>
      new Promise((resolve) => {
        stopping = true;
        ended = () => resolve(joinTranscript(finals, interim));
        rec.stop();
        // Chrome fires `onend` quickly; never leave the nurse waiting if it does not.
        setTimeout(() => resolve(joinTranscript(finals, interim)), 1500);
      }),
  };
}
