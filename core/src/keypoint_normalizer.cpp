#include "keypoint_normalizer.h"
#include <cmath>
#include <stdexcept>

// BlazePose landmark indices
static constexpr int LEFT_SHOULDER = 11;
static constexpr int RIGHT_SHOULDER = 12;
static constexpr int LEFT_HIP = 23;
static constexpr int RIGHT_HIP = 24;
static constexpr int N_KEYPOINTS = 33;
static constexpr int COORDS = 3; // x, y, z

std::vector<std::vector<float>> normalize_keypoints(
    const std::vector<std::vector<float>>& frames)
{
    if (frames.empty()) return {};

    std::vector<std::vector<float>> result;
    result.reserve(frames.size());

    for (const auto& frame : frames) {
        if (static_cast<int>(frame.size()) != N_KEYPOINTS * COORDS) {
            throw std::invalid_argument("Each frame must have 99 values (33 keypoints × 3 coords)");
        }

        auto kp = [&](int idx, int c) { return frame[idx * COORDS + c]; };

        // Hip midpoint as origin
        float ox = (kp(LEFT_HIP, 0) + kp(RIGHT_HIP, 0)) * 0.5f;
        float oy = (kp(LEFT_HIP, 1) + kp(RIGHT_HIP, 1)) * 0.5f;
        float oz = (kp(LEFT_HIP, 2) + kp(RIGHT_HIP, 2)) * 0.5f;

        // Torso scale: distance from left_shoulder to left_hip
        float dx = kp(LEFT_SHOULDER, 0) - kp(LEFT_HIP, 0);
        float dy = kp(LEFT_SHOULDER, 1) - kp(LEFT_HIP, 1);
        float dz = kp(LEFT_SHOULDER, 2) - kp(LEFT_HIP, 2);
        float scale = std::sqrt(dx*dx + dy*dy + dz*dz);
        if (scale < 1e-6f) scale = 1.0f;

        std::vector<float> normalized(N_KEYPOINTS * COORDS);
        for (int i = 0; i < N_KEYPOINTS; ++i) {
            normalized[i * COORDS + 0] = (kp(i, 0) - ox) / scale;
            normalized[i * COORDS + 1] = (kp(i, 1) - oy) / scale;
            normalized[i * COORDS + 2] = (kp(i, 2) - oz) / scale;
        }

        result.push_back(std::move(normalized));
    }

    return result;
}
