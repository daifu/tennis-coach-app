#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "keypoint_normalizer.h"
#include "joint_angle_calculator.h"
#include "dtw_aligner.h"
#include "similarity_scorer.h"

namespace py = pybind11;

PYBIND11_MODULE(tennis_core, m) {
    m.doc() = "TennisCoach AI — C++ core modules";

    m.def("normalize_keypoints", &normalize_keypoints,
          py::arg("frames"),
          "Normalize keypoint frames by torso scale. Input: list of lists of 99 floats (33 kp × 3 coords). Returns normalized frames.");

    m.def("calculate_joint_angles", &calculate_joint_angles,
          py::arg("normalized_frames"),
          "Calculate joint angles per frame. Returns dict of joint_name -> list of angles in degrees.");

    m.def("dtw_align", &dtw_align,
          py::arg("query"), py::arg("reference"),
          "DTW alignment. Returns list of (query_idx, reference_idx) pairs.");

    m.def("dtw_distance", &dtw_distance,
          py::arg("query"), py::arg("reference"),
          "Normalized DTW distance between two pose sequences.");

    m.def("similarity_score", &similarity_score,
          py::arg("user_frames"), py::arg("pro_frames"),
          "Similarity score 0–100 between user and pro normalized pose sequences.");
}
