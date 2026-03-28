#pragma once
#include <vector>
#include <string>
#include <map>

// Calculates joint angles (in degrees) for key joints per frame.
// Returns a map of joint_name -> per-frame angle values.
std::map<std::string, std::vector<float>> calculate_joint_angles(
    const std::vector<std::vector<float>>& normalized_frames  // shape: [N_frames][99]
);
