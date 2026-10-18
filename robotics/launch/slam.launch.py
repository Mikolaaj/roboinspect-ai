"""Live lidar SLAM in its native frame, anchored at the known BASE spawn."""
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

ROOT = Path(__file__).resolve().parents[2]


def generate_launch_description():
    nodes = [IncludeLaunchDescription(PythonLaunchDescriptionSource(str(
        Path(get_package_share_directory('slam_toolbox')) / 'launch/online_async_launch.py')),
        launch_arguments={'use_sim_time': 'true',
                          'slam_params_file': str(ROOT/'config/slam.yaml')}.items())]
    # Only mapping owns these edges; AMCL is not launched in this mode.
    for parent, child, xyz in [
        ('map', 'map_slam', ['-11', '-7', '0']),
        ('base_link', 'roboinspect/base_link/lidar', ['0.14', '0', '0.29']),
        ('base_link', 'roboinspect/base_link/front_camera', ['0.29', '0', '0.65']),
    ]:
        nodes.append(Node(package='tf2_ros', executable='static_transform_publisher',
                          arguments=['--x', xyz[0], '--y', xyz[1], '--z', xyz[2],
                                     '--frame-id', parent, '--child-frame-id', child],
                          parameters=[{'use_sim_time': True}]))
    return LaunchDescription(nodes)
