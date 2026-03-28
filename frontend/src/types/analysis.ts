export type ShotType = "serve" | "forehand";

export type JobStatus = "queued" | "processing" | "complete" | "failed";

export type JobStage =
  | "queued"
  | "pose_extraction"
  | "phase_detection"
  | "normalization"
  | "complete";

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
