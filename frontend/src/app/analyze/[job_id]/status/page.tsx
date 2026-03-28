"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getJobStatus } from "@/lib/api";
import type { JobStage, JobStatusResponse } from "@/types/analysis";

const TOKEN_PLACEHOLDER = process.env.NEXT_PUBLIC_DEV_TOKEN ?? "";
const POLL_INTERVAL_MS = 3000;

const STAGES: { key: JobStage; label: string }[] = [
  { key: "queued",          label: "Queued" },
  { key: "pose_extraction", label: "Extracting pose" },
  { key: "phase_detection", label: "Detecting stroke phases" },
  { key: "normalization",   label: "Normalizing keypoints" },
  { key: "complete",        label: "Analysis complete" },
];

function stageIndex(stage: JobStage): number {
  return STAGES.findIndex((s) => s.key === stage);
}

export default function JobStatusPage() {
  const { job_id } = useParams<{ job_id: string }>();
  const router = useRouter();

  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const poll = async () => {
    try {
      const data = await getJobStatus(TOKEN_PLACEHOLDER, job_id);
      setJob(data);

      if (data.status === "complete" && data.report_id) {
        clearInterval(intervalRef.current!);
        router.push(`/report/${data.report_id}`);
      } else if (data.status === "failed") {
        clearInterval(intervalRef.current!);
      }
    } catch {
      setError("Could not fetch job status. Retrying...");
    }
  };

  useEffect(() => {
    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return () => clearInterval(intervalRef.current!);
  }, [job_id]);

  const currentStageIdx = job ? stageIndex(job.stage) : 0;

  return (
    <main className="min-h-screen bg-white flex items-center justify-center px-4">
      <div className="max-w-md w-full space-y-8 text-center">
        {/* Spinner / check */}
        {job?.status === "failed" ? (
          <div className="flex justify-center">
            <span className="text-5xl">❌</span>
          </div>
        ) : job?.status === "complete" ? (
          <div className="flex justify-center">
            <span className="w-16 h-16 rounded-full bg-green-500 flex items-center justify-center">
              <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
              </svg>
            </span>
          </div>
        ) : (
          <div className="flex justify-center">
            <div className="w-16 h-16 rounded-full border-4 border-green-100 border-t-green-500 animate-spin" />
          </div>
        )}

        {/* Title */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {job?.status === "failed"
              ? "Analysis failed"
              : job?.status === "complete"
              ? "Analysis ready"
              : "Analyzing your stroke…"}
          </h1>
          {job?.status === "complete" ? (
            <p className="mt-1 text-sm text-gray-500">Redirecting to your report…</p>
          ) : job?.status === "failed" ? (
            <p className="mt-1 text-sm text-red-500">
              {job.warning_code ?? "Something went wrong. Please try uploading again."}
            </p>
          ) : (
            <p className="mt-1 text-sm text-gray-500">
              This usually takes under 90 seconds. You can leave this page and come back.
            </p>
          )}
        </div>

        {/* Stage stepper */}
        {job && job.status !== "failed" && (
          <ol className="space-y-3 text-left">
            {STAGES.map((s, idx) => {
              const done = idx < currentStageIdx;
              const active = idx === currentStageIdx;
              return (
                <li key={s.key} className="flex items-center gap-3">
                  <span
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                      done
                        ? "bg-green-500 text-white"
                        : active
                        ? "bg-green-100 text-green-600 ring-2 ring-green-400"
                        : "bg-gray-100 text-gray-400"
                    }`}
                  >
                    {done ? "✓" : idx + 1}
                  </span>
                  <span
                    className={`text-sm ${
                      done ? "text-gray-400 line-through" : active ? "text-gray-900 font-medium" : "text-gray-400"
                    }`}
                  >
                    {s.label}
                  </span>
                </li>
              );
            })}
          </ol>
        )}

        {/* Poor angle warning */}
        {job?.warning_code === "WARNING_POOR_ANGLE" && (
          <div className="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-left text-sm text-amber-800">
            <strong>Tip:</strong> The camera angle in this video may reduce accuracy. For best results, film side-on at hip height, 10–15 feet away.
          </div>
        )}

        {error && <p className="text-xs text-gray-400">{error}</p>}

        {job?.status === "failed" && (
          <button
            type="button"
            onClick={() => router.push("/analyze/new")}
            className="w-full py-3 rounded-xl bg-green-500 text-white font-medium hover:bg-green-600 transition-colors"
          >
            Try again
          </button>
        )}
      </div>
    </main>
  );
}
