"use client";

import { useEffect, useRef, useState } from "react";

import {
  installSpeech,
  speechSupport,
  startLiveTranscript,
  type LiveTranscript,
  type SpeechSupport,
} from "@/features/notes/lib/speech";
import { CheckIcon } from "@/shared/ui/icons";

import { useTranscribePreview } from "@/features/notes/hooks";
import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { Select, Textarea } from "@/shared/ui/field";
import { MicIcon, StopIcon } from "@/shared/ui/icons";

const MAX_SECONDS = 120;
// Relative bar heights; the live input level scales them, so the nurse sees the mic hears her.
const BARS = [
  0.3, 0.55, 0.8, 0.45, 0.95, 0.6, 0.35, 0.75, 1, 0.5, 0.7, 0.85, 0.4, 0.6, 0.8, 0.45, 0.55, 0.3,
];
// Loudest frame RMS below this means the microphone delivered (near) silence. Speech is ~0.05+;
// a browser without OS microphone permission delivers exact zeros.
export const SILENCE_RMS = 0.003;

export function frameRms(samples: Float32Array): number {
  let sum = 0;
  for (const x of samples) sum += x * x;
  return Math.sqrt(sum / (samples.length || 1));
}

/** Watches the input level while recording. Returns a stop function that reports the peak. */
function meter(stream: MediaStream, onLevel: (level: number) => void): () => number {
  const ctx = new AudioContext();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  ctx.createMediaStreamSource(stream).connect(analyser);
  const samples = new Float32Array(analyser.fftSize);
  let peak = 0;
  let frame = 0;
  const tick = () => {
    analyser.getFloatTimeDomainData(samples);
    const rms = frameRms(samples);
    peak = Math.max(peak, rms);
    onLevel(Math.min(1, rms * 6));
    frame = requestAnimationFrame(tick);
  };
  tick();
  return () => {
    cancelAnimationFrame(frame);
    void ctx.close();
    return peak;
  };
}

const BLOCKED =
  "The browser has blocked the microphone for this site, so it will not ask again. " +
  "Click the icon on the left of the address bar → Microphone → Allow, then reload the page. " +
  "On a Mac also check System Settings → Privacy & Security → Microphone.";

/** A message the nurse can act on, by the DOMException name getUserMedia rejected with. */
export function micError(err: unknown): string {
  const name = err instanceof DOMException ? err.name : "";
  switch (name) {
    case "NotAllowedError":
    case "SecurityError":
      return BLOCKED;
    case "NotFoundError":
    case "OverconstrainedError":
      return "No microphone was found. Plug one in or pick another device, then try again.";
    case "NotReadableError":
    case "AbortError":
      return "The microphone is in use by another app, for example a call. Close it and try again.";
    default:
      return "Microphone not available. Allow access, or upload a file / type the note instead.";
  }
}

type Permission = "granted" | "denied" | "prompt" | "unknown";

/** What the browser will do when we ask for the microphone. Chrome never re-asks once blocked. */
function usePermission(): Permission {
  const [permission, setPermission] = useState<Permission>("unknown");
  useEffect(() => {
    let status: PermissionStatus | undefined;
    const update = () => setPermission(status?.state ?? "unknown");
    navigator.permissions
      ?.query({ name: "microphone" })
      .then((s) => {
        status = s;
        s.onchange = update;
        update();
      })
      .catch(() => setPermission("unknown")); // Firefox has no "microphone" permission name
    return () => {
      if (status) status.onchange = null;
    };
  }, []);
  return permission;
}

type Microphone = { id: string; label: string };

async function listMicrophones(): Promise<Microphone[]> {
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices
    .filter((d) => d.kind === "audioinput" && d.label) // labels are empty until permission is granted
    .map((d) => ({ id: d.deviceId, label: d.label }));
}

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((t) =>
    MediaRecorder.isTypeSupported(t),
  );
}

type State =
  | { kind: "idle" }
  | { kind: "recording"; seconds: number; device: string }
  | { kind: "recorded"; blob: Blob; url: string; seconds: number; silent: boolean; device: string }
  | { kind: "error"; message: string };

