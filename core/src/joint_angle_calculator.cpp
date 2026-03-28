#include "joint_angle_calculator.h"
#include <cmath>

static constexpr int COORDS = 3;

static float angle_between(
    const float* a, const float* vertex, const float* b)
{
    float v1[3] = { a[0]-vertex[0], a[1]-vertex[1], a[2]-vertex[2] };
    float v2[3] = { b[0]-vertex[0], b[1]-vertex[1], b[2]-vertex[2] };

    float dot = v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2];
    float m1  = std::sqrt(v1[0]*v1[0] + v1[1]*v1[1] + v1[2]*v1[2]);
    float m2  = std::sqrt(v2[0]*v2[0] + v2[1]*v2[1] + v2[2]*v2[2]);

    if (m1 < 1e-6f || m2 < 1e-6f) return 0.0f;

    float cos_a = dot / (m1 * m2);
    cos_a = std::max(-1.0f, std::min(1.0f, cos_a));
    return std::acos(cos_a) * 180.0f / M_PI;
}

// BlazePose indices for joints of interest
// right side (dominant for right-handed player)
static constexpr int R_SHOULDER = 12, R_ELBOW = 14, R_WRIST = 16;
static constexpr int L_SHOULDER = 11, L_ELBOW = 13, L_WRIST = 15;
static constexpr int R_HIP = 24, R_KNEE = 26, R_ANKLE = 28;
static constexpr int L_HIP = 23, L_KNEE = 25, L_ANKLE = 27;

std::map<std::string, std::vector<float>> calculate_joint_angles(
    const std::vector<std::vector<float>>& frames)
{
    std::map<std::string, std::vector<float>> result;
    if (frames.empty()) return result;

    size_t n = frames.size();
    result["right_elbow"].reserve(n);
    result["left_elbow"].reserve(n);
    result["right_knee"].reserve(n);
    result["left_knee"].reserve(n);
    result["right_shoulder_abduction"].reserve(n);

    for (const auto& frame : frames) {
        auto kp = [&](int idx) -> const float* {
            return frame.data() + idx * COORDS;
        };

        result["right_elbow"].push_back(
            angle_between(kp(R_SHOULDER), kp(R_ELBOW), kp(R_WRIST)));
        result["left_elbow"].push_back(
            angle_between(kp(L_SHOULDER), kp(L_ELBOW), kp(L_WRIST)));
        result["right_knee"].push_back(
            angle_between(kp(R_HIP), kp(R_KNEE), kp(R_ANKLE)));
        result["left_knee"].push_back(
            angle_between(kp(L_HIP), kp(L_KNEE), kp(L_ANKLE)));
        result["right_shoulder_abduction"].push_back(
            angle_between(kp(R_ELBOW), kp(R_SHOULDER), kp(R_HIP)));
    }

    return result;
}
