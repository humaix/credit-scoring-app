"use client";

// Camera-first CNIC capture: live preview, retake, and the same basic
// quality checks the backend applies (dimensions + brightness), so bad
// captures are caught before submit. Falls back to a file input when no
// camera is available (permission denied, no webcam, insecure context).

import { useCallback, useEffect, useRef, useState, type ChangeEvent } from "react";

import { PrimaryButton, SecondaryButton } from "@/components/ui";

// mirrors backend/cnic_images.py
const MIN_WIDTH = 320;
const MIN_HEIGHT = 240;
const MIN_BRIGHTNESS = 40;
const MAX_SIDE = 1600; // upload fallback: downscale so payloads stay small

export default function CameraCapture({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  value: string | null;
  onChange: (value: string | null) => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [live, setLive] = useState(false);
  const [starting, setStarting] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [qualityError, setQualityError] = useState<string | null>(null);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setLive(false);
  }, []);

  // release the camera when the component unmounts
  useEffect(() => stopCamera, [stopCamera]);

  async function startCamera() {
    setQualityError(null);
    setCameraError(null);
    setStarting(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "environment",
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setLive(true);
    } catch {
      setCameraError(
        "Camera unavailable — allow camera access, or use the upload option below.",
      );
    } finally {
      setStarting(false);
    }
  }

  /** Quality-check a canvas frame and hand it to the parent as base64 JPEG. */
  function acceptCanvas(canvas: HTMLCanvasElement): boolean {
    if (canvas.width < MIN_WIDTH || canvas.height < MIN_HEIGHT) {
      setQualityError(
        `Image is too small (${canvas.width}×${canvas.height}) — retake it closer to the card.`,
      );
      return false;
    }
    const context = canvas.getContext("2d");
    if (!context) return false;
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    let sum = 0;
    let sampled = 0;
    for (let i = 0; i < pixels.length; i += 4 * 97) {
      // sample roughly every 97th pixel — plenty for a mean-luminance check
      sum += (pixels[i] + pixels[i + 1] + pixels[i + 2]) / 3;
      sampled += 1;
    }
    if (sampled > 0 && sum / sampled < MIN_BRIGHTNESS) {
      setQualityError("Image looks too dark — retake it in better lighting.");
      return false;
    }
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    onChange(dataUrl.slice(dataUrl.indexOf(",") + 1));
    setQualityError(null);
    return true;
  }

  function capture() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.drawImage(video, 0, 0);
    if (acceptCanvas(canvas)) stopCamera();
  }

  function retake() {
    onChange(null);
    setQualityError(null);
    void startCamera();
  }

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // allow picking the same file again
    if (!file) return;
    setQualityError(null);
    const reader = new FileReader();
    reader.onload = () => {
      const image = new Image();
      image.onload = () => {
        const scale = Math.min(
          1, MAX_SIDE / Math.max(image.width, image.height));
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(image.width * scale));
        canvas.height = Math.max(1, Math.round(image.height * scale));
        const context = canvas.getContext("2d");
        if (!context) return;
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        acceptCanvas(canvas);
      };
      image.onerror = () =>
        setQualityError("That file could not be read as an image.");
      image.src = String(reader.result);
    };
    reader.readAsDataURL(file);
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-slate-700">{label}</span>
        {value ? (
          <span className="text-xs font-semibold text-[#0e9f6e]">
            ✓ Captured
          </span>
        ) : (
          <span className="text-xs font-medium text-slate-500">Required</span>
        )}
      </div>
      {hint && <p className="mb-2 text-xs text-slate-500">{hint}</p>}

      {/* always mounted so the stream can attach the moment it starts */}
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        className={
          live && !value
            ? "w-full rounded-lg border border-slate-300 bg-black object-contain"
            : "hidden"
        }
      />

      {value ? (
        <div className="space-y-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`data:image/jpeg;base64,${value}`}
            alt={`${label} preview`}
            className="w-full rounded-lg border border-slate-200 bg-white object-contain"
          />
          <SecondaryButton type="button" onClick={retake} className="w-full">
            Retake photo
          </SecondaryButton>
        </div>
      ) : live ? (
        <div className="space-y-2">
          <PrimaryButton type="button" onClick={capture} className="w-full">
            Take photo
          </PrimaryButton>
          <SecondaryButton type="button" onClick={stopCamera} className="w-full">
            Cancel
          </SecondaryButton>
        </div>
      ) : (
        <div className="space-y-2">
          <PrimaryButton
            type="button"
            onClick={() => void startCamera()}
            loading={starting}
            className="w-full"
          >
            Open camera
          </PrimaryButton>
          {cameraError && (
            <p className="text-xs font-medium text-red-600">{cameraError}</p>
          )}
          <label className="block text-center text-xs font-medium text-slate-500">
            no camera?{" "}
            <span className="cursor-pointer font-semibold text-[#0e9f6e] underline">
              upload a photo instead
            </span>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={onFile}
            />
          </label>
        </div>
      )}

      {qualityError && (
        <p className="mt-2 text-xs font-medium text-red-600">{qualityError}</p>
      )}
    </div>
  );
}
