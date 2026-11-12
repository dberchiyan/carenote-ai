import { describe, expect, it } from "vitest";

import { joinTranscript, speechSupport, startLiveTranscript } from "@/features/notes/lib/speech";

describe("joinTranscript", () => {
  it("joins final sentences and the interim phrase, tidying punctuation", () => {
    expect(joinTranscript(["John,", " 80 pulse ,"], "headache")).toBe("John, 80 pulse, headache");
    expect(joinTranscript([], "")).toBe("");
  });
});

describe("on-device only", () => {
  it("reports unavailable when the browser has no local recognition, never falling back to the cloud", async () => {
    // jsdom has no SpeechRecognition at all; a browser with only cloud recognition has the
    // constructor but no `available()`: both must say unavailable.
    expect(await speechSupport()).toBe("unavailable");
    (window as unknown as { webkitSpeechRecognition: unknown }).webkitSpeechRecognition = class {};
    expect(await speechSupport()).toBe("unavailable");
    expect(startLiveTranscript(() => {})).toBeNull();
  });
});

describe("automated browsers", () => {
  it("skips the probe that crashes headless Chromium", async () => {
    Object.defineProperty(navigator, "webdriver", { value: true, configurable: true });
    (window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = class {
      static available() {
        throw new Error("must not be called");
      }
    };
    expect(await speechSupport()).toBe("unavailable");
  });
});
