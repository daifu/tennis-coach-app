cmake_minimum_required(VERSION 3.18)
project(tennis_core VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Release build flags
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
add_compile_options(-O3 -march=native)

find_package(pybind11 REQUIRED)

pybind11_add_module(tennis_core
    src/bindings.cpp
    src/keypoint_normalizer.cpp
    src/joint_angle_calculator.cpp
    src/dtw_aligner.cpp
    src/similarity_scorer.cpp
)

target_include_directories(tennis_core PRIVATE src)
