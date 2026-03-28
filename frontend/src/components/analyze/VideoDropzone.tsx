"use client";

import { useRef, useState } from "react";
import CameraGuideModal from "./CameraGuideModal";

const MAX_DURATION_SECONDS = 60;
const WARN_SIZE_BYTES = 100 * 1024 * 1024; // 100 MB
const ALLOWED_TYPES = ["video/mp4", "video/quicktime"];

interface Props {
  onFile: (file: File) => void;
  disabled?: boolean;
}

export default function VideoDropzone({ onFile, disabled }: Props) {
  const [showGuide, setShowGuide] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validate = (file: File): Promise<string | null> =>
    new Promise((resolve) => {
      if (!ALLOWED_TYPES.includes(file.type)) {
        return resolve("Only MP4 and MOV files are supported.");
      }
      if (file.size > WARN_SIZE_BYTES) {
        // Non-blocking warning — proceed anyway; server enforces hard limit
      }
      const video = document.createElement("video");
      video.preload = "metadata";
      video.onloadedmetadata = () => {
        URL.revokeObjectURL(video.src);
        if (video.duration > MAX_DURATION_SECONDS) {
          resolve(`Video must be ${MAX_DURATION_SECONDS} seconds or shorter (yours is ${Math.round(video.duration)}s).`);
        } else {
          resolve(null);
        }
      };
      video.onerror = () => { URL.revokeObjectURL(video.src); resolve(null); };
      video.src = URL.createObjectURL(file);
    });

  const handleFile = async (file: File) => {
    setError(null);
    const err = await validate(file);
    if (err) { setError(err); return; }
    onFile(file);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  };

  return (
    <>
      {showGuide && (
        <CameraGuideModal
          onClose={() => setShowGuide(false)}
          onConfirm={() => {
            setShowGuide(false);
            inputRef.current?.click();
          }}
        />
      )}

      {/* Input lives outside the clickable dropzone so its click events
          never bubble up and re-trigger setShowGuide */}
      <input
        ref={inputRef}
        type="file"
        accept="video/mp4,video/quicktime,.mp4,.mov"
        className="hidden"
        onChange={onInputChange}
      />

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`relative flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-12 text-center transition-colors cursor-pointer
          ${dragOver ? "border-green-400 bg-green-50" : "border-gray-300 bg-gray-50 hover:border-gray-400"}
          ${disabled ? "opacity-50 pointer-events-none" : ""}`}
        onClick={() => !disabled && setShowGuide(true)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && !disabled && setShowGuide(true)}
      >
        <svg className="w-10 h-10 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M12 18.75H4.5a2.25 2.25 0 01-2.25-2.25V7.5A2.25 2.25 0 014.5 5.25H12a2.25 2.25 0 012.25 2.25v9a2.25 2.25 0 01-2.25 2.25z" />
        </svg>
        <div>
          <p className="font-medium text-gray-700">Drop your video here</p>
          <p className="text-sm text-gray-400 mt-1">or click to browse — MP4 or MOV, max 60 seconds</p>
        </div>
      </div>

      {error && (
        <p className="mt-2 text-sm text-red-600">{error}</p>
      )}
    </>
  );
}