export type Recording = {
  blob: Blob;
  /** What the nurse confirmed was said: recognised on the device and corrected, or typed.
   *  Null when left empty, in which case the server transcribes the audio. */
  transcript: string | null;
};

/** Can this browser transcribe on the device? Cloud recognition is never used (patient names). */
function useSpeechSupport(): [SpeechSupport, () => Promise<void>] {
  const [support, setSupport] = useState<SpeechSupport>("unavailable");
  useEffect(() => {
    void speechSupport().then(setSupport);
  }, []);
  const install = async () => {
    setSupport("downloading");
    setSupport((await installSpeech()) ? "available" : "unavailable");
  };
  return [support, install];
}

export function Recorder({
  onSubmit,
  busy,
}: {
  onSubmit: (recording: Recording) => void;
  busy: boolean;
}) {
  const [state, setState] = useState<State>({ kind: "idle" });
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const stopMeter = useRef<(() => number) | null>(null);
  const live = useRef<LiveTranscript | null>(null);
  const [transcript, setTranscript] = useState("");
  const [heard, setHeard] = useState(false); // did on-device recognition run for this take?
  const [speechError, setSpeechError] = useState<string | null>(null);
  // Without a usable on-device transcript the server transcribes the take right away, so the
  // nurse reads and fixes the text before sending instead of discovering it on the review page.
  const preview = useTranscribePreview();
  const [source, setSource] = useState<"device" | "server" | null>(null);
  const [speech, installSpeechPack] = useSpeechSupport();
  const [level, setLevel] = useState(0);
  const permission = usePermission();
  const [microphones, setMicrophones] = useState<Microphone[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const supported = typeof window !== "undefined" && !!navigator.mediaDevices && !!pickMimeType();

  useEffect(() => {
    if (!supported) return;
    const refresh = () => void listMicrophones().then(setMicrophones);
    if (permission === "granted") refresh();
    navigator.mediaDevices.addEventListener("devicechange", refresh);
    return () => navigator.mediaDevices.removeEventListener("devicechange", refresh);
  }, [permission, supported]);

  useEffect(
    () => () => {
      if (timer.current) clearInterval(timer.current);
      stopMeter.current?.();
      recorder.current?.stream.getTracks().forEach((t) => t.stop());
    },
    [],
  );

  async function start() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: deviceId ? { deviceId: { exact: deviceId } } : true,
      });
      void listMicrophones().then(setMicrophones); // labels are known now
      const mimeType = pickMimeType();
      const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const chunks: Blob[] = [];
      const device = stream.getAudioTracks()[0]?.label || "Default microphone";
      let seconds = 0;
      stopMeter.current = meter(stream, setLevel);
      setSpeechError(null);
      setTranscript("");
      setSource(null);
      preview.reset();
      live.current =
        speech === "available" ? startLiveTranscript(setTranscript, setSpeechError) : null;
      setHeard(live.current !== null);
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = async () => {
        const peak = stopMeter.current?.() ?? 1;
        stopMeter.current = null;
        setLevel(0);
        stream.getTracks().forEach((t) => t.stop());
        if (timer.current) clearInterval(timer.current);
        let heardText = "";
        if (live.current) {
          heardText = await live.current.stop();
          live.current = null;
          setTranscript(heardText);
        }
        const blob = new Blob(chunks, { type: rec.mimeType.split(";")[0] });
        const silent = peak < SILENCE_RMS;
        setState({
          kind: "recorded",
          blob,
          url: URL.createObjectURL(blob),
          seconds,
          silent,
          device,
        });
        if (heardText.trim()) {
          setSource("device");
        } else if (!silent) {
          setSource(null);
          preview.mutate(blob, {
            onSuccess: (result) => {
              setTranscript(result.text);
              setSource("server");
            },
          });
        }
      };
      rec.start();
      recorder.current = rec;
      setState({ kind: "recording", seconds: 0, device });
      timer.current = setInterval(() => {
        seconds += 1;
        setState({ kind: "recording", seconds, device });
        if (seconds >= MAX_SECONDS) rec.stop();
      }, 1000);
    } catch (err) {
      setState({ kind: "error", message: micError(err) });
    }
  }

  const time = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  if (!supported) {
    return (
      <p className="text-ink-2 py-6 text-center">
        Recording is not supported in this browser. Upload a file or type the note instead.
      </p>
    );
  }

  const recording = state.kind === "recording";
  return (
    <div className="flex flex-col items-center gap-6 py-6">
      <div className="relative flex size-44 items-center justify-center">
        {recording && (
          <>
            <span
              aria-hidden="true"
              className="animate-pulse-ring absolute inset-4 rounded-full bg-red-500/30"
            />
            <span
              aria-hidden="true"
              className="animate-pulse-ring absolute inset-4 rounded-full bg-red-500/20 [animation-delay:600ms]"
            />
          </>
        )}
        {!recording && (
          <span
            aria-hidden="true"
            className="from-brand-soft absolute inset-0 rounded-full bg-gradient-to-b to-transparent"
          />
        )}
        {!recording ? (
          <button
            type="button"
            onClick={start}
            disabled={busy}
            className="ring-surface focus-visible:outline-brand-ring relative flex size-32 flex-col items-center justify-center gap-1 rounded-full bg-gradient-to-b from-teal-600 to-teal-800 text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.25),0_20px_40px_-12px_rgb(13_148_136/0.55)] ring-8 transition-transform hover:scale-[1.03] focus-visible:outline-4 focus-visible:outline-offset-4 disabled:opacity-50 motion-reduce:hover:scale-100"
          >
            <MicIcon size={34} strokeWidth={1.6} />
            <span className="text-sm font-semibold">
              {state.kind === "recorded" ? "Record again" : "Record"}
            </span>
          </button>
        ) : (
          <button
            type="button"
            onClick={() => recorder.current?.stop()}
            className="ring-surface relative flex size-32 flex-col items-center justify-center gap-1 rounded-full bg-gradient-to-b from-red-600 to-red-800 text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.2),0_20px_40px_-12px_rgb(220_38_38/0.55)] ring-8 focus-visible:outline-4 focus-visible:outline-offset-4 focus-visible:outline-red-600"
          >
            <StopIcon size={30} />
            <span className="text-sm font-semibold">Stop</span>
          </button>
        )}
      </div>

      <div aria-hidden="true" className="flex h-8 items-center gap-[4px]">
        {BARS.map((h, i) => (
          <span
            key={i}
            className={`w-[3px] rounded-full transition-[height] duration-75 ${
              recording ? "bg-red-500/80" : "bg-line-strong"
            }`}
            style={{ height: recording ? 4 + h * level * 28 : 4 }}
          />
        ))}
      </div>

      <p aria-live="polite" className="text-ink min-h-7 font-mono text-lg tabular-nums">
        {state.kind === "idle" && (
          <span className="text-ink-3 font-sans text-sm">
            Tap to start. Up to {MAX_SECONDS / 60} minutes.
          </span>
        )}
        {recording && (
          <>
            <span className="sr-only">Recording, </span>
            {time(state.seconds)} <span className="text-ink-3">/ {time(MAX_SECONDS)}</span>
          </>
        )}
        {state.kind === "recorded" && `Recorded ${time(state.seconds)}`}
      </p>
      {(state.kind === "recording" || state.kind === "recorded") && (
        <p className="text-ink-3 -mt-4 text-xs">Microphone: {state.device}</p>
      )}
      {recording && heard && !speechError && (
        <p
          aria-live="polite"
          aria-label="Live transcript"
          className="text-ink-2 min-h-12 w-full max-w-lg text-center text-[15px] leading-relaxed"
        >
          {transcript || (
            <span className="text-ink-3">
              Listening… say the patient&apos;s name and the values.
            </span>
          )}
        </p>
      )}
      {speechError && (
        <p
          role="status"
          className="w-full max-w-md text-center text-xs text-amber-800 dark:text-amber-200"
        >
          Live transcript stopped: {speechError}. You can type what you said after recording.
        </p>
      )}
      {!speechError && !(state.kind === "recorded" && preview.isPending) && (
        <p
          role="status"
          className="text-ink-3 flex w-full max-w-md items-center justify-center gap-1.5 text-center text-xs leading-relaxed"
        >
          {speech === "available" ? (
            <>
              <CheckIcon size={13} className="text-brand-text" />
              Live transcript on this device. Nothing you say leaves this computer before review.
            </>
          ) : speech === "downloadable" || speech === "downloading" ? (
            <span>
              Live transcript needs the on-device speech pack.{" "}
              <button
                type="button"
                onClick={() => void installSpeechPack()}
                disabled={speech === "downloading"}
                className="text-brand-text font-semibold underline-offset-2 hover:underline disabled:opacity-60"
              >
                {speech === "downloading" ? "Downloading…" : "Download it"}
              </button>{" "}
              (stays on this computer).
            </span>
          ) : (
            "No live transcript in this browser (it needs Chrome's on-device speech recognition). You can type what you said after recording."
          )}
        </p>
      )}
      {!recording && microphones.length > 1 && (
        <label className="text-ink-2 flex w-full max-w-md items-center gap-2 text-sm">
          <span className="shrink-0">Microphone</span>
          <Select
            size="sm"
            title="Microphone"
            className="min-w-0 flex-1"
            value={deviceId || microphones[0]?.id}
            onChange={setDeviceId}
            options={microphones.map((m) => ({ value: m.id, label: m.label }))}
          />
        </label>
      )}
      {permission === "denied" && state.kind !== "error" && (
        <p
          role="alert"
          className="w-full max-w-md text-center text-sm text-red-800 dark:text-red-200"
        >
          {BLOCKED}
        </p>
      )}
      {state.kind === "recorded" && state.silent && (
        <div
          role="alert"
          className="w-full max-w-md rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950 dark:border-amber-500/40 dark:bg-amber-950/40 dark:text-amber-50"
        >
          <p className="font-semibold">No sound was picked up.</p>
          <p className="mt-1 leading-relaxed">
            Check that the right microphone is selected and not muted, and that your browser may use
            it. On a Mac: System Settings → Privacy &amp; Security → Microphone. Then record again.
          </p>
        </div>
      )}
      {state.kind === "recorded" && (
        <div className="flex w-full flex-col items-center gap-4">
          <audio controls src={state.url} className="w-full max-w-md">
            <track kind="captions" />
          </audio>
          <label className="text-ink flex w-full max-w-md flex-col gap-2 text-sm font-medium">
            Transcript
            <span className="text-ink-3 -mt-1 text-xs font-normal" aria-live="polite">
              {preview.isPending
                ? "Transcribing on the server…"
                : source === "device"
                  ? "Recognised on this device. Fix anything the microphone got wrong before sending."
                  : source === "server"
                    ? `Transcribed on the server in ${((preview.data?.latency_ms ?? 0) / 1000).toFixed(1)} s. Fix anything that was misheard before sending.`
                    : preview.isError
                      ? `Could not transcribe: ${preview.error instanceof ApiError ? preview.error.message : "server error"}. Type what you said, or send the audio as is.`
                      : heard
                        ? "Nothing was recognised. Type what you said, or send the audio as is."
                        : "Type what you said, or send the audio as is and the server transcribes it."}
            </span>
            <Textarea
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              rows={3}
              disabled={preview.isPending}
              placeholder={preview.isPending ? "" : "What you said, in your own words"}
              className="p-3 text-[15px] font-normal"
            />
          </label>
          <Button
            onClick={() =>
              onSubmit({
                blob: state.blob,
                transcript: transcript.trim().length >= 3 ? transcript.trim() : null,
              })
            }
            disabled={busy || preview.isPending}
          >
            {busy
              ? "Uploading…"
              : transcript.trim().length >= 3
                ? "Use this recording and transcript"
                : "Use this recording"}
          </Button>
        </div>
      )}
      {state.kind === "error" && (
        <p
          role="alert"
          className="w-full max-w-sm text-center text-sm text-red-800 dark:text-red-200"
        >
          {state.message}
        </p>
      )}
    </div>
  );
}
