#pragma once
#include <vector>

// Normalizes 33 keypoints per frame by torso scale.
// torso_scale = distance between left_shoulder(11) and left_hip(23).
// All keypoints are translated so the hip midpoint is origin, then divided by torso_scale.
std::vector<std::vector<float>> normalize_keypoints(
    const std::vector<std::vector<float>>& frames  // shape: [N_frames][33*3]
);
