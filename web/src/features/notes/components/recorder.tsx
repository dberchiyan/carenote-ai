"use client";

import { useEffect, useRef, useState } from "react";

import {
  installSpeech,
  speechSupport,
  startLiveTranscript,
  type LiveTranscript,
  type SpeechSupport,
} from "@/features/notes/lib/speech";

import { useTranscribePreview } from "@/features/notes/hooks";
import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { Select, Textarea } from "@/shared/ui/field";
import {
  CheckIcon,
  LockIcon,
  MicIcon,
  PauseIcon,
  PlayIcon,
  SparkIcon,
  StopIcon,
} from "@/shared/ui/icons";

const MAX_SECONDS = 120;
// Relative bar heights, mirrored around the centre; the live input level scales them.
const HALF = [0.25, 0.4, 0.3, 0.55, 0.45, 0.7, 0.6, 0.85, 0.75, 1, 0.9, 0.95, 0.8, 1];
const METER = [...HALF, ...HALF.slice().reverse()];
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

  /** After a take (recorded or the sample): keep the audio and get its transcript. */
  function finishTake(
    blob: Blob,
    seconds: number,
    silent: boolean,
    device: string,
    heardText = "",
  ) {
    setState({ kind: "recorded", blob, url: URL.createObjectURL(blob), seconds, silent, device });
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
  }

  /** No microphone (a laptop in a meeting room, a locked-down browser): use a synthetic take. */
  async function loadSample() {
    try {
      const response = await fetch("/samples/ward-round.wav");
      if (!response.ok) throw new Error(String(response.status));
      const blob = new Blob([await response.arrayBuffer()], { type: "audio/wav" });
      setTranscript("");
      setHeard(false);
      setSpeechError(null);
      preview.reset();
      finishTake(blob, 5, false, "Sample recording (synthetic)");
    } catch {
      setState({ kind: "error", message: "The sample recording could not be loaded." });
    }
  }

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
        finishTake(blob, seconds, peak < SILENCE_RMS, device, heardText);
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
  const recorded = state.kind === "recorded";
  const progress = recording ? state.seconds / MAX_SECONDS : 0;

  return (
    <div className="flex flex-col items-center gap-3">
      {/* The stage: backdrop, time ring, level halo and the one button. */}
      <div className="relative flex size-48 items-center justify-center sm:size-52">
        <span
          aria-hidden="true"
          className={`absolute inset-0 rounded-full transition-colors duration-500 ${
            recording
              ? "bg-[radial-gradient(closest-side,rgb(239_68_68/0.14),transparent)]"
              : "bg-[radial-gradient(closest-side,var(--brand-soft),transparent)]"
          }`}
        />
        {recording && (
          <>
            <span
              aria-hidden="true"
              className="animate-pulse-ring absolute inset-7 rounded-full bg-red-500/25"
            />
            <span
              aria-hidden="true"
              className="animate-pulse-ring absolute inset-7 rounded-full bg-red-500/15 [animation-delay:600ms]"
            />
            <span
              aria-hidden="true"
              className="absolute inset-6 rounded-full bg-red-500/15 transition-transform duration-75 motion-reduce:hidden"
              style={{ transform: `scale(${1 + level * 0.35})` }}
            />
          </>
        )}
        <svg
          aria-hidden="true"
          viewBox="0 0 100 100"
          className={`absolute inset-1.5 -rotate-90 transition-opacity duration-300 ${
            recording ? "opacity-100" : "opacity-0"
          }`}
        >
          <circle cx="50" cy="50" r="47" className="stroke-line" strokeWidth="1.5" fill="none" />
          <circle
            cx="50"
            cy="50"
            r="47"
            className="stroke-red-500 transition-[stroke-dashoffset] duration-1000 ease-linear"
            strokeWidth="2.5"
            strokeLinecap="round"
            fill="none"
            strokeDasharray={2 * Math.PI * 47}
            strokeDashoffset={2 * Math.PI * 47 * (1 - progress)}
          />
        </svg>
        {!recording ? (
          <button
            type="button"
            onClick={start}
            disabled={busy}
            className="ring-surface focus-visible:outline-brand-ring relative flex size-28 flex-col items-center justify-center gap-1 rounded-full bg-gradient-to-b from-teal-600 to-teal-800 text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.25),0_20px_40px_-12px_rgb(13_148_136/0.55)] ring-8 transition-transform hover:scale-[1.03] focus-visible:outline-4 focus-visible:outline-offset-4 disabled:opacity-50 motion-reduce:hover:scale-100"
          >
            <MicIcon size={30} strokeWidth={1.6} />
            <span className="text-sm font-semibold">{recorded ? "Record again" : "Record"}</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={() => recorder.current?.stop()}
            className="ring-surface relative flex size-28 flex-col items-center justify-center gap-1 rounded-full bg-gradient-to-b from-red-600 to-red-800 text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.2),0_20px_40px_-12px_rgb(220_38_38/0.55)] ring-8 focus-visible:outline-4 focus-visible:outline-offset-4 focus-visible:outline-red-600"
          >
            <StopIcon size={26} />
            <span className="text-sm font-semibold">Stop</span>
          </button>
        )}
      </div>

      {/* Symmetric level meter: the nurse sees the microphone hears her. */}
      <div aria-hidden="true" className="-mt-3 flex h-8 items-center gap-[3px]">
        {METER.map((h, i) => (
          <span
            key={i}
            className={`w-[3px] rounded-full transition-[height,background-color] duration-75 ${
              recording ? "bg-red-500/80" : recorded ? "bg-brand/40" : "bg-line-strong"
            }`}
            style={{ height: recording ? 4 + h * level * 28 : recorded ? 4 + h * 10 : 4 }}
          />
        ))}
      </div>

      <div aria-live="polite" className="-mt-2 flex min-h-7 flex-col items-center gap-0.5">
        {state.kind === "idle" && (
          <p className="text-ink-3 text-sm">Tap to start. Up to {MAX_SECONDS / 60} minutes.</p>
        )}
        {recording && (
          <p className="text-ink flex items-center gap-3 font-mono text-2xl font-medium tabular-nums">
            <span className="text-bad inline-flex items-center gap-1.5 font-sans text-xs font-bold tracking-widest uppercase">
              <span className="size-2 animate-pulse rounded-full bg-red-500 motion-reduce:animate-none" />
              Rec
            </span>
            <span>
              <span className="sr-only">Recording, </span>
              {time(state.seconds)}
            </span>
            <span className="text-ink-3 text-sm">{time(MAX_SECONDS - state.seconds)} left</span>
          </p>
        )}
        {recorded && (
          <p className="text-ink font-mono text-lg tabular-nums">Recorded {time(state.seconds)}</p>
        )}
        {(recording || recorded) && (
          <p className="text-ink-3 text-xs">Microphone: {state.device}</p>
        )}
      </div>

      {recording && heard && !speechError && (
        <div className="bg-surface-2 ring-line w-full max-w-lg rounded-2xl px-4 py-3 ring-1 ring-inset">
          <p className="eyebrow text-brand-text mb-1.5 flex items-center gap-1.5">
            <CheckIcon size={12} />
            Live transcript · on this device
          </p>
          <p
            aria-live="polite"
            aria-label="Live transcript"
            className="text-ink min-h-12 text-[15px] leading-relaxed"
          >
            {transcript || (
              <span className="text-ink-3">
                Listening… say the patient&apos;s name and the values.
              </span>
            )}
          </p>
        </div>
      )}

      {state.kind === "idle" && (
        <p className="text-ink-2 max-w-xl text-center text-sm leading-relaxed">
          <span className="eyebrow mr-1.5">Say something like</span>“Mrs. Anna Keller, blood
          pressure 150 over 90, pulse 88, temp 37.9, headache, gave 500 mg paracetamol.”
        </p>
      )}

      {speechError && (
        <p role="status" className="text-warn-fg w-full max-w-md text-center text-xs">
          Live transcript stopped: {speechError}. You can type what you said after recording.
        </p>
      )}
      <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2">
        {(state.kind === "idle" || state.kind === "error") && (
          <button
            type="button"
            onClick={() => void loadSample()}
            disabled={busy}
            className="text-brand-text hover:bg-brand-soft focus-visible:outline-brand-ring inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium focus-visible:outline-2 disabled:opacity-50"
          >
            <SparkIcon size={14} />
            No microphone? Use a sample recording
          </button>
        )}
        {!speechError && !recorded && (
          <p
            role="status"
            className="bg-surface-2 text-ink-2 ring-line inline-flex max-w-md items-center gap-1.5 rounded-full px-3 py-1.5 text-center text-xs ring-1 ring-inset"
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
              <>
                <LockIcon size={13} className="text-ink-3 shrink-0" />
                No live transcript in this browser. You can type what you said after recording.
              </>
            )}
          </p>
        )}
      </div>
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
        <p role="alert" className="text-bad-fg w-full max-w-md text-center text-sm">
          {BLOCKED}
        </p>
      )}
      {recorded && state.silent && (
        <div
          role="alert"
          className="border-warn-line bg-warn-soft text-warn-fg w-full max-w-md rounded-xl border px-4 py-3 text-sm"
        >
          <p className="font-semibold">No sound was picked up.</p>
          <p className="mt-1 leading-relaxed">
            Check that the right microphone is selected and not muted, and that your browser may use
            it. On a Mac: System Settings → Privacy &amp; Security → Microphone. Then record again.
          </p>
        </div>
      )}
      {recorded && (
        <div className="card animate-rise w-full max-w-xl p-4 sm:p-5">
          <Player src={state.url} seconds={state.seconds} />
          <label className="text-ink mt-5 flex flex-col gap-2 text-sm font-medium">
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
              className={`p-3 text-[15px] font-normal ${preview.isPending ? "skeleton" : ""}`}
            />
          </label>
          <Button
            className="mt-4 w-full"
            onClick={() =>
              onSubmit({
                blob: state.blob,
                transcript: transcript.trim().length >= 3 ? transcript.trim() : null,
              })
            }
            disabled={busy || preview.isPending}
          >
            <SparkIcon size={16} />
            {busy
              ? "Uploading…"
              : transcript.trim().length >= 3
                ? "Use this recording and transcript"
                : "Use this recording"}
          </Button>
        </div>
      )}
      {state.kind === "error" && (
        <p role="alert" className="text-bad-fg w-full max-w-sm text-center text-sm">
          {state.message}
        </p>
      )}
    </div>
  );
}

