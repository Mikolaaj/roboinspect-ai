#!/usr/bin/env bash
set -e
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source /opt/ros/jazzy/setup.bash
mkdir -p "$repo_root/artifacts/bin"
source_file="$repo_root/robotics/visualization/pose_client.cpp"
binary="$repo_root/artifacts/bin/route_pose_client"
if [[ ! -x "$binary" || "$source_file" -nt "$binary" ]]; then
  echo 'Budowanie wizualizacji trasy Gazebo…'
  g++ -std=c++17 -O2 "$source_file" -o "$binary.tmp" $(pkg-config --cflags --libs gz-transport13 gz-msgs10)
  mv "$binary.tmp" "$binary"
fi
