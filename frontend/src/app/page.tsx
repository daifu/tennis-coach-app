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

function RecentRow({ item, onClick }: { item: JobHistoryItem; onClick: () => void }) {
  const date = new Date(item.created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
  const score = item.similarity_score;
  const scoreColor = score === null ? "" : score >= 70 ? "text-green-600" : score >= 45 ? "text-amber-600" : "text-red-500";

  return (
    <button
      onClick={onClick}
      disabled={item.status !== "complete"}
      className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-gray-50
        rounded-xl transition-colors text-left disabled:cursor-default"
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex-shrink-0 w-9 h-9 rounded-full bg-green-100 flex items-center justify-center">
          <span className="text-xs font-bold text-green-700">
            {(SHOT_LABELS[item.shot_type] ?? item.shot_type).slice(0, 2).toUpperCase()}
          </span>
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">
            {SHOT_LABELS[item.shot_type] ?? item.shot_type} vs {item.pro_player_name}
          </p>
          <p className="text-xs text-gray-400">{date}</p>
        </div>
      </div>
      {score !== null && (
        <span className={`text-sm font-bold flex-shrink-0 ml-2 ${scoreColor}`}>
          {Math.round(score)}%
        </span>
      )}
    </button>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [recentJobs, setRecentJobs] = useState<JobHistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);

  useEffect(() => {
    fetchJobHistory(TOKEN_PLACEHOLDER)
      .then((data) => setRecentJobs(data.jobs.slice(0, 5)))
      .catch(() => setRecentJobs([]))
      .finally(() => setLoadingHistory(false));
  }, []);

  const completedJobs = recentJobs.filter((j) => j.status === "complete");
  const avgScore =
    completedJobs.length > 0 && completedJobs.every((j) => j.similarity_score !== null)
      ? Math.round(completedJobs.reduce((s, j) => s + (j.similarity_score ?? 0), 0) / completedJobs.length)
      : null;

  return (
    <main className="min-h-screen bg-white">
      <div className="max-w-2xl mx-auto px-4 py-10 space-y-10">
        {/* Hero */}
        <div className="space-y-2">
          <h1 className="text-3xl font-bold text-gray-900">TennisCoach AI</h1>
          <p className="text-gray-500 text-sm">
            Upload a stroke video and get instant biomechanical coaching compared to a pro.
          </p>
        </div>

        {/* Stats strip */}
        {!loadingHistory && completedJobs.length > 0 && (
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-2xl border border-gray-200 px-5 py-4">
              <p className="text-xs text-gray-400 uppercase tracking-wide">Sessions</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">{completedJobs.length}</p>
            </div>
            {avgScore !== null && (
              <div className="rounded-2xl border border-gray-200 px-5 py-4">
                <p className="text-xs text-gray-400 uppercase tracking-wide">Avg score</p>
                <p className={`text-3xl font-bold mt-1 ${avgScore >= 70 ? "text-green-600" : avgScore >= 45 ? "text-amber-600" : "text-red-500"}`}>
                  {avgScore}%
                </p>
              </div>
            )}
          </div>
        )}

        {/* Primary CTA */}
        <button
          onClick={() => router.push("/analyze/new")}
          className="w-full py-5 rounded-2xl bg-green-500 text-white font-semibold text-lg
            hover:bg-green-600 transition-colors"
        >
          Analyze my stroke
        </button>

        {/* Recent analyses */}
        {!loadingHistory && recentJobs.length > 0 && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Recent</h2>
              <button
                onClick={() => router.push("/history")}
                className="text-xs text-green-600 hover:underline"
              >
                See all
              </button>
            </div>
            <div className="rounded-2xl border border-gray-200 overflow-hidden divide-y divide-gray-100">
              {recentJobs.map((item) => (
                <RecentRow
                  key={item.job_id}
                  item={item}
                  onClick={() => {
                    if (item.report_id) router.push(`/report/${item.report_id}`);
                  }}
                />
              ))}
            </div>
          </section>
        )}

        {!loadingHistory && recentJobs.length === 0 && (
          <div className="text-center py-10 space-y-2">
            <p className="text-gray-400 text-sm">No analyses yet — upload your first stroke video to get started.</p>
          </div>
        )}
      </div>
    </main>
  );
}
