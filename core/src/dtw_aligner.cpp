#include "dtw_aligner.h"
#include <cmath>
#include <limits>
#include <stdexcept>

static float euclidean(const std::vector<float>& a, const std::vector<float>& b) {
    if (a.size() != b.size()) throw std::invalid_argument("Vector size mismatch in DTW");
    float sum = 0.0f;
    for (size_t i = 0; i < a.size(); ++i) {
        float d = a[i] - b[i];
        sum += d * d;
    }
    return std::sqrt(sum);
}

// Standard O(n*m) DTW with full cost matrix
static std::vector<std::vector<float>> build_cost_matrix(
    const std::vector<std::vector<float>>& q,
    const std::vector<std::vector<float>>& r)
{
    int n = static_cast<int>(q.size());
    int m = static_cast<int>(r.size());

    const float INF = std::numeric_limits<float>::infinity();
    std::vector<std::vector<float>> dp(n, std::vector<float>(m, INF));

    dp[0][0] = euclidean(q[0], r[0]);

    for (int i = 1; i < n; ++i)
        dp[i][0] = dp[i-1][0] + euclidean(q[i], r[0]);
    for (int j = 1; j < m; ++j)
        dp[0][j] = dp[0][j-1] + euclidean(q[0], r[j]);

    for (int i = 1; i < n; ++i) {
        for (int j = 1; j < m; ++j) {
            float cost = euclidean(q[i], r[j]);
            dp[i][j] = cost + std::min({dp[i-1][j], dp[i][j-1], dp[i-1][j-1]});
        }
    }

    return dp;
}

std::vector<std::pair<int,int>> dtw_align(
    const std::vector<std::vector<float>>& query,
    const std::vector<std::vector<float>>& reference)
{
    if (query.empty() || reference.empty()) return {};

    auto dp = build_cost_matrix(query, reference);
    int i = static_cast<int>(query.size()) - 1;
    int j = static_cast<int>(reference.size()) - 1;

    std::vector<std::pair<int,int>> path;
    path.emplace_back(i, j);

    while (i > 0 || j > 0) {
        if (i == 0) { --j; }
        else if (j == 0) { --i; }
        else {
            float diag = dp[i-1][j-1];
            float left = dp[i][j-1];
            float up   = dp[i-1][j];
            if (diag <= left && diag <= up) { --i; --j; }
            else if (left <= up)            { --j; }
            else                            { --i; }
        }
        path.emplace_back(i, j);
    }

    std::reverse(path.begin(), path.end());
    return path;
}

float dtw_distance(
    const std::vector<std::vector<float>>& query,
    const std::vector<std::vector<float>>& reference)
{
    if (query.empty() || reference.empty()) return 0.0f;
    auto dp = build_cost_matrix(query, reference);
    int n = static_cast<int>(query.size());
    int m = static_cast<int>(reference.size());
    // Normalize by path length approximation
    return dp[n-1][m-1] / static_cast<float>(n + m);
}
