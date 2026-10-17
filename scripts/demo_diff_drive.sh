#!/usr/bin/env bash
# Run the installed ROS/Gazebo differential-drive example.
set -e
if [ ! -r /opt/ros/jazzy/setup.bash ]; then
    printf 'Missing ROS 2 Jazzy: /opt/ros/jazzy/setup.bash\n' >&2
    exit 1
fi
source /opt/ros/jazzy/setup.bash
exec /usr/bin/python3 /opt/ros/jazzy/bin/ros2 launch ros_gz_sim_demos diff_drive.launch.py rviz:=false "$@"
