#pragma once
#include <vector>

// Dynamic Time Warping alignment.
// Returns the warping path as pairs of (query_idx, reference_idx).
// Both sequences are arrays of feature vectors.
std::vector<std::pair<int,int>> dtw_align(
    const std::vector<std::vector<float>>& query,      // user stroke frames
    const std::vector<std::vector<float>>& reference   // pro stroke frames
);

// Returns the normalized DTW distance (0 = identical).
float dtw_distance(
    const std::vector<std::vector<float>>& query,
    const std::vector<std::vector<float>>& reference
);
