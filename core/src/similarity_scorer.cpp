#include "similarity_scorer.h"
#include "dtw_aligner.h"
#include <cmath>
#include <algorithm>

float similarity_score(
    const std::vector<std::vector<float>>& user_frames,
    const std::vector<std::vector<float>>& pro_frames)
{
    if (user_frames.empty() || pro_frames.empty()) return 0.0f;

    float dist = dtw_distance(user_frames, pro_frames);

    // Map distance to 0–100 score using an exponential decay.
    // k is tuned so that dist=0 -> score=100, dist=1.0 -> score ~37, dist=3.0 -> score ~5
    constexpr float k = 1.0f;
    float score = 100.0f * std::exp(-k * dist);
    return std::max(0.0f, std::min(100.0f, score));
}
