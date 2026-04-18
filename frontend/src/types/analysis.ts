export type ShotType = "serve" | "forehand" | "backhand" | "volley";

export type JobStatus = "queued" | "processing" | "complete" | "failed";

export type JobStage =
  | "queued"
  | "pose_extraction"
  | "phase_detection"
  | "normalization"
  | "comparison"
  | "feedback"
  | "complete"
  | "failed";

export interface ProPlayer {
  id: string;
  name: string;
  gender: "atp" | "wta";
  thumbnail_url: string;
  shot_types: string[];
}

export interface UploadResponse {
  job_id: string;
  status: JobStatus;
  estimated_wait_seconds: number;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  progress_pct: number;
  stage: JobStage;
  warning_code?: string;
  report_id?: string;
}

export interface CoachingFlaw {
  flaw_index: number;
  what: string;
  why: string;
  fix_drill: string;
  impact_order: number;
}

export interface JointAngleData {
  user_mean: number;
  pro_mean: number;
  delta_mean: number;
}

export interface PhaseMetric {
  similarity: number;
  joints: Record<string, { user_mean: number; pro_mean: number | null }>;
}

export interface ReportResponse {
  report_id: string;
  job_id: string;
  shot_type: string;
  pro_player_id: string;
  pro_player_name: string;
  similarity_score: number;
  joint_angles: Record<string, JointAngleData>;
  phase_metrics: Record<string, PhaseMetric>;
  coaching_feedback: CoachingFlaw[];
  warning_code?: string;
  created_at: string;
}

export interface JobHistoryItem {
  job_id: string;
  shot_type: string;
  pro_player_name: string;
  status: JobStatus;
  similarity_score: number | null;
  report_id: string | null;
  created_at: string;
}

export interface JobHistoryResponse {
  jobs: JobHistoryItem[];
}
