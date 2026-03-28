"""
Tests for pure functions in worker/worker.py.
Modal, MediaPipe, CV2, and boto3 are all mocked — no GPU or network required.
"""
import sys
import types
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Stub out Modal before importing worker so the module-level decorators
# don't fail in a test environment that has no Modal token.
# ---------------------------------------------------------------------------
def _stub_modal():
    modal = types.ModuleType("modal")
    modal.App = MagicMock(return_value=MagicMock())
    modal.Image = MagicMock()
    modal.Image.debian_slim = MagicMock(return_value=MagicMock(
        apt_install=MagicMock(return_value=MagicMock(
            pip_install_from_requirements=MagicMock(return_value=MagicMock())
        ))
    ))
    modal.Secret = MagicMock()
    modal.Secret.from_name = MagicMock(return_value=MagicMock())
    modal.Period = MagicMock(return_value=MagicMock())

    # Make the app.function decorator a no-op
    def _noop_decorator(**kwargs):
        def decorator(fn):
            return fn
        return decorator
    modal.App.return_value.function = _noop_decorator

    sys.modules["modal"] = modal


_stub_modal()

# Now import the pure functions (not the Modal-decorated ones)
sys.path.insert(0, "/Users/daifurichardye/tennis-coach-app/worker")
from worker import (
    check_poor_angle,
    detect_stroke_phases,
    _normalize_python_fallback,
    persist_results,
    _update_job,
    _set_stage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_frames(n: int, wrist_x_values=None) -> list[list[float]]:
    """Create n synthetic frames with 99 floats each (33 kp × 3 coords).

    Keypoint layout (BlazePose): indices 0..32, each with x,y,z at positions idx*3, idx*3+1, idx*3+2.
    Key indices used by the worker:
      - LEFT_SHOULDER=11, RIGHT_SHOULDER=12, LEFT_HIP=23, RIGHT_HIP=24
      - WRIST_R=16
    """
    frames = []
    for i in range(n):
        frame = [0.0] * 99
        # LEFT_SHOULDER (11) — place at y=1.5 so torso scale is non-zero
        frame[11 * 3 + 1] = 1.5
        # LEFT_HIP (23) — at origin
        frame[23 * 3 + 1] = 0.0
        # RIGHT_HIP (24) — at origin
        frame[24 * 3 + 1] = 0.0
        # RIGHT_WRIST (16) — varying x to create velocity
        if wrist_x_values:
            frame[16 * 3] = wrist_x_values[i] if i < len(wrist_x_values) else 0.0
        frames.append(frame)
    return frames


# ---------------------------------------------------------------------------
# check_poor_angle
# ---------------------------------------------------------------------------

class TestCheckPoorAngle:
    def test_empty_frames_returns_true(self):
        assert check_poor_angle([], []) is True

    def test_all_high_confidence_returns_false(self):
        frames = _make_frames(10)
        vis = [0.9] * 10
        assert check_poor_angle(frames, vis) is False

    def test_all_low_confidence_returns_true(self):
        frames = _make_frames(10)
        vis = [0.2] * 10
        assert check_poor_angle(frames, vis) is True

    def test_exactly_30_percent_low_returns_false(self):
        """30% low confidence is exactly at the boundary — should NOT trigger warning."""
        frames = _make_frames(10)
        vis = [0.2] * 3 + [0.9] * 7   # 30% below threshold
        assert check_poor_angle(frames, vis) is False

    def test_just_over_30_percent_low_returns_true(self):
        frames = _make_frames(10)
        vis = [0.2] * 4 + [0.9] * 6   # 40% below threshold
        assert check_poor_angle(frames, vis) is True

    def test_visibility_boundary_value_059(self):
        """0.59 is below the 0.6 threshold — counts as low confidence."""
        frames = _make_frames(10)
        vis = [0.59] * 10
        assert check_poor_angle(frames, vis) is True

    def test_visibility_exactly_060_not_low(self):
        """0.6 is exactly at threshold — should NOT count as low confidence."""
        frames = _make_frames(10)
        vis = [0.6] * 10
        assert check_poor_angle(frames, vis) is False

    def test_single_frame_high_confidence(self):
        frames = _make_frames(1)
        assert check_poor_angle(frames, [0.9]) is False

    def test_single_frame_low_confidence(self):
        frames = _make_frames(1)
        assert check_poor_angle(frames, [0.1]) is True


# ---------------------------------------------------------------------------
# detect_stroke_phases
# ---------------------------------------------------------------------------

class TestDetectStrokePhases:
    def test_fewer_than_4_frames_all_preparation(self):
        frames = _make_frames(3)
        phases = detect_stroke_phases(frames, 30.0, "serve")
        assert all(v == "preparation" for v in phases.values())
        assert len(phases) == 3

    def test_returns_all_four_phases(self):
        # Create wrist motion that clearly rises and falls
        n = 60
        wrist_x = [float(i) * 0.1 for i in range(n // 2)] + \
                  [float(n // 2 - i) * 0.1 for i in range(n // 2)]
        frames = _make_frames(n, wrist_x_values=wrist_x)
        phases = detect_stroke_phases(frames, 30.0, "serve")
        phase_values = set(phases.values())
        assert "preparation" in phase_values
        assert "loading" in phase_values
        assert "contact" in phase_values
        assert "follow_through" in phase_values

    def test_phase_keys_cover_all_frames(self):
        n = 30
        frames = _make_frames(n)
        phases = detect_stroke_phases(frames, 30.0, "forehand")
        assert len(phases) == n
        assert set(phases.keys()) == set(range(n))

    def test_phase_values_are_valid_strings(self):
        valid = {"preparation", "loading", "contact", "follow_through"}
        frames = _make_frames(20)
        phases = detect_stroke_phases(frames, 30.0, "serve")
        assert all(v in valid for v in phases.values())

    def test_still_wrist_all_frames_classified(self):
        """When the wrist doesn't move, argmax returns frame 0 (peak at start),
        so all frames are classified as contact or follow_through — no crash."""
        frames = _make_frames(30)  # All wrist positions at 0 → zero velocity
        phases = detect_stroke_phases(frames, 30.0, "serve")
        assert len(phases) == 30
        valid = {"preparation", "loading", "contact", "follow_through"}
        assert all(v in valid for v in phases.values())
        # With peak at frame 0, no frame satisfies i < 0, so preparation/loading are absent
        assert "contact" in phases.values() or "follow_through" in phases.values()

    def test_handles_high_fps(self):
        frames = _make_frames(30)
        phases = detect_stroke_phases(frames, 120.0, "serve")
        assert len(phases) == 30

    def test_handles_low_fps(self):
        frames = _make_frames(10)
        phases = detect_stroke_phases(frames, 24.0, "serve")
        assert len(phases) == 10


# ---------------------------------------------------------------------------
# _normalize_python_fallback
# ---------------------------------------------------------------------------

class TestNormalizePythonFallback:
    def test_output_shape_matches_input(self):
        frames = _make_frames(5)
        result = _normalize_python_fallback(frames)
        assert len(result) == 5
        assert all(len(f) == 99 for f in result)

    def test_hip_midpoint_becomes_near_zero(self):
        """After normalization, the hip midpoint should be close to origin."""
        frames = _make_frames(1)
        result = _normalize_python_fallback(frames)
        f = result[0]
        # LEFT_HIP=23, RIGHT_HIP=24
        left_hip_x  = f[23 * 3]
        right_hip_x = f[24 * 3]
        left_hip_y  = f[23 * 3 + 1]
        right_hip_y = f[24 * 3 + 1]
        # Origin is midpoint of hips — each hip should be ~±0.5 around origin
        assert abs((left_hip_x + right_hip_x) / 2) < 1e-5
        assert abs((left_hip_y + right_hip_y) / 2) < 1e-5

    def test_zero_torso_scale_handled_gracefully(self):
        """If LEFT_SHOULDER == LEFT_HIP (scale=0), should not raise ZeroDivisionError."""
        frame = [0.0] * 99  # All zeros → shoulder and hip coincide
        result = _normalize_python_fallback([frame])
        assert len(result) == 1
        assert len(result[0]) == 99

    def test_identical_frames_produce_identical_output(self):
        frame = _make_frames(1)[0]
        result = _normalize_python_fallback([frame, frame])
        assert result[0] == result[1]

    def test_normalization_is_scale_invariant(self):
        """Doubling all coordinates should produce the same normalized output."""
        frame_1x = _make_frames(1)[0]
        frame_2x = [v * 2 for v in frame_1x]
        r1 = _normalize_python_fallback([frame_1x])[0]
        r2 = _normalize_python_fallback([frame_2x])[0]
        for a, b in zip(r1, r2):
            assert abs(a - b) < 1e-4

    def test_empty_input_returns_empty(self):
        assert _normalize_python_fallback([]) == []


# ---------------------------------------------------------------------------
# persist_results
# ---------------------------------------------------------------------------

class TestPersistResults:
    def _make_sb(self):
        sb = MagicMock()
        sb.table.return_value = sb
        sb.insert.return_value = sb
        sb.execute.return_value = MagicMock(data=[])
        return sb

    def test_inserts_all_frames(self):
        sb = self._make_sb()
        frames = _make_frames(5)
        phase_map = {i: "preparation" for i in range(5)}
        persist_results(sb, "job-1", frames, phase_map)

        # Total rows = 5, all in one batch (< 100)
        sb.insert.assert_called_once()
        rows = sb.insert.call_args[0][0]
        assert len(rows) == 5

    def test_each_row_has_correct_structure(self):
        sb = self._make_sb()
        frames = _make_frames(2)
        phase_map = {0: "preparation", 1: "loading"}
        persist_results(sb, "job-42", frames, phase_map)

        rows = sb.insert.call_args[0][0]
        assert rows[0]["job_id"] == "job-42"
        assert rows[0]["frame_index"] == 0
        assert rows[0]["phase"] == "preparation"
        assert len(rows[0]["keypoints"]) == 33
        assert rows[1]["phase"] == "loading"

    def test_keypoints_have_xyz_keys(self):
        sb = self._make_sb()
        frames = _make_frames(1)
        persist_results(sb, "job-1", frames, {0: "contact"})
        kps = sb.insert.call_args[0][0][0]["keypoints"]
        for kp in kps:
            assert "x" in kp and "y" in kp and "z" in kp

    def test_batches_in_groups_of_100(self):
        sb = self._make_sb()
        frames = _make_frames(250)
        phase_map = {i: "preparation" for i in range(250)}
        persist_results(sb, "job-1", frames, phase_map)

        # 250 frames → 2 full batches of 100 + 1 batch of 50 = 3 insert calls
        assert sb.insert.call_count == 3

    def test_missing_phase_defaults_to_preparation(self):
        sb = self._make_sb()
        frames = _make_frames(3)
        phase_map = {}  # No phase info provided
        persist_results(sb, "job-1", frames, phase_map)
        rows = sb.insert.call_args[0][0]
        assert all(r["phase"] == "preparation" for r in rows)

    def test_empty_frames_makes_no_db_calls(self):
        sb = self._make_sb()
        persist_results(sb, "job-1", [], {})
        sb.insert.assert_not_called()


# ---------------------------------------------------------------------------
# _update_job / _set_stage
# ---------------------------------------------------------------------------

class TestUpdateJob:
    def test_update_job_calls_supabase_correctly(self):
        sb = MagicMock()
        sb.table.return_value = sb
        sb.update.return_value = sb
        sb.eq.return_value = sb
        sb.execute.return_value = MagicMock()
        _update_job(sb, "job-123", status="failed", error_code="NO_PLAYER_DETECTED")
        sb.table.assert_called_with("analysis_jobs")
        sb.update.assert_called_with({"status": "failed", "error_code": "NO_PLAYER_DETECTED"})
        sb.eq.assert_called_with("id", "job-123")

    def test_set_stage_sets_status_to_processing(self):
        sb = MagicMock()
        sb.table.return_value = sb
        sb.update.return_value = sb
        sb.eq.return_value = sb
        sb.execute.return_value = MagicMock()
        _set_stage(sb, "job-abc", "pose_extraction", 25)
        sb.update.assert_called_with({"stage": "pose_extraction", "progress_pct": 25, "status": "processing"})
