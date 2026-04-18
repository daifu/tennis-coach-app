"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchJobHistory } from "@/lib/api";
import type { JobHistoryItem } from "@/types/analysis";

const TOKEN_PLACEHOLDER = process.env.NEXT_PUBLIC_DEV_TOKEN ?? "";

const SHOT_LABELS: Record<string, string> = {
  serve: "Serve",
  forehand: "Forehand",
  backhand: "Backhand",
  volley: "Volley",
};

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    complete: "bg-green-50 text-green-700",
    processing: "bg-blue-50 text-blue-700",
    queued: "bg-gray-100 text-gray-600",
    failed: "bg-red-50 text-red-600",
  };
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${styles[status] ?? styles.queued}`}>
      {status}
    </span>
  );
}

function ScorePill({ score }: { score: number | null }) {
  if (score === null) return null;
  const color = score >= 70 ? "text-green-600" : score >= 45 ? "text-amber-600" : "text-red-500";
  return <span className={`text-sm font-semibold ${color}`}>{Math.round(score)}%</span>;
}

function HistoryRow({ item, onClick }: { item: JobHistoryItem; onClick: () => void }) {
  const date = new Date(item.created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <button
      onClick={onClick}
      disabled={item.status !== "complete"}
      className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50
        transition-colors border-b border-gray-100 last:border-0 text-left
        disabled:cursor-default"
    >
      <div className="flex items-center gap-4 min-w-0">
        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
          <span className="text-xs font-bold text-green-700">
            {(SHOT_LABELS[item.shot_type] ?? item.shot_type).slice(0, 2).toUpperCase()}
          </span>
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-900 truncate">
            {SHOT_LABELS[item.shot_type] ?? item.shot_type}
          </p>
          <p className="text-xs text-gray-400 truncate">vs {item.pro_player_name} &middot; {date}</p>
        </div>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0 ml-4">
        <ScorePill score={item.similarity_score} />
        <StatusBadge status={item.status} />
        {item.status === "complete" && (
          <svg className="w-4 h-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        )}
      </div>
    </button>
  );
}

export default function HistoryPage() {
  const router = useRouter();
  const [items, setItems] = useState<JobHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJobHistory(TOKEN_PLACEHOLDER)
      .then((data) => setItems(data.jobs))
      .catch(() => setError("Failed to load history."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen bg-white">
      <div className="max-w-2xl mx-auto px-4 py-10 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold text-gray-900">History</h1>
          <button
            onClick={() => router.push("/analyze/new")}
            className="px-4 py-2 rounded-xl bg-green-500 text-white text-sm font-semibold
              hover:bg-green-600 transition-colors"
          >
            + New analysis
          </button>
        </div>

        {loading && (
          <div className="flex justify-center py-16">
            <div className="w-8 h-8 border-4 border-green-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-xl px-4 py-3">{error}</p>
        )}

        {!loading && !error && items.length === 0 && (
          <div className="text-center py-16 space-y-4">
            <p className="text-gray-500">No analyses yet.</p>
            <button
              onClick={() => router.push("/analyze/new")}
              className="text-sm text-green-600 underline"
            >
              Analyze your first stroke
            </button>
          </div>
        )}

        {!loading && items.length > 0 && (
          <div className="rounded-2xl border border-gray-200 overflow-hidden">
            {items.map((item) => (
              <HistoryRow
                key={item.job_id}
                item={item}
                onClick={() => {
                  if (item.report_id) router.push(`/report/${item.report_id}`);
                }}
              />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
