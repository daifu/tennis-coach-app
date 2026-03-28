#pragma once
#include <vector>

// Computes a similarity score (0.0–100.0) between user and pro normalized pose sequences.
// Uses Euclidean distance over DTW-aligned frames, mapped to a 0–100 scale.
float similarity_score(
    const std::vector<std::vector<float>>& user_frames,
    const std::vector<std::vector<float>>& pro_frames
);