/** Play back the take: one button, a thin progress bar and the time, instead of the browser's
 *  own control. The audio element stays in the DOM for tests and assistive tech. */
function Player({ src, seconds }: { src: string; seconds: number }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [known, setKnown] = useState(0);
  // Chrome reports no duration for a MediaRecorder WebM; the timer's count is close enough.
  const duration = known > 0 && Number.isFinite(known) ? known : seconds;
  const format = (s: number) =>
    `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  const toggle = () => {
    const el = audio.current;
    if (!el) return;
    if (el.paused) void el.play();
    else el.pause();
  };
  return (
    <div className="flex items-center gap-3">
      <audio
        ref={audio}
        src={src}
        preload="metadata"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPosition(0)}
        onTimeUpdate={(e) => setPosition(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setKnown(e.currentTarget.duration)}
        onDurationChange={(e) => setKnown(e.currentTarget.duration)}
      >
        <track kind="captions" />
      </audio>
      <button
        type="button"
        onClick={toggle}
        aria-label={playing ? "Pause" : "Play"}
        className="bg-brand text-brand-fg hover:bg-brand-strong focus-visible:outline-brand-ring flex size-10 shrink-0 items-center justify-center rounded-full transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
      >
        {playing ? <PauseIcon size={18} /> : <PlayIcon size={18} />}
      </button>
      <input
        type="range"
        aria-label="Position"
        min={0}
        max={duration || 1}
        step={0.1}
        value={Math.min(position, duration || 1)}
        onChange={(e) => {
          const t = Number(e.target.value);
          setPosition(t);
          if (audio.current) audio.current.currentTime = t;
        }}
        className="accent-brand h-1.5 min-w-0 flex-1 cursor-pointer"
      />
      <span className="text-ink-3 shrink-0 font-mono text-xs tabular-nums">
        {format(position)} / {format(duration)}
      </span>
    </div>
  );
}
