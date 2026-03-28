"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ShotTypeSelector from "@/components/analyze/ShotTypeSelector";
import ProPlayerPicker from "@/components/analyze/ProPlayerPicker";
import VideoDropzone from "@/components/analyze/VideoDropzone";
import UploadProgressBar from "@/components/analyze/UploadProgressBar";
import { fetchProPlayers, uploadVideo } from "@/lib/api";
import type { ProPlayer, ShotType } from "@/types/analysis";

// TODO: Replace with real Supabase session token
const TOKEN_PLACEHOLDER = process.env.NEXT_PUBLIC_DEV_TOKEN ?? "";

export default function NewAnalysisPage() {
  const router = useRouter();

  const [shotType, setShotType] = useState<ShotType>("serve");
  const [players, setPlayers] = useState<ProPlayer[]>([]);
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadPct, setUploadPct] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // Reload players when shot type changes
  useEffect(() => {
    setSelectedPlayerId(null);
    fetchProPlayers(TOKEN_PLACEHOLDER, shotType)
      .then(setPlayers)
      .catch(() => setPlayers([]));
  }, [shotType]);

  const canSubmit = selectedPlayerId && selectedFile && !uploading;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setApiError(null);
    setUploading(true);
    setUploadPct(0);

    try {
      const result = await uploadVideo(
        TOKEN_PLACEHOLDER,
        selectedFile,
        shotType,
        selectedPlayerId,
        setUploadPct,
      );
      router.push(`/analyze/${result.job_id}/status`);
    } catch (err: unknown) {
      const detail = (err as { detail?: { message?: string } })?.detail;
      setApiError(detail?.message ?? "Upload failed. Please try again.");
      setUploading(false);
    }
  };

  return (
    <main className="min-h-screen bg-white">
      <div className="max-w-2xl mx-auto px-4 py-10 space-y-10">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Analyze my stroke</h1>
          <p className="mt-1 text-gray-500 text-sm">
            Upload a video clip and compare your technique against a pro player.
          </p>
        </div>

        {/* Step 1 — Shot type */}
        <ShotTypeSelector value={shotType} onChange={setShotType} />

        {/* Step 2 — Pro player */}
        <ProPlayerPicker
          players={players}
          selectedId={selectedPlayerId}
          onSelect={setSelectedPlayerId}
        />

        {/* Step 3 — Video */}
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Your video
          </h2>
          {!selectedFile ? (
            <VideoDropzone
              onFile={setSelectedFile}
              disabled={uploading}
            />
          ) : (
            <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span className="text-sm text-gray-700 truncate max-w-xs">{selectedFile.name}</span>
                </div>
                {!uploading && (
                  <button
                    type="button"
                    onClick={() => setSelectedFile(null)}
                    className="text-xs text-gray-400 hover:text-gray-600"
                  >
                    Remove
                  </button>
                )}
              </div>
              {uploading && (
                <UploadProgressBar pct={uploadPct} filename={selectedFile.name} />
              )}
            </div>
          )}
        </div>

        {/* Error */}
        {apiError && (
          <p className="text-sm text-red-600 bg-red-50 rounded-xl px-4 py-3">{apiError}</p>
        )}

        {/* Submit */}
        <button
          type="button"
          disabled={!canSubmit}
          onClick={handleSubmit}
          className="w-full py-4 rounded-2xl bg-green-500 text-white font-semibold text-base
            hover:bg-green-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {uploading ? "Uploading..." : "Analyze stroke"}
        </button>
      </div>
    </main>
  );
}
